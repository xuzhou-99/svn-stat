# 第一阶段：构建阶段
FROM python:3.10-slim AS builder

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 安装系统依赖
RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
    subversion \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制requirements.txt
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 第二阶段：运行阶段
FROM python:3.10-slim

# 设置环境变量
ENV FLASK_APP=app.py \
    FLASK_RUN_HOST=0.0.0.0 \
    FLASK_RUN_PORT=5000 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 安装SVN客户端
RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
    subversion \
    && rm -rf /var/lib/apt/lists/*

# 创建非root用户
RUN useradd -m -u 1000 appuser

# 设置工作目录
WORKDIR /app

# 从构建阶段复制依赖和应用代码
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin/gunicorn /usr/local/bin/gunicorn

# 复制应用代码（排除不必要的文件，通过.dockerignore实现）
COPY --chown=appuser:appuser . /app

# 创建必要的目录并设置权限
RUN mkdir -p /app/cache /app/logs \
    && chown -R appuser:appuser /app

# 添加配置文件说明
LABEL description="SVN代码统计工具，支持通过config.yml配置SVN URL"

# 切换到非root用户
USER appuser

# 暴露端口
EXPOSE 5000

# 添加健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:5000 || exit 1

# 启动应用（使用gunicorn生产服务器）
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]