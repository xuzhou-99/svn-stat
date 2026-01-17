# SVN代码统计工具

一个基于Flask的SVN代码统计工具，用于分析SVN提交记录，生成可视化的统计报告。

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

- **后端**：Python Flask
- **前端**：HTML、CSS、JavaScript
- **图表库**：Chart.js
- **容器化**：Docker

## 快速开始

### 环境要求

- Python 3.8+
- SVN客户端
- Git（可选，用于版本控制）

### 安装依赖

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

### 启动应用

```bash
# 开发模式
python app.py

# 访问地址
# http://localhost:5000
```

## Docker部署

### 1. 构建镜像

```bash
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
  -v ./svn_cache.json:/app/svn_cache.json \
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
      - ./svn_cache.json:/app/svn_cache.json
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
├── svn_stats.py        # SVN统计核心功能
├── templates/          # HTML模板
│   └── index.html      # 主页面
├── cache/              # 缓存目录
├── logs/               # 日志目录
├── svn_cache.json      # SVN缓存文件
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

# 缓存过期天数
cache_expire_days: 7
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
- **cache_expire_days**：缓存过期天数

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
- 检查SVN服务器访问权限
- 检查网络连接

### 2. Docker构建失败

- 检查网络连接，确保能够访问Docker镜像源
- 尝试使用国内镜像源，修改Dockerfile中的FROM指令
- 检查Dockerfile语法是否正确

### 3. 应用无法访问

- 检查容器是否正在运行：`docker ps`
- 检查端口映射是否正确
- 检查防火墙设置，确保端口已开放

### 4. 图表无法显示

- 检查浏览器控制台是否有JavaScript错误
- 检查分析数据是否正常生成
- 尝试刷新页面或重新启动应用

## 联系方式

如有问题或建议，欢迎提交Issue或Pull Request。

---

**最后更新时间**：2026-01-17