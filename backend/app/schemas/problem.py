from typing import Literal
from pydantic import BaseModel, Field


class ExplanationScene(BaseModel):
    id: str
    title: str
    narration: str
    visual: Literal["question", "highlight", "step", "answer", "check"]
    visual_text: str


class ProblemExplanationResponse(BaseModel):
    job_id: str
    source_type: Literal["text", "txt", "pdf", "image"]
    extracted_text: str
    problem_title: str
    explanation: str
    scenes: list[ExplanationScene]
    video_status: Literal["storyboard_ready", "renderer_pending"] = "storyboard_ready"
    video_url: str | None = None


class ProblemTextRequest(BaseModel):
    text: str = Field(min_length=3, max_length=12000)
