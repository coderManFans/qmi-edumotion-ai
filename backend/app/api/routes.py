from fastapi import APIRouter

from app.schemas.lesson import LessonGenerateRequest, LessonGenerateResponse
from app.services.lesson_generation import generate_lesson

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
