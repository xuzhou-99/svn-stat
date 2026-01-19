# 第一阶段：构建阶段
FROM python:3.10-alpine AS builder

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 安装系统依赖
RUN apk add --no-cache \
    subversion \
    curl \
    bash

# 设置工作目录
WORKDIR /app/server-python

# 复制requirements.txt
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 第二阶段：运行阶段
FROM python:3.10-alpine

# 设置环境变量
ENV FLASK_APP=app.py \
    FLASK_RUN_HOST=0.0.0.0 \
    FLASK_RUN_PORT=5000 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 安装SVN客户端
RUN apk add --no-cache \
    subversion

# 设置工作目录
WORKDIR /app/server-python

# 从构建阶段复制依赖和应用代码
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin/gunicorn /usr/local/bin/gunicorn

# 复制应用代码（排除不必要的文件，通过.dockerignore实现）
COPY . .

# 创建必要的目录
RUN mkdir -p /app/server-python/cache /app/server-python/logs 

# 添加配置文件说明
LABEL description="SVN代码统计工具，支持通过config.yml配置SVN URL"

# 暴露端口
EXPOSE 5000

# 添加健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:5000 || exit 1

# 启动应用（使用gunicorn生产服务器，gevent异步worker）
CMD ["gunicorn", "-w", "1", "-k", "gevent", "-b", "0.0.0.0:5000", "--timeout", "300", "app:app"]