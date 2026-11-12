import pytest

from app.ai.problem_solver import _local_solution


@pytest.mark.parametrize(
    ("problem", "expected", "relation"),
    [
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
    assert solved.steps[0].title == "提取已知条件"
    assert solved.steps[-1].title == "回答并验证"
    assert solved.steps[-1].expression is not None


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
