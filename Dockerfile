# ---------- 前端构建 ----------
FROM node:20-alpine AS web-build
WORKDIR /web
# 国内服务器构建时可换成 https://registry.npmmirror.com
ARG NPM_REGISTRY=https://registry.npmjs.org
COPY web/package.json ./
RUN npm config set registry "$NPM_REGISTRY" && npm install --no-audit --no-fund
COPY web/ ./
RUN npm run build

# ---------- 运行时 ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
# 国内服务器构建时可换成 https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN pip install -i "$PIP_INDEX_URL" -r requirements.txt

COPY app ./app
COPY knowledge ./knowledge
COPY scripts ./scripts
COPY pyproject.toml ./
COPY --from=web-build /web/dist ./web/dist

RUN mkdir -p data/kb

# DevCloud 仅路由容器端口 8080，应用必须监听 8080 并绑定 0.0.0.0
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
