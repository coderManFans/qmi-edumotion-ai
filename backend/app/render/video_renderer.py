import math
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.core.config import settings
from app.schemas.problem import ExplanationScene

WIDTH, HEIGHT = 1280, 720


@lru_cache(maxsize=16)
def _font(size: int, bold: bool = False):
    names = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Bold.otf" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
        "/System/Library/Fonts/PingFang.ttc", "C:/Windows/Fonts/msyh.ttc",
    ]
    for name in names:
        if Path(name).exists():
            return ImageFont.truetype(name, size=size)
    raise RuntimeError("未找到支持中文的字体。请安装 Noto CJK 字体后重试。")


def _lines(value: str, limit: int, count: int) -> list[str]:
    text = str(value or "")
    return [text[i:i + limit] for i in range(0, len(text), limit)][:count] or [""]


def _draw_knowledge_visual(draw: ImageDraw.ImageDraw, visual: str, frame: int):
    """Draw a small topic-specific teaching visual in the right half of the lesson card."""
    ink, accent, pale = "#344d9a", "#e5a43b", "#dce5ff"
    if visual == "knowledge_square":
        draw.rectangle((820, 340, 1010, 530), outline=ink, width=7, fill=pale)
        draw.text((875, 420), "边长", font=_font(25, True), fill=ink)
        draw.text((875, 545), "4条边相等", font=_font(20, True), fill=ink)
    elif visual == "knowledge_rectangle":
        draw.rectangle((790, 380, 1060, 500), outline=ink, width=7, fill=pale)
        draw.text((890, 425), "长 × 宽", font=_font(27, True), fill=ink)
        draw.text((860, 530), "相对边相等", font=_font(20, True), fill=ink)
    elif visual == "knowledge_journey":
        draw.line((790, 455, 1090, 455), fill=ink, width=8)
        for x in (810, 1060):
            draw.ellipse((x-10, 445, x+10, 465), fill=accent)
        car_x = 820 + (frame * 7) % 220
        draw.rounded_rectangle((car_x, 395, car_x+88, 445), radius=12, fill=accent, outline=ink, width=3)
        draw.ellipse((car_x+12, 435, car_x+34, 457), fill="#26334d")
        draw.ellipse((car_x+58, 435, car_x+80, 457), fill="#26334d")
        draw.text((850, 500), "路程 = 速度 × 时间", font=_font(19, True), fill=ink)
    elif visual == "knowledge_sharing":
        for i in range(4):
            x = 790 + i * 76
            draw.ellipse((x, 375, x+58, 433), fill=pale, outline=ink, width=3)
            draw.text((x+18, 390), str(i+1), font=_font(21, True), fill=ink)
        draw.text((800, 470), "平均分成4份", font=_font(25, True), fill=ink)
    elif visual == "knowledge_fraction":
        x0, y0, width = 790, 395, 280
        draw.rounded_rectangle((x0, y0, x0+width, y0+54), radius=8, fill="#edf0f7", outline=ink, width=2)
        for i in range(1, 5):
            x = x0 + i * width / 5
            draw.line((x, y0, x, y0+54), fill="#ffffff", width=4)
        draw.rectangle((x0, y0, x0+width*3/5, y0+54), fill=accent)
        draw.text((850, 480), "单位“1”平均分成5份", font=_font(21, True), fill=ink)
    elif visual == "knowledge_percentage":
        draw.ellipse((850, 355, 1040, 545), outline="#dce2ef", width=22)
        draw.arc((850, 355, 1040, 545), start=270, end=342, fill=accent, width=22)
        draw.text((885, 425), "百分率", font=_font(26, True), fill=ink)
    elif visual == "knowledge_conversion":
        draw.rounded_rectangle((785, 375, 925, 450), radius=14, fill=pale, outline=ink, width=3)
        draw.rounded_rectangle((1000, 375, 1140, 450), radius=14, fill=pale, outline=ink, width=3)
        draw.text((815, 395), "原单位", font=_font(22, True), fill=ink)
        draw.text((1025, 395), "目标单位", font=_font(22, True), fill=ink)
        draw.line((935, 413, 990, 413), fill=accent, width=7)
        draw.polygon([(990, 413), (975, 402), (975, 424)], fill=accent)
        draw.text((830, 490), "先看量纲，再用进率", font=_font(21, True), fill=ink)


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
    if scene.visual.startswith("knowledge_"):
        _draw_knowledge_visual(draw, scene.visual, frame)
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


def render_explanation_video(
    job_id: str,
    scenes: list[ExplanationScene],
    audio_path: Path | None = None,
    scene_durations: list[float] | None = None,
) -> Path:
    if not shutil.which(settings.ffmpeg_bin):
        raise RuntimeError(f"未找到 FFmpeg：{settings.ffmpeg_bin}。请安装 FFmpeg 并加入 PATH。")
    output_dir = Path(settings.video_output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{job_id}.mp4"
    fps = max(6, min(settings.video_fps, 24))
    default_frames = fps * max(2, min(settings.video_scene_seconds, 8))
    if scene_durations and len(scene_durations) != len(scenes):
        raise ValueError("语音分段时长数量必须与分镜数量一致。")

    with tempfile.TemporaryDirectory(prefix="edumotion-render-") as tmp:
        frame_dir = Path(tmp)
        frame_number = 0
        for index, scene in enumerate(scenes):
            duration = scene_durations[index] if scene_durations else default_frames / fps
            frames_per_scene = max(1, min(math.ceil(max(duration, 0.2) * fps), fps * 120))
            for frame_index in range(frames_per_scene):
                _frame(scene, index, len(scenes), frame_index, frames_per_scene).save(
                    frame_dir / f"frame_{frame_number:06d}.png", optimize=True
                )
                frame_number += 1

        silent_path = frame_dir / "silent.mp4"
        command = [
            settings.ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y",
            "-framerate", str(fps), "-i", str(frame_dir / "frame_%06d.png"),
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(silent_path),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=600, check=False)
        if result.returncode:
            raise RuntimeError(f"FFmpeg 视频编码失败：{result.stderr[-1200:]}")

        if audio_path:
            mux = [
                settings.ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(silent_path), "-i", str(audio_path),
                "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                "-c:a", "aac", "-b:a", "128k", "-shortest",
                "-movflags", "+faststart", str(output_path),
            ]
            mux_result = subprocess.run(mux, capture_output=True, text=True, timeout=180, check=False)
            if mux_result.returncode:
                raise RuntimeError(f"FFmpeg 音画合成失败：{mux_result.stderr[-1200:]}")
        else:
            shutil.copy2(silent_path, output_path)
    return output_path
