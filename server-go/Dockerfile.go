# 第一阶段：构建阶段
FROM golang:1.21-alpine AS builder

# 设置工作目录
WORKDIR /app/server-go

# 复制 go.mod 和 go.sum
COPY go.mod go.sum* ./

# 下载依赖
RUN go mod download

# 复制源代码
COPY . .

# 编译应用
RUN CGO_ENABLED=0 GOOS=linux go build -o svn-stat .

# 第二阶段：运行阶段
FROM alpine:latest

# 安装SVN客户端和curl
RUN apk add --no-cache \
    subversion \
    ca-certificates

# 设置工作目录
WORKDIR /app/server-go

# 从构建阶段复制编译好的二进制文件
COPY --from=builder /app/server-go/svn-stat .

# 复制静态文件和模板
COPY --from=builder /app/server-go/templates ./templates
COPY --from=builder /app/server-go/static ./static

# 创建必要的目录
RUN mkdir -p /app/server-go/cache /app/server-go/logs

# 添加配置文件说明
LABEL description="SVN代码统计工具，支持通过config.yml配置SVN URL (Go版本)"

# 暴露端口
EXPOSE 5000

# 添加健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:5000 || exit 1

# 启动应用
CMD ["./svn-stat"]
