from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.schemas.lesson import LessonGenerateRequest, LessonGenerateResponse
from app.schemas.problem import ProblemExplanationResponse
from app.services.lesson_generation import generate_lesson
from app.services.problem_input import ProblemInputError, extract_problem_text
from app.services.problem_explanation import build_explanation

router = APIRouter()


@router.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "edumotion-api"}


@router.post(
    "/lessons/generate",
    response_model=LessonGenerateResponse,
    tags=["lessons"],
    summary="Generate a demo lesson document",
)
def create_lesson(request: LessonGenerateRequest) -> dict:
    return generate_lesson(request)


@router.post(
    "/problems/explain",
    response_model=ProblemExplanationResponse,
    tags=["problems"],
    summary="Import a problem and generate an explanation storyboard",
)
async def explain_problem(
    text: str = Form(default=""),
    file: UploadFile | None = File(default=None),
) -> ProblemExplanationResponse:
    if file is None and not text.strip():
        raise HTTPException(status_code=400, detail="请粘贴题目文字，或上传 TXT、PDF、图片文件。")
    if file is not None:
        data = await file.read()
        if len(data) > 15 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="文件不能超过 15 MB。")
        try:
            extracted, source_type = extract_problem_text(file.filename or "", file.content_type or "", data)
        except ProblemInputError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if text.strip():
            extracted = text.strip() + "\\n" + extracted
    else:
        extracted, source_type = text.strip(), "text"
    try:
        return build_explanation(extracted, source_type)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="讲解分镜生成失败，请稍后重试。") from exc
