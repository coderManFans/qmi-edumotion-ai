from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_generate_math_lesson_returns_lesson_ir() -> None:
    response = client.post(
        "/api/v1/lessons/generate",
        json={"subject": "mathematics", "topic": "认识分数", "grade_level": 4},
    )
    assert response.status_code == 200
    lesson = response.json()
    assert lesson["schema_version"] == "1.0.0"
    assert lesson["subject"] == "mathematics"
    assert len(lesson["scenes"]) == 3
    assert lesson["scenes"][0]["blocks"][1]["content"] == r"\frac{1}{4}"


def test_generate_chinese_story() -> None:
    response = client.post(
        "/api/v1/lessons/generate",
        json={"subject": "chinese", "topic": "春天的校园", "grade_level": 3},
    )
    assert response.status_code == 200
    lesson = response.json()
    assert lesson["subject"] == "chinese"
    assert lesson["scenes"][0]["type"] == "story"
    assert len(lesson["scenes"][0]["blocks"]) == 3


def test_generate_lesson_validates_grade_level() -> None:
    response = client.post(
        "/api/v1/lessons/generate",
        json={"subject": "mathematics", "topic": "认识分数", "grade_level": 0},
    )
    assert response.status_code == 422
