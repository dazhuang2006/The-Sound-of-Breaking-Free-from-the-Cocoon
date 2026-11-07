"""破茧之声 · 本地启动入口（后端 + 已构建的前端，一条命令跑起来）。

用法（在项目根目录，或在任意目录用绝对路径执行）：

    python run.py                       # 默认 127.0.0.1:8000，端口被占用时自动顺延
    PORT=8012 python run.py             # 指定端口（Windows: $env:PORT=8012; python run.py）
    HOST=0.0.0.0 python run.py          # 允许局域网访问，启动时会打印局域网地址
    RELOAD=1 python run.py              # 开发模式：只监听 app/ 目录，改代码自动重载
    WORKERS=4 python run.py             # 多进程（不能与 RELOAD=1 同时使用）
    OPEN=1 python run.py                # 服务就绪后自动用默认浏览器打开
    ACCESS_LOG=0 python run.py          # 关闭访问日志

说明：
- 唯一需要手动执行的文件；FastAPI 应用本体在 `app/main.py`，入口变量是 `app`；
- 端口被占用时不会直接退出，会在 PORT 之后的若干端口里找一个可用的；
- 如果 `web/dist` 已构建，访问 http://127.0.0.1:<端口> 就是完整前端；
  未构建时只提供接口，控制台会给出构建与开发两种命令；
- 开发模式只监听 `app/`，不会因为 `web/node_modules` 或数据库文件变化而重载；
- 其它配置（数据库、DeepSeek、ASR/TTS 等）仍然读项目根目录的 `.env`。
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parent
APP_IMPORT = "app.main:app"
MIN_PYTHON = (3, 11)
LOG_LEVELS = {"critical", "error", "warning", "info", "debug", "trace"}


# ---------------------------------------------------------------- 输出与校验
def _step(message: str) -> None:
    print(f"  {message}")


def _fail(message: str, hint: str | None = None) -> NoReturn:
    print(f"\n启动失败：{message}")
    if hint:
        print(f"  解决方式：{hint}")
    raise SystemExit(1)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        _fail(f"{name} 必须是整数，当前是 {raw!r}", f"例如：{name}={default} python run.py")
    if not minimum <= value <= maximum:
        _fail(f"{name} 需要在 {minimum}～{maximum} 之间，当前是 {value}")
    return value


def _prepare_workdir() -> None:
    """无论从哪个目录执行，都把工作目录切到项目根，保证 .env / app / web 都能找到。"""
    if Path.cwd() != ROOT:
        os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))


def _load_dotenv() -> None:
    """把项目根目录的 .env 读进进程环境（已有的环境变量优先，不会被覆盖）。

    pydantic 读 .env 只作用于 Settings 对象，不会写回 os.environ；
    而 HOST / PORT / RELOAD / OPEN 这些启动参数读的是 os.getenv。
    没有这一步，.env 里写 HOST=0.0.0.0 不会生效，服务仍会绑 127.0.0.1，
    导致云服务器上公网访问不到。
    """
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:  # python-dotenv 由 pydantic-settings 间接安装
        return
    load_dotenv(env_path, override=False)


def _check_project_layout() -> None:
    if not (ROOT / "app" / "main.py").is_file():
        _fail(
            "没有找到 app/main.py，看起来不在项目根目录",
            "确认 run.py 与 app/ 目录在同一个文件夹，或用绝对路径执行 run.py",
        )


# ---------------------------------------------------------------- 端口
def _port_available(host: str, port: int) -> bool:
    """先尝试绑定一次，避免 uvicorn 启动后才发现端口冲突。

    SO_REUSEADDR 是必须的：服务重启时旧监听 socket 会进入 TIME_WAIT，
    不设这个选项会误判为「端口被占用」，进而自动顺延到 8001，
    结果 systemd 里起来的是 8001，而 nginx / 安全组仍指向 8000。
    """
    probe_host = {"localhost": "127.0.0.1", "": "127.0.0.1"}.get(host, host)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((probe_host, port))
        except OSError:
            return False
    return True


def _pick_port(host: str, preferred: int, span: int) -> int:
    if _port_available(host, preferred):
        return preferred
    print(f"\n提示：端口 {preferred} 已被占用，正在寻找可用端口…")
    upper = min(65535, preferred + span)
    for candidate in range(preferred + 1, upper + 1):
        if _port_available(host, candidate):
            _step(f"已自动切换到端口 {candidate}")
            return candidate
    _fail(
        f"{preferred}～{upper} 都被占用",
        f"手动换一段端口：PORT={upper + 1} python run.py",
    )


def _lan_address() -> str | None:
    """取局域网 IPv4（UDP connect 不会真的发包）。"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            return probe.getsockname()[0]
    except OSError:
        return None


# ---------------------------------------------------------------- 前端与浏览器
def _frontend_hint() -> str:
    dist = ROOT / "web" / "dist" / "index.html"
    if dist.is_file():
        return "已构建（web/dist），访问根地址即可打开完整前端"
    return "未构建：只提供接口；构建命令 cd web && pnpm install && pnpm build"


def _open_browser_later(url: str, timeout: float = 25.0) -> None:
    def worker() -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=1.5) as response:  # noqa: S310
                    if response.status < 500:
                        webbrowser.open(url)
                        return
            except (urllib.error.URLError, OSError, ValueError):
                time.sleep(0.6)
        _step("服务没有在预期时间内就绪，可手动打开上面的地址")

    threading.Thread(target=worker, name="open-browser", daemon=True).start()


# ---------------------------------------------------------------- 主流程
def main() -> None:
    if sys.version_info < MIN_PYTHON:
        _fail(
            f"需要 Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} 及以上，当前是 "
            f"{sys.version_info.major}.{sys.version_info.minor}",
            "用 3.11+ 创建虚拟环境后重试",
        )

    _prepare_workdir()
    _load_dotenv()
    _check_project_layout()

    try:
        import uvicorn
    except ModuleNotFoundError:
        _fail(
            "缺少 uvicorn 依赖",
            "先安装依赖：pip install -r requirements.txt（开发环境用 requirements-dev.txt）",
        )

    host = (os.getenv("HOST") or "127.0.0.1").strip() or "127.0.0.1"
    preferred = _env_int("PORT", 8000, minimum=1, maximum=65535)
    span = _env_int("PORT_SPAN", 50, minimum=1, maximum=1000)
    reload_enabled = _env_bool("RELOAD")
    open_browser = _env_bool("OPEN")
    access_log = _env_bool("ACCESS_LOG", True)
    workers = _env_int("WORKERS", 1, minimum=1, maximum=16)
    log_level = (os.getenv("LOG_LEVEL") or "info").strip().lower()
    if log_level not in LOG_LEVELS:
        _fail(
            f"LOG_LEVEL={log_level!r} 不支持",
            f"可选：{', '.join(sorted(LOG_LEVELS))}",
        )

    if reload_enabled and workers > 1:
        _step("RELOAD=1 与 WORKERS>1 不能同时使用，已按单进程热重载启动")
        workers = 1

    port = _pick_port(host, preferred, span)
    display_host = "127.0.0.1" if host in {"0.0.0.0", "::", "localhost", ""} else host
    url = f"http://{display_host}:{port}"
    lan = _lan_address() if host in {"0.0.0.0", "::"} else None

    print()
    print("破茧之声 · 本地服务")
    print(f"  应用地址    {url}")
    if lan:
        print(f"  局域网      http://{lan}:{port}")
    print(f"  接口文档    {url}/docs")
    print(f"  健康检查    {url}/health")
    print(f"  前端资源    {_frontend_hint()}")
    mode = "开发模式（热重载 app/）" if reload_enabled else f"生产模式（workers={workers}）"
    print(f"  运行模式    {mode}")
    if not (ROOT / "web" / "dist" / "index.html").is_file():
        print("  前端开发    cd web && pnpm dev   # 5173 端口，代理固定指向 127.0.0.1:8000")
        if port != 8000:
            print("              注意：Vite 代理只指向 8000，想前后端联调请用 PORT=8000")
    print("\n按 Ctrl+C 停止服务")
    print()

    if open_browser:
        _open_browser_later(f"{url}/health")

    kwargs: dict[str, object] = {
        "app": APP_IMPORT,
        "host": host,
        "port": port,
        "log_level": log_level,
        "access_log": access_log,
        "timeout_graceful_shutdown": 10,
    }
    if reload_enabled:
        kwargs.update(
            {
                "reload": True,
                "reload_dirs": [str(ROOT / "app")],
                "reload_includes": ["*.py"],
            }
        )
    else:
        kwargs.update({"reload": False, "workers": workers})

    try:
        uvicorn.run(**kwargs)  # type: ignore[arg-type]
    except KeyboardInterrupt:  # pragma: no cover - 手动停止
        print("\n已停止。")
    except OSError as exc:  # 端口在检测后被抢占等极端情况
        _fail(
            f"启动失败：{exc}",
            f"换一个端口：PORT={port + 1} python run.py",
        )


if __name__ == "__main__":
    main()
