# EduMotion AI

把题目内容或题目文件转化为逐步讲解分镜，并进一步生成动画讲解视频。

## 当前核心流程 MVP

1. 粘贴题目文字，或上传 TXT、可复制文字的 PDF、PNG、JPG、WEBP。
2. 后端提取题目文本（PDF 使用文本层解析；图片使用 Tesseract OCR）。
3. 生成结构化讲解分镜，包含读题、拆解条件、逐步思考、结论和检查。
4. 前端展示识别结果与分镜预览。

> 当前实现已打通题目导入和分镜预览。讲解策略暂时是 deterministic storyboard adapter，不会假装已经完成数学求解；真正的 LLM 解题、Manim/FFmpeg 动画、TTS 配音和 MP4 导出仍是后续核心开发项。

## Run locally

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

图片 OCR 还需要安装系统级 Tesseract，并安装简体中文语言包（chi_sim）。如果暂时没有安装，文字输入和文本型 PDF 仍可使用。

### Frontend

```bash
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173。可通过 `VITE_API_BASE_URL` 配置后端地址。

## API

- `GET /api/v1/health` — health check
- `POST /api/v1/problems/explain` — multipart/form-data，字段 `text`（可选）和 `file`（可选）
- `POST /api/v1/lessons/generate` — 旧版课程 demo API，暂时保留，不作为产品主流程

上传文件最大 15 MB。PDF 目前支持可复制文字的 PDF；扫描 PDF OCR 尚未接入。

## Repository layout

- `backend/` — FastAPI API、题目解析、讲解分镜服务和测试
- `frontend/` — Vue 3 题目导入和分镜工作台
- `shared/lesson-ir/` — 旧版课程 IR 示例（非当前主流程）
- `infra/` — PostgreSQL / Redis 本地基础设施
