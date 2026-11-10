import uuid
from pathlib import Path
from uuid import UUID

from celery.result import AsyncResult
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from app.celery_app import celery_app
from app.core.config import settings
from app.schemas.lesson import LessonGenerateRequest, LessonGenerateResponse
from app.schemas.problem import ProblemExplanationResponse, ProblemJobResponse
from app.services.lesson_generation import generate_lesson
from app.services.problem_input import ProblemInputError, extract_problem_text
from app.tasks import generate_problem_video_task

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
    from app.services.problem_explanation import build_explanation

    extracted, source_type = await _read_problem(text, file)
    try:
        return build_explanation(extracted, source_type)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="讲解分镜生成失败，请稍后重试。") from exc


@router.post("/problems/video", response_model=ProblemJobResponse, status_code=202, tags=["problems"])
async def create_problem_video(text: str = Form(default=""), file: UploadFile | None = File(default=None)):
    extracted, source_type = await _read_problem(text, file)
    job_id = str(uuid.uuid4())
    try:
        generate_problem_video_task.apply_async(
            args=[job_id, extracted, source_type], task_id=job_id
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="任务队列暂不可用，请确认 Redis 和 Worker 已启动。") from exc
    return ProblemJobResponse(
        job_id=job_id, status="queued", progress=0, stage="任务已进入队列，等待 Worker 处理"
    )


@router.get("/problems/jobs/{job_id}", response_model=ProblemJobResponse, tags=["problems"])
def get_problem_job(job_id: str):
    try:
        safe_id = str(UUID(job_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="任务不存在。") from exc

    task = AsyncResult(safe_id, app=celery_app)
    if task.state == "SUCCESS":
        result = ProblemExplanationResponse.model_validate(task.result)
        return ProblemJobResponse(
            job_id=safe_id, status="completed", progress=100, stage="视频与配音已完成",
            result=result, video_url=result.video_url,
        )
    if task.state == "FAILURE":
        return ProblemJobResponse(
            job_id=safe_id, status="failed", progress=0, stage="任务执行失败",
            error=str(task.info)[:1000],
        )
    if task.state in {"STARTED", "PROGRESS", "RETRY"}:
        meta = task.info if isinstance(task.info, dict) else {}
        return ProblemJobResponse(
            job_id=safe_id, status="processing", progress=int(meta.get("progress", 5)),
            stage=meta.get("stage", "Worker 正在处理"),
        )
    return ProblemJobResponse(
        job_id=safe_id, status="queued", progress=0, stage="任务已进入队列，等待 Worker 处理"
    )


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
