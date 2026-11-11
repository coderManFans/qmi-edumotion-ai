import ast
import json
import math
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

    # --- Semantic, inverse and unit-aware rules (run before positional fallbacks). ---
    def labeled(label: str):
        match = re.search(rf"(?<!周){label}(?:是|为|有|等于|：|:)?(\d+(?:\.\d+)?)", text)
        return float(match.group(1)) if match else None

    if "正方形" in text and "面积" in text and re.search(r"(?:求|求出|计算)边长|边长是多少", text) and not re.search(r"平方(?:厘米|米|分米|毫米)", text):
        return SolvedProblem(
            answer=None, verification_status="unverified",
            explanation="题目没有说明面积单位，无法给出完整的长度单位答案。",
            steps=[
                SolvedStep(title="提取条件", explanation="只知道正方形面积的数值，未给面积单位。", narration="题目没有说明面积单位。", visual_text="面积单位缺失"),
                SolvedStep(title="检查单位", explanation="面积单位与边长单位相关，缺少单位信息。", narration="即使能求出边长数值，也无法确定它应使用什么长度单位。", visual_text="单位信息不足"),
                SolvedStep(title="暂不作答", explanation="需要补充面积单位。", narration="请补充面积单位后再计算。", visual_text="等待补充单位"),
            ],
        )

    # Reverse geometry: known area and one dimension.
    if "正方形" in text and "面积" in text and re.search(r"(?:求|求出|计算)边长|边长是多少", text):
        area = labeled("面积")
        if area is not None and area >= 0:
            side = math.sqrt(area)
            if math.isclose(side, round(side), abs_tol=1e-9):
                side = round(side)
                unit = "厘米" if "厘米" in text else "米" if "米" in text else ""
                return _steps_for_formula(
                    known=f"正方形面积 = {_number_text(area)}平方{unit or '单位'}",
                    formula="面积 = 边长 × 边长",
                    rearranged="边长 = √面积",
                    substitution=f"√{_number_text(area)}",
                    result=side, unit=unit, conclusion="正方形的边长",
                    verification=f"{_number_text(side)} × {_number_text(side)} = {_number_text(area)}，与已知面积相符",
                )

    if "长方形" in text and "面积" in text and re.search(r"宽.*多少|求.*宽|长.*多少|求.*长", text):
        area = labeled("面积")
        length = labeled("长")
        width = labeled("宽")
        if area is not None and length is not None and width is None and length > 0 and area >= 0:
            result = area / length
            unit = "厘米" if "厘米" in text else "米" if "米" in text else ""
            return _steps_for_formula(
                known=f"面积 = {_number_text(area)}平方{unit or '单位'}，长 = {_number_text(length)}{unit}",
                formula="长方形面积 = 长 × 宽",
                rearranged="宽 = 面积 ÷ 长",
                substitution=f"{_number_text(area)} ÷ {_number_text(length)}",
                result=result, unit=unit, conclusion="长方形的宽",
                verification=f"{_number_text(length)} × {_number_text(result)} = {_number_text(area)}，与已知面积相符",
            )
        if area is not None and width is not None and length is None and width > 0 and area >= 0:
            result = area / width
            unit = "厘米" if "厘米" in text else "米" if "米" in text else ""
            return _steps_for_formula(
                known=f"面积 = {_number_text(area)}平方{unit or '单位'}，宽 = {_number_text(width)}{unit}",
                formula="长方形面积 = 长 × 宽",
                rearranged="长 = 面积 ÷ 宽",
                substitution=f"{_number_text(area)} ÷ {_number_text(width)}",
                result=result, unit=unit, conclusion="长方形的长",
                verification=f"{_number_text(result)} × {_number_text(width)} = {_number_text(area)}，与已知面积相符",
            )

    # Rectangle perimeter -> missing side -> area is a two-step problem.
    if "长方形" in text and "周长" in text and "面积" in text:
        perimeter, length, width = labeled("周长"), labeled("长"), labeled("宽")
        if perimeter is not None and length is not None and width is None:
            width = perimeter / 2 - length
            if width >= 0:
                area = length * width
                unit = "厘米" if "厘米" in text else "米" if "米" in text else ""
                return SolvedProblem(
                    answer=f"{_number_text(area)}平方{unit or '单位'}",
                    verification_status="verified",
                    explanation="先由周长求出未知的宽，再用长乘宽求面积。",
                    steps=[
                        SolvedStep(title="提取条件", explanation=f"周长={_number_text(perimeter)}，长={_number_text(length)}", narration=f"已知长方形周长{_number_text(perimeter)}{unit}，长{_number_text(length)}{unit}。", visual_text=f"周长 {_number_text(perimeter)}；长 {_number_text(length)}"),
                        SolvedStep(title="先求宽", explanation="宽=周长÷2−长", narration="长方形的周长等于长和宽之和的2倍，所以先用周长除以2，再减去长。", visual_text=f"{_number_text(perimeter)} ÷ 2 − {_number_text(length)} = {_number_text(width)}"),
                        SolvedStep(title="再求面积", explanation="面积=长×宽", narration=f"现在知道宽是{_number_text(width)}{unit}，再用长乘宽。", visual_text=f"{_number_text(length)} × {_number_text(width)} = {_number_text(area)}"),
                        SolvedStep(title="验证", explanation=f"({_number_text(length)}+{_number_text(width)})×2={_number_text(perimeter)}；长×宽={_number_text(area)}", narration="把长和宽代回周长公式，周长正确；再计算面积，得到最终答案。", visual_text=f"答案：{_number_text(area)}平方{unit or '单位'}"),
                    ],
                )

    # Inverse unit-price relation: total price / unit price = quantity.
    if re.search(r"数量|几支|几个|几本|多少支|多少个|多少本", text) and re.search(r"总价|一共|共计", text):
        total, price = labeled("总价"), labeled("单价")
        if total is not None and price is not None and price > 0 and total >= 0:
            quantity = total / price
            if math.isclose(quantity, round(quantity), abs_tol=1e-9):
                quantity = round(quantity)
                return _steps_for_formula(
                    known=f"总价 = {_number_text(total)}元，单价 = {_number_text(price)}元",
                    formula="总价 = 单价 × 数量",
                    rearranged="数量 = 总价 ÷ 单价",
                    substitution=f"{_number_text(total)} ÷ {_number_text(price)}",
                    result=quantity, unit=("支" if "支" in text else "本" if "本" in text else "个" if "个" in text else "件"), conclusion="购买的数量",
                    verification=f"{_number_text(price)} × {_number_text(quantity)} = {_number_text(total)}元",
                )

    # Inverse travel relation: time = distance / speed.
    if re.search(r"时间|几小时|多少小时|需要多久", text) and re.search(r"路程|距离", text) and re.search(r"速度|每小时|千米/小时|公里/小时", text):
        distance, speed = labeled("路程"), labeled("速度")
        if distance is not None and speed is not None and speed > 0 and distance >= 0:
            time_value = distance / speed
            return _steps_for_formula(
                known=f"路程 = {_number_text(distance)}，速度 = {_number_text(speed)}",
                formula="路程 = 速度 × 时间",
                rearranged="时间 = 路程 ÷ 速度",
                substitution=f"{_number_text(distance)} ÷ {_number_text(speed)}",
                result=time_value, unit="小时", conclusion="行驶时间",
                verification=f"{_number_text(speed)} × {_number_text(time_value)} = {_number_text(distance)}",
            )

    # Fraction word problems: explicitly identify the whole and the fraction.
    fraction_match = re.search(r"(?:一个数|这本书|全程|全班|总数|原有量)?的?(\d+)\s*/\s*(\d+)是(\d+(?:\.\d+)?)", text)
    if fraction_match and re.search(r"这个数|原来|总数|全程|一共|整体", text):
        numerator, denominator, part = map(float, fraction_match.groups())
        if denominator > 0 and 0 < numerator <= denominator:
            whole = part * denominator / numerator
            return _steps_for_formula(
                known=f"对应分率 = {_number_text(numerator)}/{_number_text(denominator)}，对应部分量 = {_number_text(part)}",
                formula="部分量 = 单位“1” × 对应分率",
                rearranged="单位“1” = 部分量 ÷ 对应分率",
                substitution=f"{_number_text(part)} ÷ ({_number_text(numerator)}/{_number_text(denominator)})",
                result=whole, unit="", conclusion="单位“1”所表示的整体量",
                verification=f"{_number_text(whole)} × {_number_text(numerator)}/{_number_text(denominator)} = {_number_text(part)}",
            )

    # Percentage: find the whole when a known percentage of it is given.
    percent_whole = re.search(r"(?:一个数|原价|原来|原有量)?的?(\d+(?:\.\d+)?)%是(\d+(?:\.\d+)?)", text)
    if percent_whole and re.search(r"这个数|原来|原价|原有量|单位1|整体", text):
        rate, part = map(float, percent_whole.groups())
        if 0 < rate <= 100:
            whole = part / (rate / 100)
            return _steps_for_formula(
                known=f"对应百分率 = {_number_text(rate)}%，对应部分量 = {_number_text(part)}",
                formula="部分量 = 整体量 × 百分率",
                rearranged="整体量 = 部分量 ÷ 百分率",
                substitution=f"{_number_text(part)} ÷ {_number_text(rate / 100)}",
                result=whole, unit="", conclusion="原来的整体量（单位“1”）",
                verification=f"{_number_text(whole)} × {_number_text(rate)}% = {_number_text(part)}",
            )

    # Direct fraction/percentage of an explicitly named whole.
    direct_fraction = re.search(r"(\d+(?:\.\d+)?)的(\d+)\s*/\s*(\d+)(?:是多少|是几)", text)
    if direct_fraction:
        whole, numerator, denominator = map(float, direct_fraction.groups())
        if denominator > 0 and 0 <= numerator <= denominator:
            part = whole * numerator / denominator
            return _steps_for_formula(
                known=f"单位“1” = {_number_text(whole)}，对应分率 = {_number_text(numerator)}/{_number_text(denominator)}",
                formula="部分量 = 单位“1” × 对应分率",
                rearranged="部分量 = 单位“1” × 对应分率",
                substitution=f"{_number_text(whole)} × {_number_text(numerator)}/{_number_text(denominator)}",
                result=part, unit="", conclusion="对应的部分量",
                verification=f"{_number_text(part)} ÷ {_number_text(whole)} = {_number_text(numerator / denominator)}",
            )

    # Unit conversion with dimensional safeguards.
    unit_groups = {
        "length": {"千米":1000.0,"公里":1000.0,"米":1.0,"分米":0.1,"厘米":0.01,"毫米":0.001},
        "area": {"平方千米":1_000_000.0,"公顷":10_000.0,"平方米":1.0,"平方分米":0.01,"平方厘米":0.0001,"平方毫米":0.000001},
        "volume": {"立方米":1.0,"立方分米":0.001,"立方厘米":0.000001,"升":0.001,"毫升":0.000001},
        "time": {"小时":3600.0,"分钟":60.0,"秒":1.0},
        "mass": {"吨":1000.0,"千克":1.0,"公斤":1.0,"克":0.001},
    }
    conversion_match = re.search(r"(\d+(?:\.\d+)?)\s*(平方千米|平方分米|平方厘米|平方毫米|平方米|公顷|立方米|立方分米|立方厘米|千米|公里|分米|厘米|毫米|米|小时|分钟|秒|吨|千克|公斤|克|升|毫升)", text)
    target_match = re.search(r"(?:换算成|化成|等于多少|是多少)(平方千米|平方分米|平方厘米|平方毫米|平方米|公顷|立方米|立方分米|立方厘米|千米|公里|分米|厘米|毫米|米|小时|分钟|秒|吨|千克|公斤|克|升|毫升)", text)
    if conversion_match and target_match:
        amount = float(conversion_match.group(1))
        source_unit, target_unit = conversion_match.group(2), target_match.group(1)
        dimension = next((key for key, units in unit_groups.items() if source_unit in units), None)
        target_dimension = next((key for key, units in unit_groups.items() if target_unit in units), None)
        if dimension and dimension == target_dimension:
            converted = amount * unit_groups[dimension][source_unit] / unit_groups[dimension][target_unit]
            return _steps_for_formula(
                known=f"{_number_text(amount)}{source_unit}",
                formula=f"1{source_unit} = {unit_groups[dimension][source_unit] / unit_groups[dimension][target_unit]:g}{target_unit}",
                rearranged=f"目标数值 = 原数值 × 单位进率",
                substitution=f"{_number_text(amount)} × {unit_groups[dimension][source_unit] / unit_groups[dimension][target_unit]:g}",
                result=converted, unit=target_unit, conclusion="换算后的数量",
                verification=f"{_number_text(converted)}{target_unit}换回{source_unit}等于{_number_text(amount)}{source_unit}",
            )
        # Explicitly reject incompatible dimensions rather than guessing.
        if dimension and target_dimension and dimension != target_dimension:
            return SolvedProblem(
                answer=None, verification_status="unverified",
                explanation="题目给出的原单位和目标单位不属于同一量纲，无法直接换算。",
                steps=[
                    SolvedStep(title="识别原单位", explanation=f"原单位是{source_unit}，属于{dimension}。", narration=f"先识别原单位{source_unit}。", visual_text=source_unit),
                    SolvedStep(title="识别目标单位", explanation=f"目标单位是{target_unit}，属于{target_dimension}。", narration=f"目标单位是{target_unit}，它与原单位量纲不同。", visual_text=target_unit),
                    SolvedStep(title="停止不合理换算", explanation="不能把不同量纲的单位直接换算。", narration="这两个单位不能直接互换，请检查题目。", visual_text="单位量纲不一致"),
                ],
            )

    # Multi-step equal groups followed by a change (e.g. boxes, packets, sharing).
    multi = re.search(r"(\d+)箱.*每箱(\d+)(?:瓶|个|本|支).*?(?:卖出|用去|拿走|送出)(\d+).*?(?:还剩|剩下)", text)
    if multi:
        groups, each, removed = map(float, multi.groups())
        total = groups * each
        remaining = total - removed
        if remaining >= 0:
            return SolvedProblem(
                answer=_number_text(remaining), verification_status="verified",
                explanation="先求若干相同包装的总数，再减去用去的数量。",
                steps=[
                    SolvedStep(title="提取条件", explanation=f"箱数={_number_text(groups)}，每箱={_number_text(each)}，卖出={_number_text(removed)}", narration="先整理箱数、每箱数量和卖出的数量。", visual_text=f"{_number_text(groups)}箱 × 每箱{_number_text(each)}"),
                    SolvedStep(title="求原有总数", explanation="总数=箱数×每箱数量", narration="先求一共有多少，再考虑卖出了多少。", visual_text=f"{_number_text(groups)} × {_number_text(each)} = {_number_text(total)}"),
                    SolvedStep(title="求剩余数量", explanation="剩余=原有总数−卖出数量", narration=f"再从总数{_number_text(total)}中减去卖出的{_number_text(removed)}。", visual_text=f"{_number_text(total)} − {_number_text(removed)} = {_number_text(remaining)}"),
                    SolvedStep(title="验证", explanation=f"{_number_text(remaining)}+{_number_text(removed)}={_number_text(total)}", narration="把剩余数量和卖出数量加起来，能还原原有总数。", visual_text=f"答案：{_number_text(remaining)}"),
                ],
            )


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
    if len(values) == 2 and re.search(r"速度|每小时|每分钟", text) and re.search(r"时间|小时|分钟", text) and re.search(r"求路程|路程是多少|行驶多远|多少千米|多少米", text) and not re.search(r"求速度|速度是多少|求时间|时间是多少|需要多久", text):
        speed, duration = values
        if speed >= 0 and duration >= 0:
            distance = speed * duration
            return _steps_for_formula(
                known=f"速度 = {_number_text(speed)}，时间 = {_number_text(duration)}",
                formula="路程 = 速度 × 时间",
                rearranged="路程 = 速度 × 时间",
                substitution=f"{_number_text(speed)} * {_number_text(duration)}",
                result=distance,
                unit=("千米" if "千米" in text or "公里" in text else "米" if "米" in text else ""),
                conclusion="行驶的路程",
                verification=f"{_number_text(distance)} ÷ {_number_text(duration)} = {_number_text(speed)}（速度复核）" if duration else "时间为0，路程也为0",
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

    # Percentage of a known whole: e.g. 200的20%是多少.
    direct_percent = re.search(r"(\d+(?:\.\d+)?)的(\d+(?:\.\d+)?)%", text)
    if direct_percent and re.search(r"是多少|求.*多少", text) and not ("涨价" in text and "降价" in text):
        whole = float(direct_percent.group(1))
        percent_match = re.search(r"(\d+(?:\.\d+)?)%", text)
        if percent_match:
            rate = float(percent_match.group(1)) / 100
        else:
            chinese_rate = re.search(r"百分之(\d+(?:\.\d+)?)", text)
            rate = float(chinese_rate.group(1)) / 100 if chinese_rate else None
        if rate is not None and whole >= 0 and 0 <= rate <= 1:
            result = whole * rate
            return _steps_for_formula(
                known=f"整体量 = {_number_text(whole)}，百分率 = {_number_text(rate * 100)}%",
                formula="部分量 = 整体量 × 百分率",
                rearranged="部分量 = 整体量 × 百分率",
                substitution=f"{_number_text(whole)} * {_number_text(rate)}",
                result=result,
                unit="",
                conclusion="对应的部分量",
                verification=f"{_number_text(result)} ÷ {_number_text(whole) if whole else '整体量'} = {_number_text(rate * 100)}%" if whole else "整体量为0，部分量也为0",
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
    compact = re.sub(r"\s+", "", original_text)
    if "正方形" in compact:
        knowledge_visual = "knowledge_square"
    elif "长方形" in compact:
        knowledge_visual = "knowledge_rectangle"
    elif any(token in compact for token in ("行程", "速度", "路程", "千米/小时", "公里/小时")):
        knowledge_visual = "knowledge_journey"
    elif any(token in compact for token in ("平均分", "每人", "分给", "平分")):
        knowledge_visual = "knowledge_sharing"
    elif "/" in compact or "分数" in compact:
        knowledge_visual = "knowledge_fraction"
    elif "%" in compact or "百分之" in compact or "折扣" in compact:
        knowledge_visual = "knowledge_percentage"
    elif any(token in compact for token in ("换算", "等于多少平方", "等于多少立方")):
        knowledge_visual = "knowledge_conversion"
    else:
        knowledge_visual = "step"
    scenes = [
        ExplanationScene(
            id=f"scene-{i + 1}",
            title=step.title,
            narration=step.narration,
            visual=knowledge_visual if knowledge_visual != "step" else visual_types[min(i, len(visual_types) - 1)],
            visual_text=step.visual_text,
            expression=step.expression,
        )
        for i, step in enumerate(solution.steps)
    ]
    scenes.insert(0, ExplanationScene(
        id="scene-0",
        title="题目呈现",
        narration="我们先完整读一遍题目，明确已知条件和所求问题。",
        visual=knowledge_visual if knowledge_visual != "step" else "question",
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
