FROM python:3.11-slim

WORKDIR /app

# 安装编译依赖（使用国内源）- 完整替换 sources.list
RUN rm -f /etc/apt/sources.list.d/*.sources && \
    echo "deb http://mirrors.aliyun.com/debian/ bookworm main non-free non-free-firmware" > /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian/ bookworm-updates main non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian-security/ bookworm-security main non-free non-free-firmware" >> /etc/apt/sources.list && \
    apt-get clean && \
    apt-get update && \
    apt-get install -y gcc && \
    rm -rf /var/lib/apt/lists/*

# 使用国内 PyPI 镜像
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# Copy application code
COPY . .

# Create data directory for persistent storage
RUN mkdir -p /app/data

# 初始化数据库
RUN python init_db.py || echo "Database will be initialized at runtime"

# Expose port
EXPOSE 8000

# Run the application
CMD ["sh", "-c", "python init_db.py && chainlit run app.py --host 0.0.0.0 --port 8000"]
