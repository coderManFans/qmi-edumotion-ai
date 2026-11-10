from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.schemas.lesson import LessonGenerateRequest, LessonGenerateResponse
from app.schemas.problem import ProblemExplanationResponse
from app.services.lesson_generation import generate_lesson
from app.services.problem_input import ProblemInputError, extract_problem_text
from app.services.problem_explanation import build_explanation, generate_explanation_video

router = APIRouter()


@router.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "edumotion-api"}


@router.post("/lessons/generate", response_model=LessonGenerateResponse, tags=["lessons"])
def create_lesson(request: LessonGenerateRequest) -> dict:
    return generate_lesson(request)


async def _read_problem(text: str, file: UploadFile | None) -> tuple[str, str]:
    if file is None and not text.strip():
        raise HTTPException(status_code=400, detail="请粘贴题目文字，或上传 TXT、PDF、图片文件。")
    if file is None:
        return text.strip(), "text"
    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件不能超过 15 MB。")
    try:
        extracted, source_type = await run_in_threadpool(
            extract_problem_text, file.filename or "", file.content_type or "", data
        )
    except ProblemInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if text.strip():
        extracted = text.strip() + "\n" + extracted
    return extracted, source_type


@router.post("/problems/explain", response_model=ProblemExplanationResponse, tags=["problems"])
async def explain_problem(text: str = Form(default=""), file: UploadFile | None = File(default=None)):
    extracted, source_type = await _read_problem(text, file)
    try:
        return build_explanation(extracted, source_type)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="讲解分镜生成失败，请稍后重试。") from exc


@router.post("/problems/video", response_model=ProblemExplanationResponse, tags=["problems"])
async def create_problem_video(text: str = Form(default=""), file: UploadFile | None = File(default=None)):
    extracted, source_type = await _read_problem(text, file)
    try:
        return await generate_explanation_video(extracted, source_type)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)[:1000]) from exc


@router.get("/problems/videos/{job_id}", tags=["problems"], summary="Download generated MP4")
def get_problem_video(job_id: str):
    try:
        safe_id = str(UUID(job_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="视频不存在。") from exc
    path = Path(settings.video_output_dir).resolve() / f"{safe_id}.mp4"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="视频不存在或已被清理。")
    return FileResponse(path, media_type="video/mp4", filename=f"edumotion-{safe_id}.mp4")
