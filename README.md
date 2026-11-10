# EduMotion AI

把题目文字、图片或 PDF 转成可播放的动画讲解视频。

## 当前核心流程

1. 粘贴题目，或上传 TXT、可复制文字的 PDF、PNG、JPG、WEBP。
2. 提取题目文本（PDF 文本层解析；图片通过 Tesseract OCR）。
3. 解题：配置 OpenAI-compatible Chat Completions 服务时调用 LLM；未配置时使用受限的基础数量关系规则，无法可靠判断就明确标记未验证。
4. 生成讲解分镜，Pillow 绘制动态帧，FFmpeg 编码为 MP4。
5. 在页面内播放或下载视频。

当前视频为 1280×720 的程序化讲解卡片动画，含逐镜头内容和进度动效。**本版尚未接入 TTS，MP4 暂无语音旁白；当前同步生成，暂未加入持久化任务队列。**

## 本地运行

### 1. 系统依赖

需要安装 FFmpeg。图片 OCR 需要 Tesseract 和简体中文语言包（chi_sim）。中文视频画面必须安装 Noto CJK 字体；仓库提供的后端 Dockerfile 已包含该字体。

### 2. 后端

```bash
cp .env.example .env
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

如果要使用真实 LLM 解题，在根目录 `.env` 配置：

```dotenv
LLM_BASE_URL=https://your-openai-compatible-host/v1
LLM_API_KEY=your-api-key
LLM_MODEL=your-model-name
```

留空时会使用本地规则解题，仅覆盖少量明确的基础数量关系题；不确定的问题不会编造答案。

### 3. 前端

```bash
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173。可通过 `VITE_API_BASE_URL` 配置后端地址。

### 4. Docker 构建后端运行环境

从仓库根目录执行：

```bash
docker build -t edumotion-backend ./backend
docker run --rm -p 8000:8000 -v "$PWD/data:/app/data" --env-file .env edumotion-backend
```

镜像包含 FFmpeg、Noto CJK 和 Tesseract 中文 OCR 运行依赖。

## API

- `POST /api/v1/problems/explain` — 生成讲解分镜预览。
- `POST /api/v1/problems/video` — 生成解题讲解并同步导出 MP4（multipart/form-data: `text` 或 `file`）。
- `GET /api/v1/problems/videos/{job_id}` — 播放/下载生成的 MP4。
- `GET /api/v1/health` — 健康检查。

上传文件最大 15 MB。PDF 目前支持文字型 PDF；扫描版 PDF OCR 尚未接入。MP4 输出目录由 `VIDEO_OUTPUT_DIR` 配置，默认 `./data/renders`。

## 测试

```bash
cd backend
pytest
```

## 设计文档

- [产品需求规格](docs/PRODUCT_SPEC.md)
- [Lesson IR 规范](docs/LESSON_IR_SPEC.md)
- [系统架构](docs/ARCHITECTURE.md)
