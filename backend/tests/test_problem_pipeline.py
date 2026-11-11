from app.ai.problem_solver import SolvedProblem, SolvedStep, _local_solution, _verify_model_answer, to_scenes
from app.services.problem_explanation import build_explanation
from app.services.problem_input import ProblemInputError, extract_problem_text


def test_square_perimeter_single_number_is_solved_and_verified():
    solved = _local_solution("一个正方形周长是16，求边长是多少？")
    assert solved.answer == "4"
    assert solved.verification_status == "verified"
    assert any("周长 = 边长 × 4" in step.explanation for step in solved.steps)
    assert any("16 / 4 = 4" in step.explanation for step in solved.steps)


def test_square_area_is_solved():
    solved = _local_solution("一个正方形边长是4，求面积是多少？")
    assert solved.answer == "16平方单位"
    assert solved.verification_status == "verified"


def test_rectangle_area_is_solved():
    solved = _local_solution("一个长方形长8，宽5，求面积是多少？")
    assert solved.answer == "40平方单位"
    assert solved.verification_status == "verified"


def test_rectangle_area_preserves_metric_units():
    centimeters = _local_solution("一个长方形长8厘米，宽5厘米，求面积是多少？")
    meters = _local_solution("一个长方形长8米，宽5米，求面积是多少？")
    assert centimeters.answer == "40平方厘米"
    assert meters.answer == "40平方米"


def test_rectangle_perimeter_is_solved():
    solved = _local_solution("一个长方形长8，宽5，求周长是多少？")
    assert solved.answer == "26"
    assert solved.verification_status == "verified"


def test_mixed_arithmetic_obeys_operator_precedence():
    solved = _local_solution("计算：25+36÷4")
    assert solved.answer == "34"
    assert solved.verification_status == "verified"


def test_unknown_problem_is_not_given_a_fake_answer():
    solved = _local_solution("小明今年几岁？")
    assert solved.answer is None
    assert solved.verification_status == "unverified"
    assert "不会猜测答案" in solved.explanation


def test_llm_answer_is_verified_only_when_final_arithmetic_matches():
    matching = SolvedProblem(
        answer="4",
        verification_status="verified",
        explanation="divide by four",
        steps=[
            SolvedStep(title="step one", explanation="rearrange", narration="rearrange", visual_text="边长 = 周长 ÷ 4"),
            SolvedStep(title="step two", explanation="calculate", narration="calculate", visual_text="16 / 4 = 4", expression="16 / 4 = 4"),
        ],
    )
    mismatching = matching.model_copy(deep=True)
    mismatching.answer = "5"
    assert _verify_model_answer(matching).verification_status == "verified"
    assert _verify_model_answer(mismatching).verification_status == "unverified"


def test_scene_script_contains_real_steps_and_verification():
    solved = _local_solution("一个正方形周长是16，求边长是多少？")
    scenes = to_scenes(solved, "一个正方形周长是16，求边长是多少？")
    assert scenes[0].title == "题目呈现"
    assert any("16 / 4 = 4" in scene.visual_text for scene in scenes)
    assert scenes[-1].visual_text == "答案：4｜验证通过"
    assert "已经通过计算验证" in scenes[-1].narration


def test_text_problem_preview_exposes_solution_and_verification():
    result = build_explanation("一个正方形周长是16，求边长是多少？", "text")
    assert result.answer == "4"
    assert result.verification_status == "verified"
    assert len(result.scenes) == 6


def test_average_distribution_is_solved():
    result = build_explanation("小明有 12 个苹果，平均分给 3 个同学，每人几个？", "text")
    assert result.answer == "4"
    assert result.verification_status == "verified"


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

def test_default_local_fallback_solves_chinese_rectangle_problem_without_llm(monkeypatch):
    import asyncio
    from app.ai.problem_solver import solve_problem
    from app.core import config

    monkeypatch.setattr(config.settings, "llm_base_url", "")
    monkeypatch.setattr(config.settings, "llm_api_key", "")
    monkeypatch.setattr(config.settings, "llm_model", "")

    solved = asyncio.run(solve_problem("一个长方形长 8 厘米、宽 5 厘米，面积是多少？"))

    assert solved.answer == "40平方厘米"
    assert solved.verification_status == "verified"
    assert any("8 * 5 = 40" in step.explanation for step in solved.steps)
