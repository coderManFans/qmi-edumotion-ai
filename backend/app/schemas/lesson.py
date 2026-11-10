from typing import Literal

from pydantic import BaseModel, Field


class LessonGenerateRequest(BaseModel):
    subject: Literal["mathematics", "chinese"]
    topic: str = Field(min_length=2, max_length=100)
    grade_level: int = Field(ge=1, le=12)
    title: str | None = Field(default=None, max_length=120)
    learning_objectives: list[str] = Field(default_factory=list, max_length=8)


class LessonGenerateResponse(BaseModel):
    schema_version: Literal["1.0.0"]
    lesson_id: str
    subject: Literal["mathematics", "chinese"]
    title: str
    language: str
    grade_level: int
    learning_objectives: list[str]
    scenes: list[dict]
