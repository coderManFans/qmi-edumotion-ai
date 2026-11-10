from uuid import uuid4


def generate_math_lesson(topic: str, grade_level: int, title: str | None, objectives: list[str]) -> dict:
    is_fraction = "分数" in topic or "fraction" in topic.lower()
    expression = r"\frac{1}{4}" if is_fraction else topic
    explanation = (
        "把一个整体平均分成 4 份，取其中 1 份，就是四分之一。"
        if is_fraction
        else f"学习“{topic}”时，先弄清楚概念，再通过例子一步步验证。"
    )
    diagram = {"shape": "circle", "parts": 4, "selected": [0]} if is_fraction else {
        "kind": "concept-map", "topic": topic, "nodes": ["概念", "例子", "练习"]
    }
    return {
        "schema_version": "1.0.0",
        "lesson_id": str(uuid4()),
        "subject": "mathematics",
        "title": title or f"{topic}：循序渐进学数学",
        "language": "zh-CN",
        "grade_level": grade_level,
        "learning_objectives": objectives or [f"理解{topic}的基本概念", f"能够运用{topic}解决简单问题"],
        "scenes": [
            {
                "id": "scene-1", "type": "explanation", "narration": explanation,
                "duration_seconds": 18,
                "blocks": [
                    {"type": "text", "content": explanation},
                    {"type": "math", "content": expression},
                    {"type": "diagram", "content": diagram},
                ],
            },
            {
                "id": "scene-2", "type": "question", "narration": "试着用刚才的方法想一想，再查看解析。",
                "duration_seconds": 20,
                "blocks": [{
                    "type": "quiz",
                    "content": {
                        "question": "学习一个新数学概念时，下面哪种方法更合适？",
                        "options": ["只记住答案", "理解概念并结合例子验证", "跳过例题直接做难题"],
                        "answer": 1,
                        "explanation": "先理解概念，再结合例子验证，有助于真正掌握知识。",
                    },
                }],
            },
            {
                "id": "scene-3", "type": "summary", "narration": "回顾概念、例子和练习，完成本节学习。",
                "blocks": [{"type": "text", "content": f"本节回顾：{topic}。先理解概念，再观察例子，最后独立完成练习。"}],
            },
        ],
    }
