import pytest

from app.ai.problem_solver import _local_solution


@pytest.mark.parametrize(
    ("problem", "expected", "relation"),
    [
    ("一个正方形的边长是4，求周长是多少", "16", "× 4"),
    ("正方形边长为5厘米，周长是多少？", "20厘米", "× 4"),
        ("已知正方形的面积是16，问：一条长15的绳子能否绕正方形一圈？", "不能，还差1（同一长度单位）", "<"),
        ("正方形面积16，绳长16，能绕一圈吗？", "能，刚好够", "≥"),
        ("正方形的面积是16，一条长18的绳子能绕一圈吗？", "能，多2（同一长度单位）", "≥"),
        ("正方形面积是25平方厘米，一条长19厘米的绳子能绕一圈吗？", "不能，还差1厘米", "<"),
        ("正方形面积是25平方厘米，绳长20厘米，能否绕一圈？", "能，刚好够", "≥"),
        ("正方形面积是25平方厘米，绳子长23厘米，绕一圈后还剩多少？", "能，多3厘米", "≥"),
        ("一个正方形面积为36，绳子长23，能否围一圈？", "不能，还差1（同一长度单位）", "<"),
        ("正方形的面积是9，长13的绳子能不能绕一周？", "能，多1（同一长度单位）", "≥"),
    ],
)
def test_square_area_to_perimeter_to_rope_comparison(problem, expected, relation):
    solved = _local_solution(problem)

    assert solved.answer == expected
    assert solved.verification_status == "verified"
    assert [step.title for step in solved.steps] == [
        "提取已知条件", "先求正方形边长", "再求正方形周长", "比较绳长与周长", "回答并验证"
    ]
    assert any("√" in step.visual_text for step in solved.steps)
    assert any("× 4" in step.visual_text for step in solved.steps)
    assert any(relation in step.visual_text for step in solved.steps)


@pytest.mark.parametrize(
    "problem",
    [
        "正方形面积是20，绳子长15，能绕一圈吗？",
        "正方形面积是16平方厘米，绳子长15米，能绕一圈吗？",
        "正方形面积是16平方厘米，绳子长15，能绕一圈吗？",
        "正方形面积是16，绳子长多少才能绕一圈？",
    ],
)
def test_square_rope_problem_with_ambiguous_or_incomplete_data_stays_unverified(problem):
    solved = _local_solution(problem)

    assert solved.answer is None
    assert solved.verification_status == "unverified"

@pytest.mark.parametrize(
    ("problem", "expected", "step_count"),
    [
        (
            "一个长方形周长是26厘米，长是8厘米，面积是多少？",
            "40平方厘米",
            4,
        ),
        (
            "长方形的周长为30厘米，长9厘米，求它的面积。",
            "54平方厘米",
            4,
        ),
        (
            "一辆汽车行驶了180千米，速度是60千米/小时，需要多少小时？",
            "3小时",
            4,
        ),
        (
            "路程是240千米，速度为80千米/小时，行驶时间是多少？",
            "3小时",
            4,
        ),
    ],
)
def test_other_deterministic_multistep_relation_chains(problem, expected, step_count):
    solved = _local_solution(problem)

    assert solved.answer == expected
    assert solved.verification_status == "verified"
    assert len(solved.steps) == step_count
    assert solved.steps[0].title in {"提取条件", "提取已知条件"}
    assert solved.steps[-1].title in {"验证", "回答并验证"}
    assert any("÷" in step.visual_text or "/" in step.visual_text for step in solved.steps[1:-1])


@pytest.mark.parametrize(
    "problem",
    [
        "一个长方形周长是10厘米，长是8厘米，面积是多少？",
        "一辆汽车行驶了180千米，速度是0千米每小时，需要多少小时？",
    ],
)
def test_invalid_multistep_relationships_do_not_guess(problem):
    solved = _local_solution(problem)

    assert solved.answer is None
    assert solved.verification_status == "unverified"

@pytest.mark.parametrize(
    ("problem", "expected"),
    [
        ("买笔一共花了24元，每支笔单价是6元，买了几支？", "4支"),
        ("买书总价是30元，单价是5元，买了几本书？", "6本"),
    ],
)
def test_inverse_unit_price_quantity_chain(problem, expected):
    solved = _local_solution(problem)

    assert solved.answer == expected
    assert solved.verification_status == "verified"
    assert len(solved.steps) == 4
    assert any("总价" in step.explanation for step in solved.steps)
    assert any("÷" in step.visual_text or "/" in step.visual_text for step in solved.steps)


def test_non_integral_item_quantity_is_not_rounded_or_guessed():
    solved = _local_solution("总价是20元，单价是6元，买了几支笔？")

    assert solved.answer is None
    assert solved.verification_status == "unverified"


@pytest.mark.parametrize(
    ("problem", "expected", "formula_fragment"),
    [
        ("一个正方形的边长是4，求周长是多少", "16", "边长 × 4"),
        ("正方形边长为5厘米，周长是多少？", "20厘米", "边长 × 4"),
        ("一个正方形边长是4，求面积是多少？", "16平方单位", "边长 × 边长"),
        ("一个长方形长8厘米、宽5厘米，求周长是多少？", "26厘米", "长 + 宽"),
        ("一个长方形长8厘米、宽5厘米，求面积是多少？", "40平方厘米", "长 × 宽"),
        ("一个长方形周长是26厘米，长是8厘米，宽是多少？", "5厘米", "周长 ÷ 2"),
        ("一个长方形面积是48平方厘米，长是8厘米，宽是多少？", "6厘米", "面积 ÷ 长"),
        ("一个长方形周长是30厘米，长是9厘米，面积是多少？", "54平方厘米", "周长 ÷ 2"),
    ],
)
def test_square_rectangle_solver_uses_semantic_roles(problem, expected, formula_fragment):
    solved = _local_solution(problem)
    assert solved.answer == expected
    assert solved.verification_status == "verified"
    assert any(formula_fragment in step.explanation or formula_fragment in step.visual_text for step in solved.steps)


@pytest.mark.parametrize(
    "problem",
    [
        "一个长方形周长是10厘米，长是8厘米，面积是多少？",
        "一个长方形长8厘米，面积是多少？",
        "一个正方形面积是16平方厘米，周长是多少？",
        "一个长方形面积是48平方厘米，长是0厘米，宽是多少？",
        "一个长方形长8厘米，宽5厘米，面积是100平方厘米，求周长。",
    ],
)
def test_square_rectangle_solver_rejects_incomplete_or_contradictory_data(problem):
    solved = _local_solution(problem)
    assert solved.answer is None
    assert solved.verification_status == "unverified"
