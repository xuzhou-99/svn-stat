# SVN代码统计工具

一个SVN代码统计工具，用于分析SVN提交记录，生成可视化的统计报告。

## 功能特性

- 📊 **统计概览**：展示总提交次数、修改文件数、新增/删除代码行数
- 📅 **月度统计**：按月份统计提交情况，支持切换修改文件数和代码行数
- 📈 **每日统计**：按天统计提交情况，支持切换修改文件数和代码行数
- 🌿 **分支统计**：分析不同分支的提交情况
- 👥 **作者统计**：统计不同作者的贡献情况
- ⚙️ **配置管理**：支持保存和管理多个SVN配置
- 📝 **快捷日期**：提供今日、本周、本月、最近30天、本年等快捷日期选择
- 🐳 **Docker支持**：支持Docker部署，方便迁移和扩展

## 技术栈

- **后端**：Python、Flask / Go + Gin / 其他语言（根据需求）
- **前端**：HTML、CSS、JavaScript
- **图表库**：Chart.js
- **容器化**：Docker

## 服务端架构对比

### Server-Go

**技术栈**：
- **语言**：Go 1.21+
- **框架**：Gin
- **特点**：
  - 编译为单一二进制文件
  - 镜像大小：~20-30MB
  - 启动速度快
  - 并发性能好
  - 类型安全

**项目结构**：
```
svn-stat/server-go/
├── main.go              # 主程序入口
├── go.mod               # Go 模块定义
├── go.sum               # 依赖锁定文件
├── config/              # 配置管理
│   └── config.go
├── cache/               # 缓存管理
│   └── cache.go
├── svn/                 # SVN 操作
│   ├── svn.go
├── stats/               # 统计分析
│   └── stats.go
├── api/                 # REST API
│   └── api.go
├── .dockerignore
├── Dockerfile.go        # Go 版本的 Dockerfile
└── go.sum
```

**Dockerfile 特点**：
```dockerfile
# 第一阶段：构建阶段
FROM golang:1.21-alpine AS builder
RUN CGO_ENABLED=0 GOOS=linux go build -o svn-stat .

# 第二阶段：运行阶段
FROM alpine:latest
COPY --from=builder /app/svn-stat .
CMD ["./svn-stat"]
```

**优点**：
- ✅ 镜像大小减少 70-80%（~20-30MB）
- ✅ 单文件部署，无需运行时
- ✅ 编译时类型检查，减少运行时错误
- ✅ 更好的并发性能
- ✅ 更快的启动速度

**缺点**：
- ❌ 需要重新编译才能修改代码
- ❌ 开发调试相对复杂

### 快速开始（Server-Go）

#### 环境要求

- Go 1.21+
- SVN客户端
- Git（可选，用于版本控制）

#### 安装依赖

```bash
# 安装 Gin 框架
go get github.com/gin-gonic/gin

# 安装其他依赖
go mod tidy
```

#### 启动应用

```bash
# 开发模式
cd server-go
go run main.go

# 访问地址
# http://localhost:5000
```


### Server-Python

**技术栈**：
- **语言**：Python 3.10+
- **框架**：Flask
- **特点**：
  - 解释型语言
  - 镜像大小：~80-100MB
  - 开发调试方便
  - 生态丰富

**项目结构**：
```
svn-stat/server-python/
├── app.py               # 主应用程序
├── requirements.txt      # Python 依赖
├── .dockerignore
└── Dockerfile           # Python 版本的 Dockerfile
```

**Dockerfile 特点**：
```dockerfile
# 第一阶段：构建阶段
FROM python:3.10-alpine AS builder
RUN pip install --no-cache-dir -r requirements.txt

# 第二阶段：运行阶段
FROM python:3.10-alpine
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
CMD ["gunicorn", "-w", "1", "-k", "gevent", "-b", "0.0.0.0:5000", "--timeout", "300", "app:app"]
```

**优点**：
- ✅ 开发调试方便
- ✅ 生态丰富，第三方库多
- ✅ 修改代码后立即生效
- ✅ 学习曲线平缓

**缺点**：
- ❌ 镜像大小较大（~80-100MB）
- ❌ 启动速度相对较慢
- ❌ 运行时类型错误
- ❌ 需要运行时环境


### 快速开始（Server-Python）

#### 环境要求

- Python 3.8+
- SVN客户端
- Git（可选，用于版本控制）

#### 安装依赖

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境（Linux/Mac）
source venv/bin/activate

# 激活虚拟环境（Windows）
venv\Scripts\activate

# 安装依赖
pip install flask
```

#### 启动应用

```bash
# 开发模式
cd server-python
python app.py

# 访问地址
# http://localhost:5000
```


### Server-Node（计划中）

**技术栈**（计划）：
- **语言**：Node.js 18+
- **框架**：Express.js
- **特点**：
  - 前后端统一技术栈
  - 镜像大小：~50-80MB
  - 异步非阻塞 I/O
  - 生态丰富

**项目结构**（计划）：
```
svn-stat/server-node/
├── server.js            # 主程序入口
├── package.json         # Node.js 依赖
├── config/             # 配置管理
│   └── config.js
├── cache/              # 缓存管理
│   └── cache.js
├── svn/                # SVN 操作
│   ├── svn.js
│   └── diff.js
├── stats/              # 统计分析
│   └── stats.js
├── api/                # REST API
│   └── api.js
├── .dockerignore
└── Dockerfile.node     # Node.js 版本的 Dockerfile
```

**Dockerfile 特点**（计划）：
```dockerfile
# 第一阶段：构建阶段
FROM node:18-alpine AS builder
WORKDIR /app/server-node
RUN npm ci --only=production

# 第二阶段：运行阶段
FROM node:18-alpine
WORKDIR /app/server-node
COPY --from=builder /app/server-node/node_modules ./node_modules
CMD ["node", "server.js"]
```

**优点**（预期）：
- ✅ 前后端统一技术栈（JavaScript）
- ✅ 异步非阻塞 I/O，适合 SVN 命令调用
- ✅ 生态丰富，第三方库多
- ✅ 开发调试方便

**缺点**（预期）：
- ❌ 镜像大小介于 Python 和 Go 之间
- ❌ 单线程事件循环，CPU 密集型任务性能一般
- ❌ 运行时类型错误

### 快速开始（Server-Node）

#### 环境要求

- Node.js 18+
- SVN客户端
- Git（可选，用于版本控制）

#### 安装依赖

```bash
# 安装 Express.js 和其他依赖
npm install express axios svn-diff-parser
```

#### 启动应用

```bash
# 开发模式
node server.js

# 访问地址
# http://localhost:5000
```



## Docker部署

### 1. 构建镜像

```bash
# 构建Python镜像
#cd svn-stat/server-python
# 构建Go镜像
#cd svn-stat/server-go 

# 使用默认Dockerfile构建
docker build -t svn-stat .

# 使用国内镜像源构建（解决网络问题）
docker build --no-cache -t svn-stat .
```

### 2. 运行容器

#### 基本运行
```bash
docker run -d -p 5000:5000 svn-stat
```

#### 挂载数据卷和配置文件（推荐）
```bash
docker run -d -p 5000:5000 \
  -v ./cache:/app/cache \
  -v ./logs:/app/logs \
  -v ./config.yml:/app/config.yml \
  svn-stat
```

#### 自定义配置文件
```bash
# 使用自定义配置文件
docker run -d -p 5000:5000 \
  -v ./custom-config.yml:/app/config.yml \
  svn-stat
```

#### 自定义环境变量
```bash
docker run -d -p 5000:5000 \
  -e FLASK_RUN_PORT=8080 \
  svn-stat
```

### 3. 镜像导出导入

#### 导出镜像

```bash
# 导出为tar文件
docker save -o svn-stat.tar svn-stat:latest

# 压缩导出
docker save svn-stat:latest | gzip > svn-stat.tar.gz
```

#### 传输镜像

```bash
# 使用SCP传输到目标服务器
scp svn-stat.tar username@target-server:/path/to/destination/
```

#### 导入镜像

```bash
# 导入tar文件
docker load -i /path/to/destination/svn-stat.tar

# 导入压缩文件
gunzip -c svn-stat.tar.gz | docker load
```

### 4. 构建注意事项

#### Docker构建错误修复

如果遇到以下错误：
```
cannot mount volume over existing file, file exists /var/lib/docker/overlay2/.../merged/app/config.yml
```

**解决方案**：这是因为Dockerfile中移除了`VOLUME`指令，您可以直接在运行时挂载配置文件，无需在Dockerfile中定义VOLUME。

#### 本地配置文件

- 确保`config.yml`文件存在于项目根目录
- 可以根据需要修改配置项，如`svn_base_url`
- Docker运行时会优先使用挂载的配置文件

### 4. Docker Compose

创建`docker-compose.yml`文件：

```yaml
version: '3'
services:
  svn-stat:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./cache:/app/cache
      - ./logs:/app/logs
      - ./config.yml:/app/config.yml
    restart: always
    environment:
      - FLASK_RUN_HOST=0.0.0.0
      - FLASK_RUN_PORT=5000
```

启动服务：

```bash
docker-compose up -d
```

## 项目结构

```
svn-stat/
├── app.py              # 主应用程序
├── templates/          # HTML模板
│   └── index.html      # 主页面
├── cache/              # 缓存目录
│   └── svn_cache.json      # SVN缓存文件
├── logs/               # 日志目录
├── Dockerfile          # Docker构建文件
└── README.md           # 项目说明文档
```

## 配置说明

### 配置文件

应用使用`config.yml`文件进行配置，支持在Docker部署时挂载自定义配置文件：

```yaml
# SVN基础URL
svn_base_url: http://svn.my.com/project/iorder-saas

# 默认分支
default_branch: trunk

# 调试模式
debug: false

# svn 用户名密码
svn_username: myusername
svn_password: mypassword

# 日志分析默认查询范围（天）
log_range_days: 180
```

### Docker部署时自定义配置

```bash
# 方式1：挂载自定义配置文件
docker run -d -p 5000:5000 \
  -v ./custom-config.yml:/app/config.yml \
  svn-stat

# 方式2：使用默认配置
# 如果没有挂载配置文件，应用将使用默认配置
```

### 主要配置项

- **svn_base_url**：SVN服务器基础URL
- **default_branch**：默认分支名称
- **debug**：是否启用调试模式
- **svn_username**：SVN用户名
- **svn_password**：SVN密码
- **log_range_days**：日志分析默认查询范围（天）

### 其他配置

- **日期范围**：支持手动选择日期范围或使用快捷日期按钮
- **筛选条件**：支持按作者、分支进行筛选

### 快捷日期按钮

- **今日**：统计今天的提交情况
- **本周**：统计本周的提交情况
- **本月**：统计本月的提交情况
- **最近30天**：统计最近30天的提交情况
- **本年**：统计本年的提交情况

## 注意事项

1. **首次运行**：首次运行时需要获取全量SVN日志，耗时较长
2. **SVN权限**：确保提供的SVN用户名和密码有足够的权限
3. **网络连接**：确保应用能够访问目标SVN服务器
4. **存储空间**：定期清理日志和缓存文件，避免占用过多磁盘空间
5. **性能优化**：建议将`svn_cache.json`挂载到本地，避免每次重建容器都重新获取日志

## 故障排除

### 1. SVN命令执行失败

- 检查SVN客户端是否正确安装
- 检查SVN服务器访问权限，确保提供的用户名和密码有效
- 检查网络连接，确保能够访问SVN服务器

### 2. Docker构建失败

- 检查网络连接，确保能够访问Docker镜像源
- 尝试使用国内镜像源，修改Dockerfile中的FROM指令
- 检查Dockerfile语法是否正确

### 3. 应用无法访问

- 检查容器是否正在运行：`docker ps`
- 检查端口映射是否正确：`docker port svn-stat 5000`
- 检查防火墙设置，确保端口已开放：`ufw allow 5000`

### 4. 图表无法显示

- 检查浏览器控制台是否有JavaScript错误
- 检查分析数据是否正常生成
- 尝试刷新页面或重新启动应用

## 联系方式

如有问题或建议，欢迎提交Issue或Pull Request。

---

**最后更新时间**：2026-01-19