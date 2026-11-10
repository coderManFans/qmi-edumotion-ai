import re
import uuid
from app.schemas.problem import ProblemExplanationResponse, ExplanationScene


def build_explanation(problem_text: str, source_type: str) -> ProblemExplanationResponse:
    cleaned = re.sub(r"\\s+", " ", problem_text).strip()
    title = cleaned[:42] + ("…" if len(cleaned) > 42 else "")
    # This deterministic storyboard keeps the first vertical slice runnable without a model key.
    # Replace this adapter with an LLM-backed solver before presenting generated answers as authoritative.
    steps = [
        ("读懂题目", "question", cleaned[:180], "先把题目读完整，找出已知条件和要求我们求什么。"),
        ("拆解条件", "highlight", "已知条件  →  分析关系", "把题目中的数字、单位和关键词圈出来，判断它们之间的关系。"),
        ("逐步思考", "step", "分析  →  列式  →  计算", "根据题意选择合适的方法，写出每一步推理。计算时注意检查单位和运算顺序。"),
        ("得到结论", "answer", "写出答案，并说明理由", "把计算结果放回题目中检查，确认它回答了题目真正提出的问题。"),
        ("回顾检查", "check", "条件是否用全？答案合理吗？", "最后检查每个已知条件是否都被正确使用，答案是否符合实际情境。"),
    ]
    scenes = [ExplanationScene(id=f"scene-{i+1}", title=t, visual=v, visual_text=visual, narration=narration)
              for i, (t, v, visual, narration) in enumerate(steps)]
    return ProblemExplanationResponse(
        job_id=str(uuid.uuid4()),
        source_type=source_type,
        extracted_text=cleaned,
        problem_title=title,
        explanation="已生成讲解分镜草稿。当前版本负责题目导入与讲解结构编排；自动求解、语音和 MP4 渲染尚未接入。",
        scenes=scenes,
    )
