import pytest

from app.ai.problem_solver import _local_solution, to_scenes
from app.render.video_renderer import _frame
from app.schemas.problem import ExplanationScene
from PIL import Image


def test_local_solver_verifies_basic_subtraction_word_problem():
    solved = _local_solution("小红有 12 个苹果，送给小明 4 个，还剩多少个？")
    assert solved.answer == "8"
    assert solved.verification_status == "verified"
    assert solved.steps[-1].expression == "12 − 4"


def test_ambiguous_problem_does_not_invent_answer():
    solved = _local_solution("请解释一下这道题的思路")
    assert solved.answer is None
    assert solved.verification_status == "unverified"


def test_storyboard_contains_original_question_scene():
    solved = _local_solution("12 个苹果送走 4 个，还剩多少？")
    scenes = to_scenes(solved, "12 个苹果送走 4 个，还剩多少？")
    assert scenes[0].title == "题目呈现"
    assert len(scenes) == len(solved.steps) + 2


def test_renderer_produces_a_video_frame():
    scene = ExplanationScene(
        id="scene-1", title="计算", narration="十二减四等于八。",
        visual="answer", visual_text="12 − 4 = 8",
    )
    frame = _frame(scene, 0, 1, 1, 12)
    assert isinstance(frame, Image.Image)
    assert frame.size == (1280, 720)


@pytest.mark.parametrize("duration", [float("nan"), 121.0, 0.0])
def test_renderer_rejects_invalid_or_overlong_audio_segments(monkeypatch, tmp_path, duration):
    from app.render import video_renderer

    monkeypatch.setattr(video_renderer.shutil, "which", lambda _: "ffmpeg")
    monkeypatch.setattr(video_renderer.settings, "video_output_dir", str(tmp_path))
    scene = ExplanationScene(
        id="scene-1", title="计算", narration="计算结果。",
        visual="answer", visual_text="1 + 1 = 2",
    )

    with pytest.raises(ValueError, match="有效数值"):
        video_renderer.render_explanation_video(
            "job-test", [scene], scene_durations=[duration]
        )
def test_square_problem_uses_geometry_animation_template():
    scenes = to_scenes(_local_solution("一个正方形周长是16，求边长是多少？"), "一个正方形周长是16，求边长是多少？")
    assert scenes[0].visual == "knowledge_square"
    frame = _frame(scenes[0], 0, len(scenes), 1, 12)
    assert isinstance(frame, Image.Image)


def test_travel_problem_uses_journey_animation_template():
    scenes = to_scenes(_local_solution("路程是180千米，速度是60千米/小时，时间是多少小时？"), "路程是180千米，速度是60千米/小时，时间是多少小时？")
    assert scenes[0].visual == "knowledge_journey"
    frame = _frame(scenes[0], 0, len(scenes), 1, 12)
    assert isinstance(frame, Image.Image)


def test_sharing_problem_uses_equal_groups_animation_template():
    scenes = to_scenes(_local_solution("小明有12个苹果，平均分给3个同学，每人几个？"), "小明有12个苹果，平均分给3个同学，每人几个？")
    assert scenes[0].visual == "knowledge_sharing"


