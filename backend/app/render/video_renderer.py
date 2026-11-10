import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.core.config import settings
from app.schemas.problem import ExplanationScene

WIDTH, HEIGHT = 1280, 720


def _font(size: int, bold: bool = False):
    names = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc", "C:/Windows/Fonts/msyh.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for name in names:
        if Path(name).exists():
            return ImageFont.truetype(name, size=size)
    return ImageFont.load_default()


def _lines(value: str, limit: int, count: int) -> list[str]:
    text = str(value or "")
    return [text[i:i + limit] for i in range(0, len(text), limit)][:count] or [""]


def _frame(scene: ExplanationScene, index: int, total: int, frame: int, frames_per_scene: int) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), "#f4f6fc")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((54, 42, WIDTH - 54, HEIGHT - 42), radius=32, fill="#ffffff", outline="#e2e7f1", width=2)
    draw.text((100, 88), "EDUMOTION AI  /  PROBLEM EXPLAINER", font=_font(20, True), fill="#6675a8")
    draw.text((100, 145), f"{index + 1:02d}  /  {total:02d}", font=_font(22, True), fill="#9aa4b8")
    draw.text((100, 200), scene.title, font=_font(42, True), fill="#17233b")
    draw.rounded_rectangle((100, 285, WIDTH - 100, 545), radius=24, fill="#f1f4ff")
    y = 330
    for line in _lines(scene.visual_text, 24, 4):
        draw.text((145, y), line, font=_font(34, True), fill="#344d9a")
        y += 52
    y = 575
    for line in _lines(scene.narration, 46, 2):
        draw.text((100, y), line, font=_font(21), fill="#536176")
        y += 32
    left, right = 100, WIDTH - 100
    draw.rounded_rectangle((left, 655, right, 665), radius=5, fill="#e8ebf3")
    progress = (index + frame / max(frames_per_scene, 1)) / max(total, 1)
    draw.rounded_rectangle((left, 655, left + int((right - left) * progress), 665), radius=5, fill="#5269bd")
    marker_x = 150 + int((WIDTH - 300) * (frame / max(frames_per_scene - 1, 1)))
    draw.ellipse((marker_x - 12, 265, marker_x + 12, 289), fill="#e5a43b")
    return image


def render_explanation_video(job_id: str, scenes: list[ExplanationScene]) -> Path:
    if not shutil.which(settings.ffmpeg_bin):
        raise RuntimeError(f"未找到 FFmpeg：{settings.ffmpeg_bin}。请安装 FFmpeg 并加入 PATH。")
    output_dir = Path(settings.video_output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{job_id}.mp4"
    fps = max(6, min(settings.video_fps, 24))
    seconds = max(2, min(settings.video_scene_seconds, 8))
    frames_per_scene = fps * seconds
    with tempfile.TemporaryDirectory(prefix="edumotion-render-") as tmp:
        frame_dir = Path(tmp)
        frame_number = 0
        for index, scene in enumerate(scenes):
            for frame_index in range(frames_per_scene):
                _frame(scene, index, len(scenes), frame_index, frames_per_scene).save(
                    frame_dir / f"frame_{frame_number:06d}.png", optimize=True
                )
                frame_number += 1
        command = [
            settings.ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y",
            "-framerate", str(fps), "-i", str(frame_dir / "frame_%06d.png"),
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(output_path),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
        if result.returncode:
            output_path.unlink(missing_ok=True)
            raise RuntimeError(f"FFmpeg 合成失败：{result.stderr[-1200:]}")
    return output_path
