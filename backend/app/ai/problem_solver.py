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


def _number_text(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _safe_arithmetic(expression: str) -> float:
    """Evaluate only basic arithmetic AST nodes; never use eval()."""
    operations = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
    }

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in operations:
            return operations[type(node.op)](visit(node.left), visit(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            return -visit(node.operand) if isinstance(node.op, ast.USub) else visit(node.operand)
        raise ValueError("Unsupported arithmetic expression")

    value = float(visit(ast.parse(expression, mode="eval")))
    if abs(value) > 1e12:
        raise ValueError("Arithmetic result out of supported range")
    return value


def _steps_for_formula(
    *,
    known: str,
    formula: str,
    rearranged: str,
    substitution: str,
    result: float,
    unit: str,
    conclusion: str,
    verification: str,
) -> SolvedProblem:
    answer = _number_text(result)
    calculation = f"{substitution} = {answer}"
    return SolvedProblem(
        answer=f"{answer}{unit}",
        verification_status="verified",
        explanation=conclusion,
        steps=[
            SolvedStep(
                title="提取已知条件",
                explanation=known,
                narration=f"先找出题目给出的条件：{known}。我们要求的是{conclusion}",
                visual_text=known,
            ),
            SolvedStep(
                title="选择公式并变形",
                explanation=f"根据数量或图形关系：{formula}。整理后得到：{rearranged}。",
                narration=f"这里要用到的公式是：{formula}。把公式变形，就能得到{rearranged}。",
                visual_text=f"{formula}  →  {rearranged}",
            ),
            SolvedStep(
                title="代入数据计算",
                explanation=f"把已知数据代入：{calculation}。",
                narration=f"把题目中的数据代入，{substitution}，计算结果是{answer}{unit}。",
                visual_text=calculation,
                expression=f"{substitution} = {answer}",
            ),
            SolvedStep(
                title="回答并验证",
                explanation=verification,
                narration=f"所以{conclusion}答案是{answer}{unit}。再检查一次：{verification}",
                visual_text=f"答案：{answer}{unit}",
            ),
        ],
    )


def _local_solution(problem: str) -> SolvedProblem:
    """Deterministic, deliberately narrow elementary-math solver.

    A rule is applied only when the wording identifies the operation/formula
    sufficiently clearly. Unsupported or ambiguous questions remain unverified.
    """
    text = re.sub(r"\s+", "", problem)
    numbers = re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?", text)
    values = [float(n) for n in numbers]

    # Triangle area: the prompt must explicitly provide base and height.
    if "三角形" in text and "面积" in text and len(values) == 2 and re.search(r"底.*高|高.*底", text):
        base, height = values
        if base >= 0 and height >= 0:
            area = base * height / 2
            return _steps_for_formula(
                known=f"底 = {_number_text(base)}，高 = {_number_text(height)}",
                formula="三角形面积 = 底 × 高 ÷ 2",
                rearranged="面积 = 底 × 高 ÷ 2",
                substitution=f"{_number_text(base)} * {_number_text(height)} / 2",
                result=area,
                unit="平方单位",
                conclusion="三角形的面积",
                verification=f"{_number_text(base)} × {_number_text(height)} ÷ 2 = {_number_text(area)}",
            )

    # Parallelogram area: require explicit base and perpendicular height wording.
    if "平行四边形" in text and "面积" in text and len(values) == 2 and re.search(r"底.*高|高.*底", text):
        base, height = values
        if base >= 0 and height >= 0:
            area = base * height
            return _steps_for_formula(
                known=f"底 = {_number_text(base)}，高 = {_number_text(height)}",
                formula="平行四边形面积 = 底 × 高",
                rearranged="面积 = 底 × 高",
                substitution=f"{_number_text(base)} * {_number_text(height)}",
                result=area,
                unit="平方单位",
                conclusion="平行四边形的面积",
                verification=f"{_number_text(base)} × {_number_text(height)} = {_number_text(area)}",
            )

    # Trapezoid area: require upper base, lower base and height.
    if "梯形" in text and "面积" in text and len(values) == 3 and re.search(r"上底.*下底.*高|下底.*上底.*高|上底.*高.*下底", text):
        upper, lower, height = values
        if min(upper, lower, height) >= 0:
            area = (upper + lower) * height / 2
            return _steps_for_formula(
                known=f"上底 = {_number_text(upper)}，下底 = {_number_text(lower)}，高 = {_number_text(height)}",
                formula="梯形面积 = (上底 + 下底) × 高 ÷ 2",
                rearranged="面积 = (上底 + 下底) × 高 ÷ 2",
                substitution=f"({_number_text(upper)} + {_number_text(lower)}) * {_number_text(height)} / 2",
                result=area,
                unit="平方单位",
                conclusion="梯形的面积",
                verification=f"({_number_text(upper)} + {_number_text(lower)}) × {_number_text(height)} ÷ 2 = {_number_text(area)}",
            )

    # Distance = speed × time. Require explicit semantic labels to avoid guessing number roles.
    if len(values) == 2 and re.search(r"速度|每小时|每分钟", text) and re.search(r"时间|小时|分钟", text) and re.search(r"路程|行驶多远|多少千米|多少米", text):
        speed, duration = values
        if speed >= 0 and duration >= 0:
            distance = speed * duration
            return _steps_for_formula(
                known=f"速度 = {_number_text(speed)}，时间 = {_number_text(duration)}",
                formula="路程 = 速度 × 时间",
                rearranged="路程 = 速度 × 时间",
                substitution=f"{_number_text(speed)} * {_number_text(duration)}",
                result=distance,
                unit="（按题目单位）",
                conclusion="行驶的路程",
                verification=f"{_number_text(distance)} ÷ {_number_text(duration) if duration else '时间'} = {_number_text(speed)}（速度复核）" if duration else "时间为0，路程也为0",
            )

    # Unit price × quantity = total price.
    if len(values) == 2 and re.search(r"单价|每支|每个|每本|每千克|每斤", text) and re.search(r"总价|一共.*元|共.*元|买了.*个|买.*支|买.*本", text):
        unit_price, quantity = values
        if unit_price >= 0 and quantity >= 0:
            total = unit_price * quantity
            return _steps_for_formula(
                known=f"单价 = {_number_text(unit_price)}，数量 = {_number_text(quantity)}",
                formula="总价 = 单价 × 数量",
                rearranged="总价 = 单价 × 数量",
                substitution=f"{_number_text(unit_price)} * {_number_text(quantity)}",
                result=total,
                unit="元",
                conclusion="需要支付的总价",
                verification=f"{_number_text(total)} ÷ {_number_text(quantity) if quantity else '数量'} = {_number_text(unit_price)}（单价复核）" if quantity else "数量为0，总价也为0",
            )

    # Average = sum / count; require explicit total and number of items.
    if len(values) == 2 and re.search(r"平均数|平均每人|平均每组|平均成绩", text) and re.search(r"总和|一共|总数|人数|个数据|几个人|几组", text):
        total, count = values
        if total >= 0 and count > 0:
            average = total / count
            return _steps_for_formula(
                known=f"总和 = {_number_text(total)}，份数 = {_number_text(count)}",
                formula="平均数 = 总和 ÷ 份数",
                rearranged="平均数 = 总和 ÷ 份数",
                substitution=f"{_number_text(total)} / {_number_text(count)}",
                result=average,
                unit="",
                conclusion="平均数",
                verification=f"{_number_text(average)} × {_number_text(count)} = {_number_text(total)}",
            )

    # Circle circumference / area with an explicit radius or diameter.
    if "圆" in text and len(values) == 1 and ("周长" in text or "面积" in text):
        measure = values[0]
        if measure >= 0 and "半径" in text:
            radius = measure
        elif measure >= 0 and "直径" in text:
            radius = measure / 2
        else:
            radius = None
        if radius is not None:
            if "周长" in text:
                result = 2 * 3.14 * radius
                formula = "圆周长 = 2 × 3.14 × 半径"
                substitution = f"2 * 3.14 * {_number_text(radius)}"
                unit = ""
                conclusion = "圆的周长（π按3.14近似计算）"
            else:
                result = 3.14 * radius * radius
                formula = "圆面积 = 3.14 × 半径 × 半径"
                substitution = f"3.14 * {_number_text(radius)} * {_number_text(radius)}"
                unit = "平方单位"
                conclusion = "圆的面积（π按3.14近似计算）"
            return _steps_for_formula(
                known=f"半径 = {_number_text(radius)}（π按3.14近似）",
                formula=formula,
                rearranged=formula,
                substitution=substitution,
                result=result,
                unit=unit,
                conclusion=conclusion,
                verification=f"按π≈3.14重新代入，结果为{_number_text(result)}",
            )

    # Square: one side is unknown, perimeter is known.
    if "正方形" in text and ("周长" in text or "一周" in text) and len(values) == 1 and re.search(r"求.*边长|边长.*多少", text):
        perimeter = values[0]
        if perimeter >= 0:
            side = perimeter / 4
            return _steps_for_formula(
                known=f"正方形周长 = {_number_text(perimeter)}",
                formula="周长 = 边长 × 4",
                rearranged="边长 = 周长 ÷ 4",
                substitution=f"{_number_text(perimeter)} / 4",
                result=side,
                unit="",
                conclusion="正方形的边长",
                verification=f"{_number_text(side)} × 4 = {_number_text(side * 4)}，与已知周长 {_number_text(perimeter)} 一致",
            )

    # Square area from side length.
    if "正方形" in text and "面积" in text and len(values) == 1 and re.search(r"求.*面积|面积.*多少", text):
        side = values[0]
        if side >= 0:
            area = side * side
            return _steps_for_formula(
                known=f"正方形边长 = {_number_text(side)}",
                formula="面积 = 边长 × 边长",
                rearranged="面积 = 边长的平方",
                substitution=f"{_number_text(side)} * {_number_text(side)}",
                result=area,
                unit="平方单位",
                conclusion="正方形的面积",
                verification=f"{_number_text(side)} × {_number_text(side)} = {_number_text(area)}",
            )

    # Rectangle: two values are length and width, order stated in the prompt.
    if "长方形" in text and len(values) == 2 and ("面积" in text or "周长" in text):
        length, width = values
        if length >= 0 and width >= 0:
            if "面积" in text:
                area = length * width
                return _steps_for_formula(
                    known=f"长 = {_number_text(length)}，宽 = {_number_text(width)}",
                    formula="长方形面积 = 长 × 宽",
                    rearranged="面积 = 长 × 宽",
                    substitution=f"{_number_text(length)} * {_number_text(width)}",
                    result=area,
                    unit="平方单位",
                    conclusion="长方形的面积",
                    verification=f"{_number_text(length)} × {_number_text(width)} = {_number_text(area)}",
                )
            perimeter = 2 * (length + width)
            return _steps_for_formula(
                known=f"长 = {_number_text(length)}，宽 = {_number_text(width)}",
                formula="长方形周长 = (长 + 宽) × 2",
                rearranged="周长 = (长 + 宽) × 2",
                substitution=f"({_number_text(length)} + {_number_text(width)}) * 2",
                result=perimeter,
                unit="",
                conclusion="长方形的周长",
                verification=f"({_number_text(length)} + {_number_text(width)}) × 2 = {_number_text(perimeter)}",
            )

    # Equal sharing / average distribution.
    if len(values) == 2 and re.search(r"平均分|每人|每组|分给|平分|平均分配", text):
        total, groups = values
        if groups > 0 and total >= 0 and total % groups == 0:
            result = total / groups
            return _steps_for_formula(
                known=f"总数 = {_number_text(total)}，平均分成 {_number_text(groups)} 份",
                formula="每份数量 = 总数 ÷ 份数",
                rearranged="每份数量 = 总数 ÷ 份数",
                substitution=f"{_number_text(total)} / {_number_text(groups)}",
                result=result,
                unit="",
                conclusion="每份的数量",
                verification=f"{_number_text(result)} × {_number_text(groups)} = {_number_text(total)}，与总数一致",
            )

    # Explicit arithmetic expression, e.g. 25+36÷4=?
    expression_match = re.search(r"(?<!\d)(\d+(?:\.\d+)?(?:\s*[+＋\-−×*÷/]\s*\d+(?:\.\d+)?){1,8})\s*(?:=\s*\?|等于几|是多少)?", text)
    if expression_match:
        expression = expression_match.group(1).replace("＋", "+").replace("−", "-").replace("×", "*").replace("÷", "/")
        try:
            result = _safe_arithmetic(expression)
            answer = _number_text(result)
            display_expression = expression.replace("*", " × ").replace("/", " ÷ ")
            return SolvedProblem(
                answer=answer,
                verification_status="verified",
                explanation="按照四则运算顺序，先算乘除，再算加减。",
                steps=[
                    SolvedStep(title="识别算式", explanation=f"题目给出的算式是 {display_expression}。", narration=f"先读出算式：{display_expression}。", visual_text=display_expression),
                    SolvedStep(title="按运算顺序计算", explanation="先计算乘法和除法，再计算加法和减法。", narration="根据四则混合运算规则，先算乘除，后算加减。", visual_text=display_expression),
                    SolvedStep(title="得到结果", explanation=f"计算结果为 {answer}。", narration=f"逐步计算后，结果等于 {answer}。", visual_text=f"{display_expression} = {answer}", expression=f"{expression} = {answer}"),
                    SolvedStep(title="检查结果", explanation=f"使用相同的运算顺序复核，结果为 {answer}。", narration=f"检查运算顺序和计算结果，答案是 {answer}。", visual_text=f"答案：{answer}"),
                ],
            )
        except (ValueError, SyntaxError, ZeroDivisionError):
            pass

    # Two-number word problems with explicit, conventional relation wording.
    if len(values) == 2:
        a, b = values
        operation = None
        label = ""
        symbol = ""
        if re.search(r"平均分|每人|每组|分给|平分|平均分配", text) and b > 0 and a % b == 0:
            operation, label, symbol = (a / b, "平均分配", "÷")
        elif re.search(r"每个.*有|几倍|倍数|每份.*个", text):
            operation, label, symbol = (a * b, "求相同数量的总和", "×")
        elif re.search(r"还剩|剩下|送给|用去|减少|拿走|吃掉", text):
            operation, label, symbol = (a - b, "从原有数量中减去变化的数量", "−")
        elif re.search(r"一共|总共|合起来|共有|共计", text):
            operation, label, symbol = (a + b, "把两部分数量合并", "+")
        if operation is not None:
            answer = _number_text(operation)
            expr = f"{_number_text(a)} {symbol} {_number_text(b)}"
            return SolvedProblem(
                answer=answer,
                verification_status="verified",
                explanation=f"题目中的数量关系明确：{label}。按对应运算计算并复核。",
                steps=[
                    SolvedStep(title="提取已知数量", explanation=f"题目中有 {_number_text(a)} 和 {_number_text(b)} 两个数量。", narration=f"先找出题目中的两个数量：{_number_text(a)} 和 {_number_text(b)}。", visual_text=f"{_number_text(a)}，{_number_text(b)}"),
                    SolvedStep(title="确定数量关系", explanation=f"根据题目描述，这是{label}，列式为 {expr}。", narration=f"题目说明{label}，所以列式：{expr}。", visual_text=expr),
                    SolvedStep(title="计算并验证", explanation=f"{expr} = {answer}。", narration=f"计算得到 {answer}。再用逆运算或总量关系检查，结果一致。", visual_text=f"{expr} = {answer}", expression=expr),
                ],
            )

    return SolvedProblem(
        explanation="当前本地解题规则无法可靠识别这道题的题型或数量关系。系统不会猜测答案；可以配置兼容 OpenAI Chat Completions 的模型服务，或人工补充条件。",
        steps=[
            SolvedStep(title="读懂题目", explanation=problem[:240], narration="先完整阅读题目，找出已知条件和需要回答的问题。", visual_text=problem[:80] or "请提供题目内容"),
            SolvedStep(title="整理已知条件", explanation="识别数字、单位、对象以及它们之间的关系。", narration="接下来需要整理题目中的数字、单位和数量关系。", visual_text="已知条件 → 数量关系"),
            SolvedStep(title="等待进一步分析", explanation="目前缺少可靠的解题依据，因此没有生成答案。", narration="当前规则无法可靠求解这道题，我们不会编造答案。", visual_text="暂无法可靠求解"),
        ],
    )


def _verify_model_answer(solved: SolvedProblem) -> SolvedProblem:
    """Only mark an LLM answer verified when its final arithmetic is independently reproducible."""
    if solved.answer is None or not solved.steps:
        solved.verification_status = "unverified"
        return solved
    expression = solved.steps[-1].expression
    if not expression or "=" not in expression:
        solved.verification_status = "unverified"
        return solved
    left_side, right_side = expression.split("=", 1)
    normalized = left_side.replace("×", "*").replace("÷", "/").replace("−", "-").replace("^", "**")
    try:
        computed = _safe_arithmetic(normalized.strip())
        expected = float(re.sub(r"[^0-9.\-]", "", right_side.strip()))
        answer_value = float(re.sub(r"[^0-9.\-]", "", solved.answer))
        valid = abs(computed - expected) < 1e-8 and abs(computed - answer_value) < 1e-8
        solved.verification_status = "verified" if valid else "unverified"
    except (ValueError, SyntaxError, ZeroDivisionError):
        solved.verification_status = "unverified"
    return solved


async def solve_problem(problem: str) -> SolvedProblem:
    local = _local_solution(problem)
    # Prefer deterministic local results for supported question types. The LLM
    # is an extension for unsupported questions, not a replacement for known rules.
    if local.verification_status == "verified":
        return local
    if not (settings.llm_base_url and settings.llm_model and settings.llm_api_key):
        return local

    endpoint = settings.llm_base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": settings.llm_model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": (
                "你是严谨的中小学数学解题助手。不得补造题目条件。只输出 JSON，字段为 answer（字符串或null）、"
                "verification_status（只能填unverified，不能自行宣称verified）、explanation、steps（2到8项）。"
                "每个step必须有title、explanation、narration、visual_text、expression（字符串或null）。"
                "每一步写清楚已知条件、公式、代入、计算和单位。最后一步expression必须是可独立计算的纯算术等式，"
                "例如 \"16 / 4 = 4\"。若题意不清或无法可靠求解，answer设为null并解释原因。"
            )},
            {"role": "user", "content": problem},
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(
                endpoint,
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json=payload,
            )
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        content = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", content)
        solved = SolvedProblem.model_validate(json.loads(content))
        return _verify_model_answer(solved)
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
        # A provider outage or malformed model response must not create fake content.
        return local


def to_scenes(solution: SolvedProblem, original_text: str) -> list[ExplanationScene]:
    visual_types = ["highlight", "step", "answer", "check"]
    scenes = [
        ExplanationScene(
            id=f"scene-{i + 1}",
            title=step.title,
            narration=step.narration,
            visual=visual_types[min(i, len(visual_types) - 1)],
            visual_text=step.visual_text,
            expression=step.expression,
        )
        for i, step in enumerate(solution.steps)
    ]
    scenes.insert(0, ExplanationScene(
        id="scene-0",
        title="题目呈现",
        narration="我们先完整读一遍题目，明确已知条件和所求问题。",
        visual="question",
        visual_text=original_text[:100],
    ))
    if solution.answer is not None and solution.verification_status == "verified":
        final_text = f"答案：{solution.answer}｜验证通过"
        final_narration = f"最终答案是{solution.answer}。并且已经通过计算验证。"
    elif solution.answer is not None:
        final_text = f"暂定结果：{solution.answer}｜尚未验证"
        final_narration = f"目前得到的结果是{solution.answer}，但解题依据尚未通过独立验证，请先核对。"
    else:
        final_text = "暂无法可靠求解｜不生成猜测答案"
        final_narration = "当前无法可靠确定答案。请补充题目条件或使用人工核对后的解法。"
    scenes.append(ExplanationScene(
        id="scene-check",
        title="答案与验证",
        narration=final_narration,
        visual="check",
        visual_text=final_text,
    ))
    return scenes
