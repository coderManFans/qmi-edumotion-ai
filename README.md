# EduMotion AI

把题目文字、图片或 PDF 转成带中文旁白的动画讲解视频。

## 当前核心流程

1. 粘贴题目，或上传 TXT、可复制文字的 PDF、PNG、JPG、WEBP。
2. 提取题目文本（PDF 文本层解析；图片通过 Tesseract OCR）。
3. 解题：配置 OpenAI-compatible Chat Completions 服务时调用 LLM；未配置时使用受限的基础数量关系规则，无法可靠判断就明确标记未验证。
4. Celery Worker 生成讲解分镜，Edge TTS 为每个镜头合成中文旁白。
5. Pillow 按每段语音的实际时长绘制动画帧，FFmpeg 合成为带 AAC 音轨的 MP4。
6. 前端轮询任务状态，在页面内播放或下载视频。

## 中文语音

默认使用 Edge TTS 的普通话神经语音 zh-CN-XiaoxiaoNeural，无需额外 API Key，但 Worker 需要能够访问互联网。可以通过 TTS_VOICE 更换 Edge TTS 支持的中文音色，通过 TTS_RATE 调整语速。该服务依赖外部语音服务可用性；若部署环境无法访问外网，任务会失败并在任务状态接口返回错误。可将 TTS provider adapter 替换为自托管语音服务。

设置 TTS_PROVIDER=none 可关闭配音并生成静音视频。

## 本地运行

### 1. 系统依赖

需要安装 FFmpeg（包含 ffprobe）。图片 OCR 需要 Tesseract 和简体中文语言包（chi_sim）。中文视频画面必须安装 Noto CJK 字体；仓库提供的后端 Dockerfile 已包含这些系统依赖。

### 2. 启动 Redis

    docker run --rm -p 6379:6379 redis:7-alpine

### 3. 后端 API 和 Worker

    cp .env.example .env
    cd backend
    python -m venv .venv
    source .venv/bin/activate  # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    uvicorn app.main:app --reload

另开一个终端，在 backend 目录启动 Worker：

    celery -A app.celery_app:celery_app worker --loglevel=info

### 4. 前端

    cd frontend
    npm install
    npm run dev

打开 http://localhost:5173。可通过 VITE_API_BASE_URL 配置后端地址。

### Docker Compose

从仓库根目录执行：

    cp .env.example .env
    docker compose -f backend/docker-compose.yml up --build

Compose 会启动 Redis、API 和 Celery Worker。API 暴露在 http://localhost:8000，Swagger 文档在 http://localhost:8000/docs。视频目录挂载到宿主机 data/renders。

## LLM 配置

如需使用真实模型解题，在根目录 .env 配置：

    LLM_BASE_URL=https://your-openai-compatible-host/v1
    LLM_API_KEY=your-api-key
    LLM_MODEL=your-model-name

留空时会使用本地规则解题，仅覆盖少量明确的基础数量关系题；不确定的问题不会编造答案。

## API

- POST /api/v1/problems/explain — 生成讲解分镜预览。
- POST /api/v1/problems/video — 提交后台视频任务，返回 HTTP 202 和 job_id（multipart/form-data: text 或 file）。
- GET /api/v1/problems/jobs/{job_id} — 查询排队、执行进度、成功结果或错误。
- GET /api/v1/problems/videos/{job_id} — 播放/下载生成的 MP4。
- GET /api/v1/health — API 健康检查。

任务状态和结果由 Redis 保存，默认保留 7 天。生产部署时应使用持久化 Redis，并为 Worker 配置合理并发与资源限制。上传文件最大 15 MB。PDF 目前支持文字型 PDF；扫描版 PDF OCR 尚未接入。

## 测试

    cd backend
    pytest

## 设计文档

- [产品需求规格](docs/PRODUCT_SPEC.md)
- [Lesson IR 规范](docs/LESSON_IR_SPEC.md)
- [系统架构](docs/ARCHITECTURE.md)
