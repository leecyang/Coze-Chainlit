FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /src/frontend
ENV CYPRESS_INSTALL_BINARY=0

RUN corepack enable && corepack prepare pnpm@9.15.9 --activate

COPY frontend/ ./
RUN pnpm install --no-frozen-lockfile && pnpm run build


FROM python:3.11-slim

WORKDIR /app/backend
ENV PYTHONPATH=/app/backend
ENV CHAINLIT_APP_ROOT=/app/backend
ENV CHAINLIT_FRONTEND_DIST=/app/frontend/dist
ENV CHAINLIT_COPILOT_DIST=/app/frontend/libs/copilot/dist

RUN rm -f /etc/apt/sources.list.d/*.sources && \
    echo "deb http://mirrors.aliyun.com/debian/ bookworm main non-free non-free-firmware" > /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian/ bookworm-updates main non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian-security/ bookworm-security main non-free non-free-firmware" >> /etc/apt/sources.list && \
    apt-get clean && \
    apt-get update && \
    apt-get install -y gcc && \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

COPY backend/ ./
COPY --from=frontend-builder /src/frontend/dist /app/frontend/dist
COPY --from=frontend-builder /src/frontend/libs/copilot/dist /app/frontend/libs/copilot/dist

RUN mkdir -p /app/backend/data

EXPOSE 8000

CMD ["python", "-m", "chainlit", "run", "app.py", "--host", "0.0.0.0", "--port", "8000"]
