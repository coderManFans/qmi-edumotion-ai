# Backend

FastAPI service. Python 3.11+ recommended.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Health check: `GET http://localhost:8000/api/v1/health`; API docs: `http://localhost:8000/docs`.
