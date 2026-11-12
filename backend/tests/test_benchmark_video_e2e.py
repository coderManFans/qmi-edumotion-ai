import asyncio
import json
import shutil
import subprocess
import uuid
from pathlib import Path

from app.ai.problem_solver import _local_solution, to_scenes
from app.render.video_renderer import render_explanation_video
from app.services.tts import synthesize_scene_audio
from app.core.config import settings


FIXTURE = Path(__file__).parent / "fixtures" / "primary_math_benchmark_v1.json"
REPORT = Path(__file__).parent.parent / "data" / "benchmark_video_report.json"

# One representative, fully specified case from each requested teaching family.
TOPIC_MATCHES = {
    "square": "正方形面积反求边长",
    "fraction": "分数应用题反求单位1",
    "percentage": "百分数应用题反求单位1",
    "unit_conversion": "面积单位换算",
    "multi_step": "长方形周长求面积两步题",
}


def _probe(path: Path) -> dict:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-show_entries", "stream=codec_type", "-of", "json", str(path)],
        capture_output=True, text=True, timeout=30, check=True,
    )
    return json.loads(result.stdout)


def test_five_benchmark_cases_generate_narrated_mp4s(monkeypatch):
    dataset = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cases = dataset["cases"]
    selected = {}
    for family, topic in TOPIC_MATCHES.items():
        case = next((item for item in cases if item["topic"] == topic
                     and item["verification_status"] == "verified"), None)
        assert case is not None, f"fixture has no verified representative for {family}"
        selected[family] = case

    monkeypatch.setattr(settings, "tts_provider", "edge")
    output_dir = Path(settings.video_output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {"dataset_id": dataset["dataset_id"], "videos": []}

    for family, case in selected.items():
        solved = _local_solution(case["problem"])
        assert solved.verification_status == "verified", case["id"]
        assert solved.answer == case["standard_answer"], case["id"]
        scenes = to_scenes(solved, case["problem"])

        teaching_narration = [step.narration.strip() for step in solved.steps]
        assert len(teaching_narration) >= 3, case["id"]
        assert all(teaching_narration), case["id"]
        narration_text = "\n".join(teaching_narration)
        # Ensure the generated script includes the actual formula, numerical
        # substitution/result, and a check or explicit answer—not generic filler.
        combined = "\n".join(
            f"{step.title} {step.explanation} {step.narration} {step.visual_text}"
            for step in solved.steps
        )
        assert any(token in combined for token in ("公式", "关系", "面积", "单位", "分率", "周长", "长方形")), case["id"]
        assert any(char.isdigit() for char in combined), case["id"]
        assert any(token in combined for token in ("验证", "符合", "答案", "还原", "相符")), case["id"]

        job_id = f"benchmark-{family}-{uuid.uuid4().hex[:8]}"
        audio_dir = output_dir / f"{job_id}-audio"
        audio_path, durations = asyncio.run(synthesize_scene_audio(scenes, audio_dir))
        assert audio_path and audio_path.is_file() and audio_path.stat().st_size > 0, case["id"]
        assert durations and len(durations) == len(scenes), case["id"]

        video_path = render_explanation_video(
            job_id, scenes, audio_path=audio_path, scene_durations=durations
        )
        assert video_path.is_file() and video_path.stat().st_size > 0, case["id"]
        media = _probe(video_path)
        stream_types = {stream["codec_type"] for stream in media["streams"]}
        assert {"video", "audio"} <= stream_types, case["id"]
        duration = float(media["format"]["duration"])
        assert duration > 0, case["id"]

        narration_file = output_dir / f"{job_id}-narration.txt"
        narration_file.write_text(narration_text, encoding="utf-8")
        report["videos"].append({
            "family": family, "case_id": case["id"], "problem": case["problem"],
            "expected_answer": case["standard_answer"], "actual_answer": solved.answer,
            "verification_status": solved.verification_status,
            "narration_file": str(narration_file), "video_file": str(video_path),
            "duration_seconds": duration, "audio_video_streams": sorted(stream_types),
            "steps": [{"title": s.title, "explanation": s.explanation,
                       "narration": s.narration, "visual_text": s.visual_text}
                      for s in solved.steps],
        })
        shutil.rmtree(audio_dir, ignore_errors=True)

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    assert len(report["videos"]) == 5
