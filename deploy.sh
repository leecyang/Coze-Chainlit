#!/bin/bash

# 灵犀智学 - Docker Compose 部署脚本
# 使用方法: 
#   ./deploy.sh                    # 自动获取 IP
#   ./deploy.sh 47.93.133.55       # 手动指定公网 IP

set -e

echo "🚀 开始部署 灵犀智学..."

# 创建数据目录
mkdir -p data
mkdir -p public

# 注意：数据库文件由 Chainlit 自动管理，不要手动删除
# 历史数据会自动保存在 data/chainlit.db

echo "🗄️  数据目录已准备"

# 检查 Docker 和 Docker Compose
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，请先安装 Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose 未安装，请先安装 Docker Compose"
    exit 1
fi

# 获取服务器 IP 地址
if [ -n "$1" ]; then
    # 使用手动指定的 IP
    SERVER_IP="$1"
    echo "📍 使用手动指定的服务器 IP: $SERVER_IP"
else
    # 自动获取 IP（兼容 CentOS 和其他系统）
    if command -v hostname &> /dev/null && hostname -I &> /dev/null 2>&1; then
        SERVER_IP=$(hostname -I | awk '{print $1}')
    elif command -v ip &> /dev/null; then
        SERVER_IP=$(ip route get 1 | awk '{print $7;exit}')
    elif command -v ifconfig &> /dev/null; then
        SERVER_IP=$(ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*' | grep -v '127.0.0.1' | head -n 1)
    else
        SERVER_IP="localhost"
    fi
    echo "📍 自动获取的服务器 IP: $SERVER_IP"
    echo "⚠️  如果这是内网 IP，请重新运行脚本并指定公网 IP:"
    echo "   ./deploy.sh 47.93.133.55"
fi

# 更新 docker-compose.yml 中的重定向 URL
sed -i "s|COZE_REDIRECT_URL=.*|COZE_REDIRECT_URL=http://$SERVER_IP:8123/oauth/callback|g" docker-compose.yml

echo "🔧 已配置 OAuth 回调地址: http://$SERVER_IP:8123/oauth/callback"

# 构建并启动服务
echo "🏗️  构建 Docker 镜像..."
docker-compose build

echo "🚀 启动服务..."
docker-compose up -d

echo "⏳ 等待服务启动..."
sleep 5

# 检查服务状态
if docker-compose ps | grep -q "Up"; then
    echo "✅ 服务启动成功！"
    echo ""
    echo "🌐 访问地址: http://$SERVER_IP:8123"
    echo "👤 管理员账号: yang"
    echo "🔑 管理员密码: lcy@050426"
    echo ""
    echo "📋 常用命令:"
    echo "  - 查看日志: docker-compose logs -f"
    echo "  - 停止服务: docker-compose down"
    echo "  - 重启服务: docker-compose restart"
    echo ""
    echo "💡 首次使用请通过 /model 和 /config 命令配置 Coze 参数"
    echo ""
    echo "🔐 OAuth 配置信息:"
    echo "  - 回调地址: http://$SERVER_IP:8123/oauth/callback"
    echo "  - 请在 Coze 开发者平台添加此回调地址"
else
    echo "❌ 服务启动失败，请检查日志: docker-compose logs"
    exit 1
fi
