# EduMotion AI 本地启动指南

本文说明关机、重启电脑后，如何重新启动 EduMotion AI。项目由三个运行部分组成：

- **API 后端**：FastAPI，地址 `http://localhost:8000`
- **异步任务 Worker**：Celery，负责生成讲解音频和 MP4
- **Redis**：保存任务队列和任务结果
- **前端**：Vue + Vite，地址 `http://localhost:5173`

> 注意：仅启动前端和 API 不够。要生成视频，Redis 和 Celery Worker 也必须运行。

## 一、准备工作（首次运行）

### 必备软件

- Git
- Python 3.12（建议）
- Node.js（建议使用当前 LTS 版本，含 npm）
- Docker Desktop（如果使用 Docker 方式）

非 Docker 方式还需要本机安装 FFmpeg（含 `ffprobe`）、Tesseract OCR（含简体中文语言包 `chi_sim`）和 Noto CJK 字体。它们分别用于 MP4 合成、图片 OCR 和中文画面文字显示。

克隆仓库后，以下命令均从仓库根目录 `qmi-edumotion-ai/` 开始，除非特别说明：

```bash
git clone https://github.com/coderManFans/qmi-edumotion-ai.git
cd qmi-edumotion-ai
```

复制环境变量模板（只需首次执行）：

**macOS / Linux**
```bash
cp .env.example .env
```

**Windows PowerShell**
```powershell
Copy-Item .env.example .env
```

默认可以不配置 LLM，项目会使用本地规则处理有限的题型；需要调用 OpenAI-compatible 模型时，再填写根目录 `.env` 中的 `LLM_BASE_URL`、`LLM_API_KEY` 和 `LLM_MODEL`。不要把真实 API Key 提交到 Git。

## 二、Docker 方式（推荐，最省事）

### 1. 启动 Docker Desktop

确认 Docker Desktop 已启动，并且终端中的以下命令能正常执行：

```bash
docker --version
docker compose version
```

### 2. 启动 Redis、API 和 Worker

在仓库根目录执行：

```bash
docker compose -f backend/docker-compose.yml up --build -d
```

首次运行会构建后端镜像并下载 Redis 镜像，可能需要几分钟。该 Compose 文件会启动：

| 服务 | 说明 | 地址 |
|---|---|---|
| redis | 任务队列和结果存储 | 容器内部 6379 |
| api | FastAPI 后端 | http://localhost:8000 |
| worker | Celery 视频生成任务 | 后台容器 |

### 3. 启动前端

当前 Compose 文件**不包含前端服务**，所以前端需要在宿主机单独启动。打开一个新的终端，在仓库根目录执行：

```bash
cd frontend
npm install
npm run dev
```

浏览器访问：

- 前端页面：http://localhost:5173
- API 文档：http://localhost:8000/docs
- API 健康检查：http://localhost:8000/api/v1/health

### 4. 重启电脑后再次启动

电脑重启后，Docker Desktop 启动，再在仓库根目录执行：

```bash
docker compose -f backend/docker-compose.yml up -d
```

然后重新启动前端终端：

```bash
cd frontend
npm run dev
```

如果需要查看服务是否正常：

```bash
docker compose -f backend/docker-compose.yml ps
docker compose -f backend/docker-compose.yml logs -f api worker redis
```

只看某个服务的日志，例如：

```bash
docker compose -f backend/docker-compose.yml logs -f worker
```

停止服务（保留 Redis 数据卷和本地生成的视频）：

```bash
docker compose -f backend/docker-compose.yml down
```

再次启动使用前面的 `up -d` 即可。**不要随意执行 `down -v`**：它会删除 Compose 管理的 Redis 数据卷，任务状态和 Redis 中保存的结果会丢失。生成的视频位于仓库根目录的 `data/renders/`，不会因普通 `down` 被删除。

如果修改了后端依赖或 Dockerfile，重新构建：

```bash
docker compose -f backend/docker-compose.yml up --build -d
```

## 三、非 Docker 方式（本机运行 API 和 Worker）

非 Docker 方式仍然需要 Redis。可以自行安装并启动本机 Redis，也可以只用 Docker 启动一个 Redis 容器；后端 API、Worker 和前端都在本机运行。

### 1. 启动 Redis

如果本机已安装 Redis，先启动 Redis 服务，并确认它监听 `localhost:6379`。

或者使用 Docker 单独启动 Redis：

```bash
docker run -d --name edumotion-redis --restart unless-stopped -p 6379:6379 redis:7-alpine
```

检查：

```bash
docker exec edumotion-redis redis-cli ping
```

应返回 `PONG`。以后重启电脑，如果容器没有自动启动，可以执行：

```bash
docker start edumotion-redis
```

如果提示容器名已存在，不要重复创建，使用 `docker start edumotion-redis` 即可。

### 2. 创建 Python 环境并安装后端依赖（首次运行）

从仓库根目录：

**macOS / Linux**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**Windows PowerShell**
```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

如果 Windows 阻止激活脚本，可在当前 PowerShell 窗口执行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 3. 启动 API

保持当前终端位于 `backend/`，并确认命令行前面显示已激活的 `.venv`：

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

看到 Uvicorn 启动成功后，API 地址为 http://localhost:8000，文档地址为 http://localhost:8000/docs。这个终端不要关闭。

### 4. 启动 Celery Worker

再打开一个新的终端：

**macOS / Linux**
```bash
cd qmi-edumotion-ai/backend
source .venv/bin/activate
celery -A app.celery_app:celery_app worker --loglevel=info
```

**Windows PowerShell**
```powershell
cd qmi-edumotion-ai\backend
.\.venv\Scripts\Activate.ps1
celery -A app.celery_app:celery_app worker --loglevel=info --pool=solo
```

Windows 本地开发建议使用 `--pool=solo`。Worker 终端也必须保持运行；关闭它就无法处理视频生成任务。

### 5. 启动前端

再打开一个终端，从仓库根目录执行：

```bash
cd frontend
npm install
npm run dev
```

如果依赖之前已经安装过，通常只需执行 `npm run dev`。打开 http://localhost:5173。

## 四、每次重启电脑后，最短启动清单

### Docker 方式

1. 启动 Docker Desktop。
2. 仓库根目录运行：`docker compose -f backend/docker-compose.yml up -d`。
3. 进入 `frontend/` 运行：`npm run dev`。
4. 打开 http://localhost:5173。

### 非 Docker 方式

需要分别保持三个终端运行：

1. 启动 Redis（如果用 Docker Redis：`docker start edumotion-redis`）。
2. 在 `backend/` 激活虚拟环境，运行 `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`。
3. 另一个终端在 `backend/` 激活虚拟环境，运行 Celery Worker（Windows 加 `--pool=solo`）。
4. 另一个终端在 `frontend/` 运行 `npm run dev`。

## 五、常见问题排查

### 页面能打开，但提交视频后一直排队

通常是 Worker 没启动，或者 Worker 连不上 Redis。检查：

- Docker：`docker compose -f backend/docker-compose.yml ps`，确认 redis、api、worker 都是运行状态；再查看 worker 日志。
- 非 Docker：确认 Redis 在 6379 端口运行，并且 Celery Worker 的终端没有报错。

### API 无法连接 Redis

确认 Redis 已启动。非 Docker 模式下，根目录 `.env` 默认使用：

```env
REDIS_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

Docker Compose 会自动把容器内的 Redis 地址覆盖为 `redis://redis:6379/0` 和 `redis://redis:6379/1`，不要把 Docker 环境变量改成 localhost。

### 端口被占用

默认端口：前端 5173、API 8000、Redis 6379。若提示端口占用，先检查是否已有旧进程或容器在运行，不要盲目启动多个相同服务。

### 图片 OCR 不工作或中文显示异常（非 Docker）

确认 Tesseract 已安装 `chi_sim` 语言包、FFmpeg/ffprobe 在 PATH 中，并安装 Noto CJK 字体。Docker 后端镜像已安装这些系统依赖。

### Edge TTS 生成语音失败

默认使用 Edge TTS 在线服务，Worker 所在环境必须能访问互联网。可查看 Worker 日志确认错误；`TTS_PROVIDER=none` 可以用于排查视频管线（会生成无配音视频）。

### 前端访问不到后端

前端默认 API 地址是 `http://localhost:8000`。如需修改，在 `frontend/.env` 中设置：

```env
VITE_API_BASE_URL=http://localhost:8000
```

修改 Vite 环境变量后，需要重启前端开发服务器。

## 六、数据和配置说明

- 根目录 `.env`：后端和 Docker Compose 使用的环境配置，不要提交密钥。
- `backend/.venv/`：本机 Python 虚拟环境。
- `frontend/node_modules/`：前端依赖。
- `data/renders/`：生成的 MP4 文件。
- Docker 的 `redis_data` 命名卷：Redis 数据。

更多项目说明见仓库根目录的 [README.md](../README.md)。
