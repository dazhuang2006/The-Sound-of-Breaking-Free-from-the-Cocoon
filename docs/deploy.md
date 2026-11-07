# 部署到自己的云服务器（京东云 ECS / 任意 Linux）

> 目标：在一台普通 Linux 云主机上把「破茧之声」跑起来，浏览器能打开、能登录、能对话。
> 全文命令可直接复制，`<公网IP>` 换成你服务器地址。

## 0. 先选路线

| | 路线 A：Docker Compose | 路线 B：裸机 + SQLite |
| --- | --- | --- |
| 适合 | 能 `sudo`、服务器有外网 | 权限少、不想装 Docker |
| 数据库 | MySQL 8（容器内，自动初始化） | SQLite 单文件 |
| 前端 | 构建镜像时自动打包 | 必须本机先构建再上传 |
| 依赖 | 只要 Docker | 需要 Python 3.11+ |
| 数据持久化 | Docker volume | `data/app.db` 文件 |
| 推荐度 | ★★★★★ 一条命令起全套 | ★★★☆ 最省权限 |

两条路线**不要混用**。下面按顺序给。

---

## 1. 把代码送到服务器

前端产物 `web/dist/` 被 `.gitignore` 排除了（`web/dist/` 在忽略列表里），所以：

- **路线 A**：Dockerfile 里会用 Node 自动构建，服务器上不需要 node；
- **路线 B**：必须在你本机先构建，再连 `dist` 一起传上去，否则打开就是白屏/404。

### 1.1 本机打包（推荐，绕开服务器拉 GitHub 慢）

在 **Windows 本机**、项目根目录执行：

```powershell
cd D:\python\xiangmu\soud

# 前端产物（路线 B 必需；路线 A 也可带着，省得服务器再构建）
cd web; npm install; npm run build; cd ..

# 打一个不含虚拟环境/依赖/密钥/数据的包
tar -czf soud-deploy.tar.gz --exclude=.git --exclude=.venv --exclude=node_modules --exclude=data --exclude=.env .
```

> `tar` 是 Windows 10 以后自带的，不用另装。包体大约几 MB。

上传并解压（在你本机执行）：

```powershell
scp soud-deploy.tar.gz root@<公网IP>:/tmp/
```

服务器上：

```bash
sudo mkdir -p /opt/soud
sudo tar -xzf /tmp/soud-deploy.tar.gz -C /opt/soud
sudo chown -R $USER:$USER /opt/soud
ls /opt/soud        # 应该看到 app/ web/ knowledge/ Dockerfile ...
```

### 1.2 或者直接在服务器 clone（服务器能访问 GitHub 时）

```bash
sudo mkdir -p /opt/soud && sudo chown -R $USER:$USER /opt/soud
git clone https://github.com/dazhuang2006/The-Sound-of-Breaking-Free-from-the-Cocoon.git /opt/soud
```

> 国内机器拉 GitHub 经常卡住。拉不动就用 1.1，或者把仓库镜像到 Gitee 再 clone。

---

## 2. 路线 A：Docker Compose

### 2.1 装 Docker（Ubuntu / Debian）

```bash
curl -fsSL https://get.docker.com | sudo sh -s -- --mirror Aliyun
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
newgrp docker            # 或者退出重登，让 docker 组生效
docker compose version   # 能看到 v2.x 即可
```

CentOS / openEuler / 麒麟：

```bash
sudo yum install -y yum-utils
sudo yum-config-manager --add-repo https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo
sudo yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable --now docker
```

### 2.2 配 .env

```bash
cd /opt/soud
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # 生成 SECRET_KEY
```

用 `vim .env` 改这几项（其余保持默认即可）：

```env
ENV=prod
SECRET_KEY=<粘贴上面生成的那串，必须 ≥32 位>

MYSQL_DATABASE=pojian
MYSQL_USER=pojian
MYSQL_PASSWORD=<换成一串随机密码>
MYSQL_ROOT_PASSWORD=<再换一串随机密码>

# 宿主机端口：8000 是应用，3306/6379 只是给本机调试用
API_HOST_PORT=8000
MYSQL_HOST_PORT=13306
REDIS_HOST_PORT=16379

# 国内构建提速（可选，但强烈建议）
PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
NPM_REGISTRY=https://registry.npmmirror.com

# 想用真实模型就打开（默认 mock 是离线模板回复）
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-你的key
```

> `.env.example` 里自带一行 `DATABASE_URL=sqlite+...`，Compose 会用上面的 `MYSQL_*` 自动拼出
> 容器内 MySQL 地址并覆盖它，**不用特意删**。唯一要避免的是把它改成你自己机器的 MySQL 地址，
> 那样排查时会看糊涂。

### 2.3 起服务

```bash
cd /opt/soud
docker compose up -d --build
docker compose ps                 # api / mysql / redis 都应是 running（mysql 是 healthy）
docker compose logs -f api        # 看到「服务就绪｜LLM=...」说明启动完成，Ctrl+C 退出日志
curl -s http://127.0.0.1:8000/health
```

期望输出类似：

```json
{"status":"ok","app":"破茧之声","components":{"database":"ok","cache":"redis",...}}
```

### 2.4 初始化演示数据（可选）

```bash
docker compose exec api python -m scripts.seed_demo
```

会创建账号 `demo / demo123456`、孩子档案和 7 天记录，答辩演示直接用。

---

## 3. 路线 B：裸机 + SQLite

### 3.1 装 Python 3.11+

```bash
python3 --version           # 需要 ≥ 3.11
# Ubuntu 没装或版本低：
sudo apt update && sudo apt install -y python3 python3-venv python3-pip
```

### 3.2 建虚拟环境、装依赖

```bash
cd /opt/soud
python3 -m venv .venv
.venv/bin/pip install -U pip -i https://pypi.tuna.tsinghua.edu.cn/simple
.venv/bin/pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

> 如果报内存不足（1G 小机器常见），先加 swap，或只装必需包。

### 3.3 配 .env（SQLite 模板）

```bash
cd /opt/soud
cat > .env <<'EOF'
ENV=prod
SECRET_KEY=把这里换成本机生成的随机串
DATABASE_URL=sqlite+aiosqlite:///./data/app.db
AUTO_CREATE_TABLES=true
CACHE_ENABLED=false
HOST=0.0.0.0
PORT=8000
EOF
```

生成密钥：`python3 -c "import secrets; print(secrets.token_urlsafe(48))"`，替换掉上面那行。
`CACHE_ENABLED=false` 是为了不依赖 Redis（不装也能跑）。

> `HOST` / `PORT` 写进 `.env` 也会生效：`run.py` 启动时会先把 `.env` 读进进程环境
> （不覆盖已存在的环境变量）。所以 `.env` 和 `HOST=0.0.0.0 python run.py` 两种写法都行，
> 显式环境变量优先级更高。

需要语音/模型就再追加（照抄你本地 `.env` 的值）：

```env
ASR_PROVIDER=http
ASR_HTTP_URL=https://api.siliconflow.cn/v1/audio/transcriptions
ASR_HTTP_API_KEY=sk-...
ASR_HTTP_MODEL=FunAudioLLM/SenseVoiceSmall
ASR_HTTP_TRUST_ENV=false

TTS_PROVIDER=siliconflow
TTS_API_KEY=sk-...
TTS_TRUST_ENV=false
```

### 3.4 前台试跑一次

```bash
cd /opt/soud
.venv/bin/python run.py
```

看到「应用地址 http://127.0.0.1:8000」后，另开一个终端 `curl -s localhost:8000/health`，通了再 `Ctrl+C`。

### 3.5 注册成 systemd 服务（推荐，挂了自动拉起）

```bash
sudo tee /etc/systemd/system/soud.service > /dev/null <<'EOF'
[Unit]
Description=pojian-voice (破茧之声)
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/soud
ExecStart=/opt/soud/.venv/bin/python run.py
Environment=HOST=0.0.0.0
Environment=PORT=8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now soud
sudo systemctl status soud
sudo journalctl -u soud -f        # 看日志
```

### 3.6 没有 sudo 时：nohup 兜底

```bash
cd /opt/soud
nohup .venv/bin/python run.py > run.log 2>&1 &
tail -f run.log
```

---

## 4. 放行端口（十有八九卡在这）

1. **云平台安全组**：京东云控制台 → 云主机 → 实例 → 安全组 → 入站规则 → 添加
   - 协议 `TCP`、端口 `8000`、源 `0.0.0.0/0`
2. **系统防火墙**（开着才需要）：

```bash
sudo ufw allow 8000/tcp                 # Ubuntu
sudo firewall-cmd --add-port=8000/tcp --permanent && sudo firewall-cmd --reload   # CentOS
```

3. **确认真的在监听**：

```bash
ss -lntp | grep 8000      # 应看到 0.0.0.0:8000 或 *:8000，不是 127.0.0.1:8000
```

> 如果是 `127.0.0.1:8000`，说明 `HOST` 没设成 `0.0.0.0`（Docker 路线不用管，容器内部已经是 0.0.0.0）。

4. **最后从你自己的电脑验证**（不是服务器上）：

```powershell
curl.exe http://<公网IP>:8000/health
```

浏览器打开 `http://<公网IP>:8000`。

### 4.1 服务器上已经有 nginx 占着 80？

这时更省事的做法是让 nginx 反向代理，不用再去开 8000 端口（80 通常本来就放行了）。
以 `/etc/nginx/sites-available/你的站点` 为例，把 `server` 块换成：

```nginx
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    client_max_body_size 25m;      # 语音上传默认 ≤20MB，留余量

    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_types text/plain text/css application/javascript application/json image/svg+xml;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
```

```bash
sudo cp /etc/nginx/sites-available/你的站点 /root/nginx-site.conf.bak   # 先备份
sudo nginx -t && sudo systemctl reload nginx
curl -s http://127.0.0.1/ | grep -o '<title>[^<]*</title>'
```

> 注意两点：
> 1. 换完之后原来 80 上的站点就不对外了，但文件还在，想切回去把备份覆盖回来再 reload 即可；
> 2. `client_max_body_size` 不设的话，上传语音会得到 `413 Request Entity Too Large`。

---

## 5. 验收清单

- [ ] `/health` 返回 `"status":"ok"`，且 `components.database` 是 `ok`
- [ ] 首页能打开（不是白屏、不是 404）
- [ ] 能注册或 `demo / demo123456` 登录
- [ ] 新建会话、发一条消息有回复（mock 模式也会回模板）
- [ ] 重启服务器后，服务自动起来（`systemctl` 或 compose 的 `restart: unless-stopped`）
- [ ] 断网重连、刷新子页面（如 `/#/game`）不报错

---

## 6. 日常运维

```bash
# 看日志
docker compose logs -f api          # 路线 A
sudo journalctl -u soud -f          # 路线 B

# 更新代码后重启
docker compose up -d --build        # 路线 A
sudo systemctl restart soud         # 路线 B

# 停 / 起
docker compose stop && docker compose start
sudo systemctl stop soud && sudo systemctl start soud

# 备份数据
docker run --rm -v pojian-voice_mysql_data:/data -v $PWD:/backup alpine tar czf /backup/mysql-$(date +%F).tar.gz -C /data .   # 路线 A
cp data/app.db data/app.db.$(date +%F)                                                                                          # 路线 B
```

---

## 7. 常见错误对照表

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 浏览器弹「网络异常，请稍后再试」 | 端口没放行 / 服务没起 | 先 `curl` 服务器本机 `/health`，再查安全组 |
| 页面白屏、控制台 404 | `web/dist` 没构建或没上传（路线 B） | 本机 `cd web && npm run build` 后重传 |
| 启动即退出：`生产环境必须通过 SECRET_KEY 配置…` | `ENV=prod` 但密钥是默认值或太短 | 换 32 位以上随机串 |
| `Can't connect to MySQL server on '127.0.0.1'` | `.env` 里写了本机 MySQL 地址 | 路线 B 改成 SQLite；路线 A 删掉这行 |
| `docker compose` 报 `port is already allocated` | 端口被占用 | 改 `.env` 的 `API_HOST_PORT` |
| `systemctl restart` 后 nginx 502，`ss` 显示服务跑到 8001 | 重启瞬间旧 socket 处于 TIME_WAIT，旧版 `run.py` 端口探测未设 `SO_REUSEADDR`，误判占用后自动顺延 | 已修复（`run.py` 绑定探测加 `SO_REUSEADDR`）；线上更新 `run.py` 后重启即可 |
| 构建卡在 npm/pip 几分钟不动 | 没走国内源 | `.env` 设置 `PIP_INDEX_URL`、`NPM_REGISTRY` 后重新 build |
| `no space left on device` | 镜像+日志占满盘 | `docker system prune -af`，或换大点的盘 |
| 上传录音报 503 | `ASR_PROVIDER` 还是 `disabled` | `.env` 配好 `ASR_*` 再重启 |

---

## 8. 安全底线（对外演示前务必做）

- `.env` **绝不进 git**（已在 `.gitignore` 里），也不要贴到群里；
- 示例密码全部换掉，`SECRET_KEY` 每台机器独立生成；
- 不要把 MySQL 的 3306 暴露到公网：安全组不要放行，或把 compose 里的端口改成 `127.0.0.1:${MYSQL_HOST_PORT}:3306`；
- 正式对外建议前面挂 Nginx + HTTPS，应用只监听内网；
- 演示数据不要录入真实儿童信息。
