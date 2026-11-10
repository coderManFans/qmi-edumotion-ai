# EduMotion AI

AI-powered teaching content generation for primary and secondary education.

## MVP workflow

1. Choose mathematics or Chinese.
2. Enter a lesson/story topic and grade.
3. Generate a structured Lesson IR document through the API.
4. Preview the lesson as scrollable scenes in the Vue application.

The current generator is a deterministic demo adapter. It provides a runnable end-to-end workflow without requiring an LLM key; a model provider can be added behind the lesson-generation service later.

## Repository layout

- `backend/` — FastAPI application, lesson schemas, subject engines and tests
- `frontend/` — Vue 3 + TypeScript lesson creator and preview
- `shared/lesson-ir/` — JSON Schema and sample lesson documents
- `infra/` — PostgreSQL and Redis local infrastructure
- `scripts/` — developer utilities
- `storage/` — local generated asset storage (ignored by Git)

## Run locally

### 1. Start infrastructure (optional for the current in-memory MVP)

From the repository root:

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml up -d
```

### 2. Start the API

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

### 3. Start the web app

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Set `VITE_API_BASE_URL` if the API is hosted elsewhere.

### 4. Run backend tests

From `backend/`:

```bash
pytest
```

## API

- `GET /api/v1/health` — health check
- `POST /api/v1/lessons/generate` — generate a mathematics or Chinese lesson IR

Example request:

```json
{
  "subject": "mathematics",
  "topic": "认识分数",
  "grade_level": 4
}
```

## Next milestones

- LLM provider adapter and content moderation
- Persistent lesson history and versioning
- Rich diagram renderer and interactive quiz interactions
- TTS, Manim/FFmpeg video rendering and asynchronous task status
- Human review workflow and role-based access
