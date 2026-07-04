#!/bin/bash

set -e

echo "开始部署灵犀智学..."

mkdir -p data public

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker 未安装"
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "Docker Compose v2 未安装"
    exit 1
fi

if [ -n "$1" ]; then
    SERVER_IP="$1"
else
    SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
    SERVER_IP=${SERVER_IP:-localhost}
fi

docker compose -f docker-compose.yml build
docker compose -f docker-compose.yml up -d

echo "访问地址: http://$SERVER_IP:8123"
echo "空数据库首次启动会创建管理员: ${ADMIN_USERNAME:-admin}"
echo "Coze 参数通过环境变量或 /admin 管理后台配置"
