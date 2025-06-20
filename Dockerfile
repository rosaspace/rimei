# 使用官方 Python 基础镜像
FROM python:3.11-slim

# 安装依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libglib2.0-0 \
    libxml2 \
    libxslt1.1 \
    shared-mime-info \
    libpq-dev \
    fonts-liberation \
    fonts-dejavu-core \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝项目文件
COPY . .

# 暴露端口
EXPOSE 8001

# 启动命令
CMD ["python", "manage.py", "runserver", "0.0.0.0:8001"]