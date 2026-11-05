"""把 knowledge/ 下的 Markdown 全量重新入库。

用法：python -m scripts.ingest_kb
"""

from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.base import dispose_engine, init_db
from app.services.container import build_services, close_services


async def main() -> None:
    settings = get_settings()
    configure_logging(True)
    await init_db()
    services = await build_services(settings)
    report = await services.kb.ingest_directory(settings.kb_dir, replace=True)
    print("入库完成:", report.to_dict())
    print("当前知识块数量:", await services.kb.count())
    await close_services(services)
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
