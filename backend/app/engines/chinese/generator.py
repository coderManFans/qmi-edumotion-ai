from uuid import uuid4


def generate_chinese_lesson(topic: str, grade_level: int, title: str | None, objectives: list[str]) -> dict:
    story = [
        f"清晨，{topic}悄悄开始了新的一天。小主人公带着好奇，决定认真观察身边发生的事情。",
        "一路上，它遇到了一个小小的难题。它没有急着放弃，而是仔细思考，主动向伙伴请教。",
        "经过尝试与合作，难题终于解决了。它明白了：保持好奇、认真观察、勇敢尝试，常常能带来新的发现。",
    ]
    return {
        "schema_version": "1.0.0",
        "lesson_id": str(uuid4()),
        "subject": "chinese",
        "title": title or f"{topic}：一段小故事",
        "language": "zh-CN",
        "grade_level": grade_level,
        "learning_objectives": objectives or ["理解故事内容", "梳理故事发展顺序", "表达故事带来的启发"],
        "scenes": [
            {
                "id": "scene-1", "type": "story", "narration": "".join(story),
                "duration_seconds": 35,
                "blocks": [{"type": "text", "content": paragraph} for paragraph in story],
            },
            {
                "id": "scene-2", "type": "question", "narration": "想一想，主人公是怎样解决问题的？",
                "blocks": [{
                    "type": "quiz",
                    "content": {
                        "question": "故事中的主人公遇到难题时，采取了什么做法？",
                        "options": ["立刻放弃", "仔细思考并向伙伴请教", "假装没有看见"],
                        "answer": 1,
                        "explanation": "主人公通过思考和请教伙伴，最终解决了问题。",
                    },
                }],
            },
            {
                "id": "scene-3", "type": "summary", "narration": "回顾故事，试着用自己的话说说收获。",
                "blocks": [{"type": "text", "content": "故事启发：保持好奇，认真观察，遇到困难时勇敢尝试并学会合作。"}],
            },
        ],
    }
