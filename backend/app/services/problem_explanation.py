import re
import uuid

from app.ai.problem_solver import _local_solution, to_scenes
from app.schemas.problem import ProblemExplanationResponse


def build_explanation(problem_text: str, source_type: str) -> ProblemExplanationResponse:
    cleaned = re.sub(r"\s+", " ", problem_text).strip()
    solution = _local_solution(cleaned)
    return ProblemExplanationResponse(
        job_id=str(uuid.uuid4()), source_type=source_type, extracted_text=cleaned,
        problem_title=cleaned[:42] + ("…" if len(cleaned) > 42 else ""),
        explanation=solution.explanation, answer=solution.answer,
        verification_status=solution.verification_status, scenes=to_scenes(solution, cleaned),
    )
