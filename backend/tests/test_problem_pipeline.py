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
    assert _verify_model_answer(matching).verification_status == "unverified"
    assert _verify_model_answer(mismatching).verification_status == "unverified"


def test_arithmetic_only_does_not_semantically_verify_a_model_solution():
    plausible_but_wrong = SolvedProblem(
        answer="1",
        verification_status="verified",
        explanation="把边长当成周长后再除以4。",
        steps=[
            SolvedStep(title="条件", explanation="边长是4", narration="边长是4", visual_text="边长=4"),
            SolvedStep(title="计算", explanation="4÷4=1", narration="计算得到1", visual_text="4÷4=1", expression="4 / 4 = 1"),
        ],
    )
    assert _verify_model_answer(plausible_but_wrong).verification_status == "unverified"


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


def test_square_side_from_area_inverse_formula():
    solved = _local_solution("一个正方形面积是64平方厘米，边长是多少？")
    assert solved.answer == "8厘米"
    assert solved.verification_status == "verified"
    assert any("边长 = √面积" in step.explanation for step in solved.steps)


def test_rectangle_width_from_area_inverse_formula():
    solved = _local_solution("一个长方形面积是48平方厘米，长是8厘米，宽是多少？")
    assert solved.answer == "6厘米"
    assert solved.verification_status == "verified"


def test_unit_price_quantity_inverse_formula():
    solved = _local_solution("买文具总价是48元，单价是6元，买了多少支？")
    assert solved.answer == "8支"
    assert solved.verification_status == "verified"


def test_travel_time_inverse_formula():
    solved = _local_solution("路程是180千米，速度是60千米/小时，时间是多少小时？")
    assert solved.answer == "3小时"
    assert solved.verification_status == "verified"


def test_fraction_find_unit_whole():
    solved = _local_solution("一个数的3/5是18，求这个数。")
    assert solved.answer == "30"
    assert solved.verification_status == "verified"


def test_fraction_find_part_from_whole():
    solved = _local_solution("60的3/5是多少？")
    assert solved.answer == "36"
    assert solved.verification_status == "verified"


def test_percentage_find_unit_whole():
    solved = _local_solution("一个数的25%是20，求这个数。")
    assert solved.answer == "80"
    assert solved.verification_status == "verified"


def test_area_unit_conversion_uses_squared_factor():
    solved = _local_solution("2平方米等于多少平方厘米？")
    assert solved.answer == "20000平方厘米"
    assert solved.verification_status == "verified"


def test_volume_unit_conversion_uses_cubed_factor():
    solved = _local_solution("1立方米等于多少立方分米？")
    assert solved.answer == "1000立方分米"
    assert solved.verification_status == "verified"


def test_time_conversion_uses_sixty_not_ten():
    solved = _local_solution("2小时换算成分钟是多少？")
    assert solved.answer == "120分钟"
    assert solved.verification_status == "verified"


def test_incompatible_unit_conversion_is_unverified():
    solved = _local_solution("3米等于多少平方米？")
    assert solved.answer is None
    assert solved.verification_status == "unverified"


def test_rectangle_two_step_perimeter_then_area():
    solved = _local_solution("一个长方形周长是30厘米，长是9厘米，求面积。")
    assert solved.answer == "54平方厘米"
    assert solved.verification_status == "verified"
    assert any(step.title == "先求宽" for step in solved.steps)
    assert any(step.title == "再求面积" for step in solved.steps)


def test_multi_step_equal_groups_then_subtract():
    solved = _local_solution("仓库有3箱矿泉水，每箱12瓶，卖出5瓶，还剩多少瓶？")
    assert solved.answer == "31"
    assert solved.verification_status == "verified"
    assert len(solved.steps) == 4


def test_misleading_keyword_does_not_override_semantic_roles():
    solved = _local_solution("路程是180千米，速度是60千米/小时，不是求路程，求时间。")
    assert solved.answer == "3小时"
    assert solved.verification_status == "verified"


def test_missing_geometry_condition_stays_unverified():
    solved = _local_solution("一个三角形底是8厘米，面积是多少？")
    assert solved.answer is None
    assert solved.verification_status == "unverified"


def test_number_order_is_not_used_for_inverse_travel_problem():
    solved = _local_solution("速度是60千米/小时，路程是180千米，求行驶时间。")
    assert solved.answer == "3小时"
    assert solved.verification_status == "verified"


def test_primary_math_benchmark_has_exactly_50_cases_and_matches_solver():
    import json
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "primary_math_benchmark_v1.json"
    dataset = json.loads(fixture.read_text(encoding="utf-8"))
    assert dataset["count"] == 50
    assert len(dataset["cases"]) == 50
    assert len({case["id"] for case in dataset["cases"]}) == 50

    for case in dataset["cases"]:
        solved = _local_solution(case["problem"])
        assert solved.verification_status == case["verification_status"], case["id"]
        assert solved.answer == case["standard_answer"], case["id"]
        assert len(solved.steps) >= 2, case["id"]
        narration = "\\n".join(step.narration for step in solved.steps)
        teaching_content = "\\n".join(
            f"{step.title} {step.explanation} {step.narration} {step.visual_text}"
            for step in solved.steps
        )
        assert all(step.narration.strip() for step in solved.steps), case["id"]
        if case["verification_status"] == "verified":
            assert any(char.isdigit() for char in teaching_content), case["id"]
            assert any(token in teaching_content for token in (
                "公式", "关系", "面积", "周长", "速度", "分率", "单位", "总价",
                "×", "÷", "+", "-", "√"
            )), case["id"]
            assert any(token in teaching_content for token in (
                "验证", "符合", "答案", "相符", "还原"
            )), case["id"]
        else:
            assert solved.answer is None, case["id"]
            assert any(token in narration for token in ("缺少", "不足", "无法", "不能", "需要")), case["id"]


def test_benchmark_cases_have_complete_teaching_and_source_metadata():
    import json
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "primary_math_benchmark_v1.json"
    dataset = json.loads(fixture.read_text(encoding="utf-8"))
    for case in dataset["cases"]:
        assert case["problem"]
        assert case["concepts"]
        assert case["formula"]
        assert case["solution_steps"]
        assert case["source_refs"]
        assert case["verification"]
        if case["verification_status"] == "verified":
            assert case["standard_answer"]
            assert case["calculation_steps"]




def test_square_perimeter_storyboard_uses_correct_answer_and_formula():
    result = build_explanation("一个正方形的边长是4，求周长是多少", "text")
    assert result.answer == "16"
    assert result.verification_status == "verified"
    assert any("边长 × 4" in scene.visual_text for scene in result.scenes)
    assert result.scenes[-1].visual_text == "答案：16｜验证通过"


def test_rectangle_perimeter_storyboard_uses_correct_answer_and_formula():
    result = build_explanation("一个长方形长8厘米、宽5厘米，求周长是多少？", "text")
    assert result.answer == "26厘米"
    assert result.verification_status == "verified"
    assert any("(8 + 5) * 2 = 26" in scene.visual_text for scene in result.scenes)
