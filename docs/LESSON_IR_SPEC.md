# EduMotion AI 教学中间表示规范（LESSON_IR_SPEC）

-   文档版本：1.0
-   Schema 版本：1.0
-   状态：MVP 设计基线
-   核心对象：Lesson IR（Instructional Representation）

------------------------------------------------------------------------

## 1. 设计目标

Lesson IR
是题目理解、教学策划与最终渲染之间的稳定契约。它不是某个视频引擎的脚本，而是对"教什么、怎么讲、每一步展示什么"的结构化描述。

同一份 IR 应至少支持： - Web 可滚动交互式图解。 - Manim 数学动画。 -
图片/绘本式故事视频。 - TTS 旁白与字幕。 - 后续新增的
PPT、H5、其他视频引擎。

### 1.1 核心原则

1.  **内容与渲染分离**：IR 描述教学语义，不直接包含可执行代码。
2.  **结构化与可校验**：所有字段有类型、枚举、约束和版本。
3.  **场景化**：课程由有序 scenes 组成。
4.  **可追溯**：结论、答案、故事事实可引用原题或原文片段。
5.  **可编辑**：场景可独立修改、锁定和重渲染。
6.  **可扩展**：新组件和动画类型通过注册表增加。
7.  **可降级**：未知组件可显示通用文本卡片，不应整课崩溃。
8.  **安全**：禁止 IR 携带任意 Python、Shell、JS 执行代码。

------------------------------------------------------------------------

## 2. 顶层数据结构

``` json
{
  "schema_version": "1.0",
  "lesson_id": "lesson_01",
  "version": 1,
  "locale": "zh-CN",
  "subject": "math",
  "grade": {
    "stage": "primary",
    "level": "grade_1",
    "label": "小学一年级",
    "confidence": 0.82,
    "source": "user_or_model"
  },
  "title": "苹果的数量变化",
  "learning_objectives": [],
  "source_material": {},
  "question": {},
  "solution": {},
  "style": {},
  "scenes": [],
  "quality": {},
  "render_preferences": {},
  "metadata": {}
}
```

### 2.1 顶层字段

  字段                  类型        必需 说明
  --------------------- --------- ------ -------------------------
  schema_version        string        是 IR Schema 版本
  lesson_id             string        是 教学内容 ID
  version               integer       是 IR 版本号，从 1 开始
  locale                string        是 默认 zh-CN
  subject               enum          是 学科
  grade                 object        否 年级/学段，可由用户确认
  title                 string        是 教学标题
  learning_objectives   array         是 教学目标
  source_material       object        是 原始题目/文章来源
  question              object        是 题目内容
  solution              object        否 答案与解题过程
  style                 object        是 视觉风格
  scenes                array         是 有序场景，至少一个
  quality               object        是 验证与审核状态
  render_preferences    object        是 输出偏好
  metadata              object        否 创建时间、模型等

### 2.2 学科枚举

-   `math`
-   `chinese`
-   `english`
-   `science`
-   `history`
-   `geography`
-   `general`

学段枚举： - `primary` - `junior_middle` - `senior_middle` - `unknown`

年级未知时必须使用 `unknown`，不可根据模型猜测后伪装成用户确认值。

------------------------------------------------------------------------

## 3. 原始材料、题目与证据

### 3.1 source_material

``` json
{
  "type": "text",
  "original_text": "小红有12个苹果，送给小明4个，还剩多少个？",
  "normalized_text": "小红有12个苹果，送给小明4个，还剩多少个？",
  "assets": [],
  "paragraphs": [
    {
      "id": "p1",
      "text": "小红有12个苹果，送给小明4个，还剩多少个？"
    }
  ]
}
```

`type` 可为： - `text` - `image` - `pdf` - `mixed`

### 3.2 question

``` json
{
  "content": "小红有12个苹果，送给小明4个，还剩多少个？",
  "question_type": "word_problem",
  "sub_questions": [],
  "entities": [
    {
      "id": "e1",
      "name": "小红",
      "entity_type": "person"
    },
    {
      "id": "e2",
      "name": "苹果",
      "entity_type": "object"
    }
  ]
}
```

### 3.3 证据引用 EvidenceRef

``` json
{
  "source_id": "p1",
  "quote": "小红有12个苹果",
  "start_offset": 0,
  "end_offset": 9,
  "evidence_type": "explicit"
}
```

`evidence_type`： - `explicit`：原文明确陈述。 -
`inferred`：基于原文推断。 - `external`：来自外部知识或教材知识库。

语文事实、人物行为和阅读理解答案尽量附
evidence。没有证据的内容应标为推断或待审核。

------------------------------------------------------------------------

## 4. 解题与教学目标结构

### 4.1 solution

``` json
{
  "answer": {
    "value": "8个",
    "display": "8个苹果",
    "unit": "个",
    "confidence": 1.0
  },
  "steps": [
    {
      "id": "step_1",
      "description": "原来有12个苹果",
      "expression": null,
      "result": null,
      "evidence": []
    },
    {
      "id": "step_2",
      "description": "送出4个苹果",
      "expression": "12 - 4",
      "result": "8",
      "evidence": []
    }
  ],
  "knowledge_points": [
    {
      "id": "kp_subtraction",
      "name": "减法",
      "description": "从总量中去掉一部分，求剩余量"
    }
  ]
}
```

数学表达式必须由适当的计算工具或规则验证。LLM 给出的 `confidence`
不能替代确定性验证。

### 4.2 learning_objectives

每项包括： - `id` - `text` - `level`：`understand`、`apply`、`analyze` -
可选 `knowledge_point_id`

------------------------------------------------------------------------

## 5. Scene 场景规范

### 5.1 Scene 基础结构

``` json
{
  "id": "scene_001",
  "order": 1,
  "type": "counting",
  "title": "原来的苹果",
  "duration_ms": 5000,
  "narration": {
    "text": "小红原来有12个苹果。",
    "voice_id": "zh_female_teacher_01",
    "speed": 1.0,
    "subtitle": true
  },
  "visual": {
    "component": "apple_group",
    "props": {
      "count": 12
    },
    "assets": []
  },
  "animation": {
    "type": "appear",
    "duration_ms": 1200,
    "easing": "ease_out",
    "params": {}
  },
  "annotations": [],
  "evidence": [],
  "render": {
    "web": true,
    "video": true
  },
  "locked": false
}
```

### 5.2 Scene 字段

  字段          类型      说明
  ------------- --------- ---------------------
  id            string    场景稳定 ID
  order         integer   场景顺序
  type          enum      场景语义类型
  title         string    场景标题
  duration_ms   integer   目标时长，毫秒
  narration     object    旁白与字幕
  visual        object    视觉组件与参数
  animation     object    动画指令
  annotations   array     标注、箭头、重点
  evidence      array     内容证据
  render        object    是否输出到 Web/视频
  locked        boolean   是否锁定场景

### 5.3 Scene 类型枚举

基础类型： - `intro`：课程开场。 - `text`：文本讲解。 -
`image`：图片展示。 - `counting`：数量展示。 -
`operation`：数学运算过程。 - `equation`：公式。 -
`number_line`：数轴。 - `geometry`：几何图形。 -
`diagram`：通用关系图。 - `story`：故事场景。 -
`character`：人物介绍。 - `timeline`：时间线。 -
`experiment`：科学实验/过程。 - `knowledge_card`：知识点卡片。 -
`question`：互动提问。 - `summary`：总结。 - `answer`：答案揭示。

------------------------------------------------------------------------

## 6. Visual Component 注册表

IR 的 `visual.component` 必须来自允许列表。组件参数需要各自的 Pydantic
Schema。

### 6.1 数学组件

  component           主要 props                     用途
  ------------------- ------------------------------ --------------
  `apple_group`       count、removed、label          物体数量
  `object_group`      object_name、count、layout     通用对象数量
  `math_equation`     expression、highlight_tokens   公式和步骤
  `number_line`       min、max、markers、jumps       数轴
  `geometry_shape`    shape、dimensions、labels      几何
  `bar_model`         segments、labels、values       线段图
  `unit_conversion`   from_unit、to_unit、value      单位换算
  `table`             columns、rows                  数据表

### 6.2 语文/故事组件

  component           主要 props                        用途
  ------------------- --------------------------------- --------------
  `story_scene`       background、characters、action    故事场景
  `story_character`   character_id、pose、expression    人物
  `dialogue_bubble`   speaker、text                     对话气泡
  `story_map`         locations、path                   故事地点关系
  `paragraph_card`    paragraph_id、text、highlights    原文段落
  `evidence_card`     question、answer、evidence_refs   阅读理解依据

### 6.3 通用组件

-   `title_card`
-   `text_block`
-   `image_panel`
-   `highlight_text`
-   `arrow`
-   `label`
-   `timeline`
-   `knowledge_card`
-   `quiz_card`

### 6.4 组件安全规则

-   禁止 `component` 指向任意模块路径。
-   禁止 props 中包含可执行代码。
-   限制图片 URL 来源和本地文件访问范围。
-   对文字长度、数组长度、场景数量、渲染尺寸设置上限。
-   未知组件降级显示通用文本/图片卡片，并写入 warning。

------------------------------------------------------------------------

## 7. Animation 指令规范

### 7.1 基础结构

``` json
{
  "type": "highlight",
  "duration_ms": 1000,
  "delay_ms": 0,
  "easing": "ease_in_out",
  "params": {
    "target": "answer"
  }
}
```

### 7.2 动画类型

  type            用途             典型参数
  --------------- ---------------- ----------------
  `none`          静态展示         无
  `appear`        出现             opacity、scale
  `fade`          淡入淡出         direction
  `move`          位移             from、to
  `remove`        移除/消失        target_ids
  `highlight`     高亮             target
  `count_up`      数字递增         from、to
  `draw`          绘制线条/图形    path_id
  `transform`     图形变换         target、to
  `camera_pan`    镜头平移         from、to
  `camera_zoom`   镜头缩放         scale
  `reveal`        逐步揭示         target
  `typewriter`    逐字显示         speed
  `pulse`         强调闪动         repeat
  `sequence`      多动画顺序组合   children

### 7.3 缓动函数白名单

-   `linear`
-   `ease_in`
-   `ease_out`
-   `ease_in_out`
-   `bounce_out`

不允许从 IR 传入 JavaScript 函数或任意表达式。

### 7.4 动画时间规则

-   所有时间统一使用毫秒。
-   `duration_ms` 必须在服务端配置的上下限内。
-   动画时长不应超过场景时长，除非明确允许并发。
-   Web 与视频端可以使用不同实现，但必须保持语义一致。
-   视频渲染以时间轴为准；Web 端可根据滚动和用户操作播放。

------------------------------------------------------------------------

## 8. 旁白、字幕和音频

### 8.1 narration

字段： - `text`：旁白文本。 - `voice_id`：语音角色。 - `speed`：语速。 -
`subtitle`：是否显示字幕。 - `audio_asset_id`：TTS
完成后关联音频资源。 - `start_ms`：场景内音频起始时间，可选。

### 8.2 字幕分段

建议后续增加 `subtitle_segments`：

``` json
[
  {
    "start_ms": 0,
    "end_ms": 1800,
    "text": "小红原来有12个苹果。"
  }
]
```

MVP 可以先按场景生成整段旁白，后续再通过 ASR/强制对齐或 TTS
时间戳实现逐句同步。

------------------------------------------------------------------------

## 9. 视觉风格与渲染偏好

### 9.1 style

``` json
{
  "theme": "cartoon",
  "palette": "warm",
  "font_family": "Noto Sans CJK SC",
  "aspect_ratio": "16:9",
  "background": "#FFF9ED",
  "density": "comfortable"
}
```

主题枚举： - `cartoon` - `storybook` - `blackboard` - `minimal` -
`scientific` - `watercolor`

### 9.2 render_preferences

``` json
{
  "outputs": ["web", "video"],
  "video": {
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "format": "mp4",
    "subtitle_mode": "burn_in"
  },
  "web": {
    "scroll_mode": "scene_by_scene",
    "show_navigation": true,
    "autoplay_narration": false
  }
}
```

------------------------------------------------------------------------

## 10. 质量状态与审核

``` json
{
  "quality": {
    "schema_valid": true,
    "answer_status": "verified",
    "content_status": "needs_review",
    "warnings": [],
    "checks": [
      {
        "name": "math_expression",
        "status": "passed",
        "detail": "12 - 4 = 8"
      }
    ]
  }
}
```

状态枚举： - `passed` - `failed` - `warning` - `not_checked` -
`needs_review`

答案状态： - `verified` - `unverified` - `incorrect` - `not_applicable`

语文内容状态： - `verified` - `needs_review` - `inconsistent`

未通过关键验证时，不应标记为"已验证"，也不应默认自动发布。

------------------------------------------------------------------------

## 11. Pydantic 模型建议

建议代码放在
`backend/app/schemas/lesson_ir.py`，所有模型设置严格字段校验。

``` python
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, ConfigDict

class Subject(str, Enum):
    MATH = "math"
    CHINESE = "chinese"
    ENGLISH = "english"
    SCIENCE = "science"
    GENERAL = "general"

class AnimationType(str, Enum):
    NONE = "none"
    APPEAR = "appear"
    FADE = "fade"
    MOVE = "move"
    REMOVE = "remove"
    HIGHLIGHT = "highlight"
    COUNT_UP = "count_up"
    DRAW = "draw"
    CAMERA_PAN = "camera_pan"
    CAMERA_ZOOM = "camera_zoom"
    REVEAL = "reveal"
    TYPEWRITER = "typewriter"
    PULSE = "pulse"

class AnimationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: AnimationType
    duration_ms: int = Field(default=1000, ge=0, le=30000)
    delay_ms: int = Field(default=0, ge=0, le=30000)
    easing: str = "ease_in_out"
    params: dict[str, Any] = Field(default_factory=dict)

class VisualSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    component: str
    props: dict[str, Any] = Field(default_factory=dict)
    assets: list[str] = Field(default_factory=list)

class NarrationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    voice_id: str | None = None
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    subtitle: bool = True

class Scene(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    order: int = Field(ge=0)
    type: str
    title: str
    duration_ms: int = Field(ge=500, le=120000)
    narration: NarrationSpec
    visual: VisualSpec
    animation: AnimationSpec
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    locked: bool = False
```

注意：上面的代码是基础示意。生产实现还需要对 `visual.component` 与对应
props 使用 discriminated union 或注册表 Schema 校验，不能只检查
component 是字符串。

------------------------------------------------------------------------

## 12. 版本兼容与迁移

-   每份 IR 必须有 `schema_version`。
-   `version` 表示同一 lesson 的内容版本，不等于 schema 版本。
-   Schema 升级时提供显式 migration 函数。
-   历史 IR 原样保留，不做原地覆盖。
-   Renderer 声明支持的 schema 版本。
-   不支持的版本应拒绝渲染并提示迁移，而不是静默丢字段。

建议： - `1.0`：基础场景、视觉组件、动画、旁白。 -
`1.1`：字幕时间轴、交互题、原文证据。 -
`1.2`：多语言、更多学科组件、分支式讲解。

------------------------------------------------------------------------

## 13. IR 验收测试

至少覆盖： 1. 合法数学 IR 能通过校验。 2. 合法语文故事 IR 能通过校验。
3. 缺少必需字段时拒绝。 4. 未知动画类型拒绝或按策略降级。 5.
未知视觉组件产生 warning 并安全降级。 6.
超长旁白、超多场景和超大资源引用被限制。 7. Web Renderer 与 Video
Renderer 对场景顺序保持一致。 8. 语文 evidence 引用的 paragraph_id
必须存在。 9. 数学答案状态与验证结果一致。 10. Schema migration
能将旧版本转换为新版本。