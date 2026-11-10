import ast
import json
import operator
import re
from typing import Literal

import httpx
from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.problem import ExplanationScene


class SolvedStep(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    explanation: str = Field(min_length=1, max_length=500)
    narration: str = Field(min_length=1, max_length=500)
    visual_text: str = Field(min_length=1, max_length=120)
    expression: str | None = None


class SolvedProblem(BaseModel):
    answer: str | None = None
    verification_status: Literal["verified", "unverified"] = "unverified"
    explanation: str
    steps: list[SolvedStep] = Field(min_length=2, max_length=8)


def _safe_arithmetic(expression: str) -> float:
    operations = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in operations:
            return operations[type(node.op)](visit(node.left), visit(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -visit(node.operand)
        raise ValueError("Unsupported arithmetic expression")
    return float(visit(ast.parse(expression, mode="eval")))


def _local_solution(problem: str) -> SolvedProblem:
    numbers = re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?", problem)
    if len(numbers) >= 2:
        a, b = float(numbers[0]), float(numbers[1])
        if re.search(r"平均分|每人|每组|分成|平分|平均分配", problem):
            symbol, value, label = "/", (a / b if b else None), "平均分配"
        elif re.search(r"每个.*有|几倍|倍数|每份.*个", problem):
            symbol, value, label = "×", a * b, "求几个相同数量的总和"
        elif re.search(r"还剩|剩下|送给|用去|减少|拿走|吃掉|比.+少", problem):
            symbol, value, label = "−", a - b, "从原有数量中减去变化的数量"
        elif re.search(r"一共|总共|合起来|共有|共计|增加|多了", problem):
            symbol, value, label = "+", a + b, "把两部分数量合并"
        else:
            symbol, value, label = "", None, ""
        if symbol and value is not None:
            answer = str(int(value)) if value.is_integer() else str(round(value, 4))
            expression = f"{numbers[0]} {symbol} {numbers[1]}"
            return SolvedProblem(
                answer=answer, verification_status="verified",
                explanation=f"根据题目中的数量关系，使用{label}的方法。",
                steps=[
                    SolvedStep(title="找出已知条件", explanation=f"题目中出现了 {numbers[0]} 和 {numbers[1]} 两个数量。", narration=f"先找出题目给出的两个数量，分别是 {numbers[0]} 和 {numbers[1]}。", visual_text=f"{numbers[0]}   {numbers[1]}"),
                    SolvedStep(title="确定数量关系", explanation=label, narration=f"题目描述的是{label}，所以选择运算符号 {symbol}。", visual_text=expression, expression=expression),
                    SolvedStep(title="计算并回答", explanation=f"{expression} = {answer}", narration=f"计算得到 {answer}。请结合题目中的单位写出完整答案。", visual_text=f"{expression} = {answer}", expression=expression),
                ],
            )
    return SolvedProblem(
        explanation="当前没有足够可靠的规则确定答案。请配置兼容 OpenAI Chat Completions 的模型服务，或人工核对解题步骤。",
        steps=[
            SolvedStep(title="读懂题目", explanation=problem[:240], narration="先完整阅读题目，确认题目给出的条件和需要回答的问题。", visual_text=problem[:80]),
            SolvedStep(title="整理条件", explanation="标记数量、单位、关键词和它们之间的关系。", narration="把已知条件整理出来，判断它们之间的数学关系。", visual_text="已知条件 → 数量关系"),
            SolvedStep(title="核对解题思路", explanation="本题尚未自动求解，不能将猜测当作答案。", narration="这一步需要进一步分析，当前系统不会编造答案。", visual_text="待进一步分析"),
        ],
    )


async def solve_problem(problem: str) -> SolvedProblem:
    if not (settings.llm_base_url and settings.llm_model and settings.llm_api_key):
        return _local_solution(problem)
    endpoint = settings.llm_base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": settings.llm_model, "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": (
                "你是中小学题目讲解助手。只根据题目求解，不补造条件。"
                "只输出 JSON：answer(字符串或null)、verification_status(verified/unverified)、"
                "explanation(字符串)、steps(2到8项数组)。每项字段 title、explanation、narration、"
                "visual_text、expression(字符串或null)。题目歧义或无法确认时 answer=null，"
                "verification_status=unverified，并说明缺少什么。不要输出代码。"
            )},
            {"role": "user", "content": problem},
        ],
    }
    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        response = await client.post(endpoint, headers={"Authorization": f"Bearer {settings.llm_api_key}"}, json=payload)
        response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"].strip()
    content = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", content)
    solved = SolvedProblem.model_validate(json.loads(content))
    # Never trust a model's "verified" flag on its own. Verify simple final arithmetic locally.
    if solved.answer is not None and solved.steps[-1].expression:
        expression = solved.steps[-1].expression
        expression = expression.replace("×", "*").replace("÷", "/").replace("−", "-")
        left_side = expression.split("=")[0].strip()
        try:
            computed = _safe_arithmetic(left_side)
            expected = float(re.sub(r"[^0-9.\-]", "", solved.answer))
            solved.verification_status = "verified" if abs(computed - expected) < 1e-8 else "unverified"
        except (ValueError, SyntaxError, ZeroDivisionError):
            solved.verification_status = "unverified"
    else:
        solved.verification_status = "unverified"
    return solved


def to_scenes(solution: SolvedProblem, original_text: str) -> list[ExplanationScene]:
    visual_types = ["highlight", "step", "answer", "check"]
    scenes = [
        ExplanationScene(
            id=f"scene-{i + 1}", title=step.title, narration=step.narration,
            visual=visual_types[min(i, len(visual_types) - 1)],
            visual_text=step.visual_text, expression=step.expression,
        )
        for i, step in enumerate(solution.steps)
    ]
    scenes.insert(0, ExplanationScene(
        id="scene-0", title="题目呈现", narration="我们先来看这道题。",
        visual="question", visual_text=original_text[:100],
    ))
    scenes.append(ExplanationScene(
        id="scene-check", title="检查与回顾",
        narration="最后检查运算关系、计算结果和题目单位，确认答案真正回应了问题。",
        visual="check",
        visual_text=(f"答案：{solution.answer}" if solution.answer is not None else "答案尚未验证"),
    ))
    return scenes
