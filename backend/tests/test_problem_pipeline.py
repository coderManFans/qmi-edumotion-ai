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

def test_triangle_area_formula():
    solved = _local_solution("一个三角形底是8厘米，高是5厘米，求面积是多少？")
    assert solved.answer == "20平方单位"
    assert solved.verification_status == "verified"
    assert any("底 × 高 ÷ 2" in step.explanation for step in solved.steps)


def test_parallelogram_area_formula():
    solved = _local_solution("平行四边形底是8厘米，高是5厘米，面积是多少？")
    assert solved.answer == "40平方单位"
    assert solved.verification_status == "verified"


def test_trapezoid_area_formula():
    solved = _local_solution("梯形上底是4厘米，下底是8厘米，高是5厘米，求面积？")
    assert solved.answer == "30平方单位"
    assert solved.verification_status == "verified"


def test_travel_distance_formula():
    solved = _local_solution("汽车速度是每小时60千米，行驶3小时，路程是多少？")
    assert solved.answer == "180千米"
    assert solved.verification_status == "verified"


def test_unit_price_total_formula():
    solved = _local_solution("每支铅笔6元，买了4支，一共多少元？")
    assert solved.answer == "24元"
    assert solved.verification_status == "verified"


def test_circle_area_uses_explicit_radius():
    solved = _local_solution("圆的半径是2厘米，面积是多少？")
    assert solved.answer == "12.56平方单位"
    assert solved.verification_status == "verified"


def test_knowledge_catalog_contains_primary_topics():
    import json
    from pathlib import Path

    catalog_path = Path(__file__).parents[1] / "app" / "knowledge" / "elementary_math.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    topic_ids = {topic["id"] for topic in catalog["problem_families"]}
    assert {"square", "rectangle", "triangle", "trapezoid", "distance_speed_time", "percentage"} <= topic_ids


def test_percentage_of_whole():
    solved = _local_solution("200的20%是多少？")
    assert solved.answer == "40"
    assert solved.verification_status == "verified"

