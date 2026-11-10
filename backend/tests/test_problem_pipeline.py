from app.services.problem_explanation import build_explanation
from app.services.problem_input import ProblemInputError, extract_problem_text


def test_text_problem_creates_five_explanation_scenes():
    result = build_explanation("小明有 12 个苹果，平均分给 3 个同学，每人几个？", "text")
    assert result.source_type == "text"
    assert len(result.scenes) == 5
    assert result.scenes[0].title == "题目呈现"
    assert result.scenes[-1].visual == "check"


def test_txt_file_is_decoded():
    text, source_type = extract_problem_text("question.txt", "text/plain", "1+1=?".encode())
    assert text == "1+1=?"
    assert source_type == "txt"


def test_unsupported_file_is_rejected():
    try:
        extract_problem_text("question.exe", "application/octet-stream", b"data")
    except ProblemInputError as exc:
        assert "仅支持" in str(exc)
    else:
        raise AssertionError("unsupported file should be rejected")
