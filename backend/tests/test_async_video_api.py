import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api import routes
from app.main import app
from app.schemas.problem import ExplanationScene, ProblemExplanationResponse

client = TestClient(app)

QUESTION = "一个长方形长 8 厘米、宽 5 厘米，面积是多少？"


def test_video_submission_enqueues_job_and_returns_202(monkeypatch):
    captured = {}

    def fake_apply_async(*, args, task_id):
        captured["args"] = args
        captured["task_id"] = task_id

    monkeypatch.setattr(routes.generate_problem_video_task, "apply_async", fake_apply_async)

    response = client.post("/api/v1/problems/video", data={"text": QUESTION})

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["progress"] == 0
    assert uuid.UUID(payload["job_id"])
    assert captured == {
        "args": [payload["job_id"], QUESTION, "text"],
        "task_id": payload["job_id"],
    }


def test_video_submission_reports_queue_unavailable(monkeypatch):
    def fail_to_enqueue(*, args, task_id):
        raise ConnectionError("Redis unavailable")

    monkeypatch.setattr(routes.generate_problem_video_task, "apply_async", fail_to_enqueue)

    response = client.post("/api/v1/problems/video", data={"text": QUESTION})

    assert response.status_code == 503
    assert "任务队列暂不可用" in response.json()["detail"]


@pytest.mark.parametrize(
    ("state", "info", "expected_status", "expected_progress"),
    [
        ("PENDING", None, "queued", 0),
        ("STARTED", None, "processing", 5),
        ("PROGRESS", {"progress": 60, "stage": "正在合成中文语音"}, "processing", 60),
        ("FAILURE", RuntimeError("Edge TTS network unavailable"), "failed", 0),
    ],
)
def test_job_status_maps_celery_states(monkeypatch, state, info, expected_status, expected_progress):
    job_id = str(uuid.uuid4())
    fake_result = SimpleNamespace(state=state, info=info, result=None)
    monkeypatch.setattr(routes, "AsyncResult", lambda task_id, app: fake_result)

    response = client.get(f"/api/v1/problems/jobs/{job_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == expected_status
    assert payload["progress"] == expected_progress
    if state == "PROGRESS":
        assert payload["stage"] == "正在合成中文语音"
    if state == "FAILURE":
        assert "Edge TTS network unavailable" in payload["error"]


def test_completed_job_returns_result_and_video_url(monkeypatch):
    job_id = str(uuid.uuid4())
    result = ProblemExplanationResponse(
        job_id=job_id,
        source_type="text",
        extracted_text=QUESTION,
        problem_title=QUESTION,
        explanation="长方形面积等于长乘宽。",
        answer="40平方单位",
        verification_status="verified",
        scenes=[
            ExplanationScene(
                id="scene-0",
                title="题目呈现",
                narration="先读题。",
                visual="question",
                visual_text=QUESTION,
            )
        ],
        video_status="completed",
        audio_status="completed",
        video_url=f"/api/v1/problems/videos/{job_id}",
    ).model_dump(mode="json")
    fake_result = SimpleNamespace(state="SUCCESS", info=result, result=result)
    monkeypatch.setattr(routes, "AsyncResult", lambda task_id, app: fake_result)

    response = client.get(f"/api/v1/problems/jobs/{job_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["progress"] == 100
    assert payload["result"]["answer"] == "40平方单位"
    assert payload["video_url"] == f"/api/v1/problems/videos/{job_id}"


def test_video_endpoint_serves_mp4_file(monkeypatch, tmp_path):
    job_id = str(uuid.uuid4())
    video_path = tmp_path / f"{job_id}.mp4"
    video_path.write_bytes(b"test-mp4-content")
    monkeypatch.setattr(routes.settings, "video_output_dir", str(tmp_path))

    response = client.get(f"/api/v1/problems/videos/{job_id}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("video/mp4")
    assert response.content == b"test-mp4-content"
