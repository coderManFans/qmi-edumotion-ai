from app.engines.chinese.generator import generate_chinese_lesson
from app.engines.math.generator import generate_math_lesson
from app.schemas.lesson import LessonGenerateRequest


def generate_lesson(request: LessonGenerateRequest) -> dict:
    """Generate a deterministic demo lesson until an LLM provider is configured."""
    if request.subject == "mathematics":
        return generate_math_lesson(
            request.topic, request.grade_level, request.title, request.learning_objectives
        )
    return generate_chinese_lesson(
        request.topic, request.grade_level, request.title, request.learning_objectives
    )
