# syntax=docker/dockerfile:1.7

FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /src/frontend
ENV CYPRESS_INSTALL_BINARY=0
ENV NODE_OPTIONS=--max-old-space-size=2048
ENV VITE_BUILD_SOURCEMAP=false
ARG BUILD_COPILOT=false

RUN corepack enable && corepack prepare pnpm@9.15.9 --activate

COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
COPY frontend/libs/react-client/package.json ./libs/react-client/package.json
COPY frontend/libs/copilot/package.json ./libs/copilot/package.json

RUN --mount=type=cache,id=pnpm-store,target=/root/.local/share/pnpm/store \
    if [ "$BUILD_COPILOT" = "true" ]; then \
        pnpm install --no-frozen-lockfile --prefer-offline; \
    else \
        pnpm --filter @chainlit/app --filter @chainlit/react-client install --no-frozen-lockfile --prefer-offline; \
    fi

COPY frontend/ ./
RUN --mount=type=cache,id=pnpm-store,target=/root/.local/share/pnpm/store \
    pnpm run build:web && \
    mkdir -p libs/copilot/dist && \
    if [ "$BUILD_COPILOT" = "true" ]; then pnpm run build:copilot; fi


FROM python:3.11-slim AS python-builder

WORKDIR /app/backend

RUN rm -f /etc/apt/sources.list.d/*.sources && \
    echo "deb http://mirrors.aliyun.com/debian/ bookworm main non-free non-free-firmware" > /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian/ bookworm-updates main non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian-security/ bookworm-security main non-free non-free-firmware" >> /etc/apt/sources.list && \
    apt-get clean && \
    apt-get update && \
    apt-get install -y gcc && \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --prefix=/install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt


FROM python:3.11-slim

WORKDIR /app/backend
ENV PYTHONPATH=/app/backend
ENV CHAINLIT_APP_ROOT=/app/backend
ENV CHAINLIT_FRONTEND_DIST=/app/frontend/dist
ENV CHAINLIT_COPILOT_DIST=/app/frontend/libs/copilot/dist

COPY --from=python-builder /install /usr/local

COPY backend/ ./
COPY --from=frontend-builder /src/frontend/dist /app/frontend/dist
COPY --from=frontend-builder /src/frontend/libs/copilot/dist /app/frontend/libs/copilot/dist

RUN mkdir -p /app/backend/data

EXPOSE 8000

CMD ["sh", "-c", "python init_db.py && python -m chainlit run app.py --host 0.0.0.0 --port 8000"]
