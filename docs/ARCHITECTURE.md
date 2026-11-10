# EduMotion AI 系统架构设计（ARCHITECTURE）

> **当前实现进度说明（2026-11-10）**：当前主流程为题目导入 → 文本提取 → LLM/规则求解 → 分镜 → Pillow 动画帧 → FFmpeg MP4。LLM 通过 OpenAI-compatible Chat Completions 配置；视频渲染已提供同步 MVP API。Celery/Redis 持久化任务、TTS 配音、扫描 PDF OCR 和对象存储迁移仍是后续架构目标。课程/项目域不是当前主流程的交付重点。

-   文档版本：1.0
-   架构风格：模块化单体 + 异步 Worker
-   部署策略：本地优先，云端可迁移
-   前端：Vue 3 + TypeScript
-   后端：Python + FastAPI

------------------------------------------------------------------------

## 1. 架构目标与约束

### 1.1 目标

-   一次题目理解，生成统一 Lesson IR。
-   Web 图解与 MP4 共用 IR。
-   AI Provider、OCR、TTS、Storage、Renderer 可替换。
-   长耗时任务异步执行。
-   渲染与 API 服务隔离，避免视频任务阻塞接口。
-   本地开发易启动，未来可迁移云端。
-   支持失败重试、版本管理、人工审核和资源追踪。

### 1.2 MVP 架构决策

采用模块化单体，而不是微服务： - FastAPI 提供 HTTP API。 - Celery Worker
处理耗时任务。 - PostgreSQL 保存业务数据。 - Redis 作为 Celery
Broker/Result Backend（任务状态以数据库为准）。 -
本地文件系统保存资源。 - Manim、FFmpeg 在独立 Worker/子进程中执行。 -
ComfyUI 作为可选外部服务，第二阶段接入。

------------------------------------------------------------------------

## 2. 逻辑架构

``` mermaid
flowchart TB
    FE["Vue 3 Web App"]
    API["FastAPI"]
    AUTH["Auth / Project / Lesson API"]
    DB[("PostgreSQL")]
    REDIS[("Redis")]
    CELERY["Celery Workers"]
    PIPE["Teaching Pipeline"]
    OCR["OCR Adapter"]
    LLM["LLM Adapter"]
    PLANNER["Math / Chinese Planner"]
    VALIDATOR["Answer & Content Validator"]
    IR["Lesson IR Repository"]
    WEB["Web Lesson Renderer"]
    MANIM["Manim Renderer"]
    STORY["Story Image Renderer"]
    TTS["TTS Adapter"]
    FFMPEG["FFmpeg Composer"]
    STORAGE["Storage Adapter"]
    ASSET[("Local Files / S3 / MinIO")]

    FE --> API
    API --> AUTH
    AUTH --> DB
    API --> REDIS
    REDIS --> CELERY
    CELERY --> PIPE
    PIPE --> OCR
    PIPE --> LLM
    PIPE --> PLANNER
    PLANNER --> VALIDATOR
    VALIDATOR --> IR
    IR --> DB
    IR --> WEB
    IR --> MANIM
    IR --> STORY
    MANIM --> FFMPEG
    STORY --> FFMPEG
    TTS --> FFMPEG
    FFMPEG --> STORAGE
    WEB --> STORAGE
    STORAGE --> ASSET
    API --> ASSET
```

Web 图解可以由前端根据 IR 即时渲染，也可以生成静态 HTML/JSON 资源。MVP
推荐前端即时渲染，减少后端重复工作。

------------------------------------------------------------------------

## 3. 技术栈与职责

  层          技术                                  职责
  ----------- ------------------------------------- ------------------------
  前端        Vue 3、TypeScript、Vite               工作台、编辑器、播放器
  UI          Element Plus 或 Naive UI              基础表单和管理界面
  状态        Pinia                                 页面状态
  动画        SVG、CSS、Motion One/GSAP（按需）     Web 场景动画
  API         FastAPI、Pydantic                     REST API、Schema 校验
  ORM         SQLAlchemy 2                          数据持久化
  Migration   Alembic                               数据库迁移
  任务队列    Celery                                异步任务
  Broker      Redis                                 任务分发
  LLM 编排    普通 Python Service；后续 LangGraph   教学工作流
  OCR         PaddleOCR Adapter                     图片/PDF 文字识别
  数学动画    Manim Community                       数学/科学动画
  TTS         CosyVoice Adapter                     中文旁白
  合成        FFmpeg                                音画合成
  图片生成    ComfyUI（P1）                         故事人物和场景
  数据库      PostgreSQL                            业务、IR、任务元数据
  存储        LocalStorage；后续 S3/MinIO           图片、音频、视频
  观测        Python logging，后续 OpenTelemetry    日志和链路追踪

模型选择不写死在业务层。通过环境变量和 Provider Factory
配置本地模型或远程 API。

------------------------------------------------------------------------

## 4. 模块边界

### 4.1 API 层

职责： - 请求校验。 - 用户/项目/教学内容接口。 - 创建任务和查询状态。 -
资源访问授权。 - 不执行长时间视频渲染。

### 4.2 Lesson Domain

职责： - Lesson、LessonVersion、Scene 的领域规则。 - IR 版本控制。 -
场景编辑和锁定。 - 任务与教学内容的关联。

### 4.3 AI Pipeline

职责： - 题目分类。 - 学科 Planner。 - 脚本生成。 - 答案验证。 -
内容审核。 - IR 生成与校验。

AI Pipeline 不直接调用 Manim 或 FFmpeg；它只产出合法 IR。

### 4.4 Renderer

统一接口建议：

``` python
from typing import Protocol

class Renderer(Protocol):
    async def render_scene(self, lesson_id: str, scene: dict) -> list[str]:
        ...

class VideoComposer(Protocol):
    async def compose(
        self,
        lesson_id: str,
        scene_assets: list[str],
        audio_assets: list[str],
        output_key: str
    ) -> str:
        ...
```

具体实现： - `WebRenderer`：前端按 IR 渲染。 -
`ManimRenderer`：数学/图形场景。 -
`StoryRenderer`：图片场景和镜头运动。 -
`FFmpegComposer`：视频拼接和音画合成。

### 4.5 Provider 层

统一抽象： - `LLMProvider` - `OCRProvider` - `TTSProvider` -
`ImageProvider` - `StorageProvider`

Provider 的输入输出采用内部数据模型，不将第三方 SDK 类型泄漏到业务层。

------------------------------------------------------------------------

## 5. 推荐仓库结构

``` text
edumotion-ai/
├── docs/
│   ├── PRODUCT_SPEC.md
│   ├── LESSON_IR_SPEC.md
│   └── ARCHITECTURE.md
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── views/
│   │   ├── stores/
│   │   ├── composables/
│   │   ├── types/
│   │   └── router/
│   ├── package.json
│   └── vite.config.ts
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/v1/
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── repositories/
│   │   ├── services/
│   │   ├── ai/
│   │   │   ├── llm/
│   │   │   ├── ocr/
│   │   │   ├── planners/
│   │   │   └── validators/
│   │   ├── render/
│   │   │   ├── manim/
│   │   │   ├── story/
│   │   │   └── video/
│   │   ├── tts/
│   │   ├── storage/
│   │   └── workers/
│   ├── tests/
│   ├── alembic/
│   └── pyproject.toml
├── shared/
│   └── lesson-ir/
│       ├── schema.json
│       └── examples/
├── model-workflows/
│   └── comfyui/
├── infra/
│   ├── docker-compose.yml
│   ├── docker/
│   └── scripts/
├── data/
│   ├── uploads/
│   ├── assets/
│   └── renders/
├── .env.example
├── .gitignore
└── README.md
```

------------------------------------------------------------------------

## 6. API 设计

统一前缀：`/api/v1`

### 6.1 创建教学内容

`POST /lessons`

请求：

``` json
{
  "title": "苹果应用题",
  "subject": "math",
  "grade": "grade_1",
  "input_type": "text",
  "content": "小红有12个苹果，送给小明4个，还剩多少个？",
  "outputs": ["web", "video"]
}
```

响应：

``` json
{
  "lesson_id": "lesson_001",
  "job_id": "job_001",
  "status": "CREATED"
}
```

### 6.2 上传文件

`POST /lessons/upload`

-   使用 multipart/form-data。
-   返回 source_id、文件元数据和解析任务 ID。
-   校验 MIME、扩展名、文件大小。
-   文件名采用服务端生成的安全 ID，不直接作为存储路径。

### 6.3 分析题目

`POST /lessons/{lesson_id}/analyze`

响应包含： - 学科分类。 - 题型。 - OCR/规范化文本。 - 关键实体。 -
建议年级。 - 分类置信度。 - warning。

### 6.4 生成 Lesson IR

`POST /lessons/{lesson_id}/generate`

请求：

``` json
{
  "style": "cartoon",
  "outputs": ["web", "video"],
  "duration_target_seconds": 60,
  "require_human_review": true
}
```

响应：

``` json
{
  "lesson_id": "lesson_001",
  "job_id": "job_002",
  "status": "SCRIPT_GENERATING"
}
```

### 6.5 获取和编辑 IR

-   `GET /lessons/{lesson_id}/ir`
-   `GET /lessons/{lesson_id}/versions`
-   `PUT /lessons/{lesson_id}/ir`

更新时建议传 `expected_version`，防止覆盖其他编辑。

### 6.6 渲染

`POST /lessons/{lesson_id}/render`

``` json
{
  "ir_version": 2,
  "outputs": ["video"],
  "scene_ids": ["scene_001", "scene_003"],
  "force": false
}
```

`scene_ids`
为空表示渲染所有场景。指定场景时，只重渲染对应场景及其依赖资产。

### 6.7 查询任务

`GET /jobs/{job_id}`

``` json
{
  "job_id": "job_002",
  "status": "RENDERING",
  "progress": 65,
  "stage": "video_composition",
  "message": "正在合成视频",
  "error": null
}
```

### 6.8 SSE 进度

`GET /jobs/{job_id}/stream`

事件示例：

``` text
event: progress
data: {"status":"RENDERING","progress":65,"stage":"video_composition"}

event: completed
data: {"status":"COMPLETED","asset_id":"asset_001"}
```

### 6.9 资源接口

-   `GET /lessons/{lesson_id}/assets`
-   `GET /assets/{asset_id}`
-   `DELETE /assets/{asset_id}`（需校验引用关系和权限）

生产环境下载应使用受控下载接口或短时签名 URL。

------------------------------------------------------------------------

## 7. 数据模型

建议 PostgreSQL 表：

### 7.1 edu_project

-   id UUID PK
-   owner_id UUID
-   name VARCHAR
-   description TEXT
-   created_at TIMESTAMPTZ
-   updated_at TIMESTAMPTZ

### 7.2 edu_source

-   id UUID PK
-   project_id UUID FK
-   source_type VARCHAR
-   original_filename VARCHAR
-   storage_key TEXT
-   mime_type VARCHAR
-   file_size BIGINT
-   extracted_text TEXT
-   parse_status VARCHAR
-   created_at TIMESTAMPTZ

### 7.3 edu_lesson

-   id UUID PK
-   project_id UUID FK
-   title VARCHAR
-   subject VARCHAR
-   grade VARCHAR
-   status VARCHAR
-   current_version INTEGER
-   created_at TIMESTAMPTZ
-   updated_at TIMESTAMPTZ

### 7.4 edu_lesson_version

-   id UUID PK
-   lesson_id UUID FK
-   version INTEGER
-   schema_version VARCHAR
-   ir_json JSONB
-   created_by VARCHAR
-   created_at TIMESTAMPTZ
-   UNIQUE(lesson_id, version)

### 7.5 edu_generation_job

-   id UUID PK
-   lesson_id UUID FK
-   lesson_version_id UUID FK NULL
-   job_type VARCHAR
-   status VARCHAR
-   stage VARCHAR
-   progress INTEGER
-   idempotency_key VARCHAR
-   retry_count INTEGER
-   error_code VARCHAR NULL
-   error_message TEXT NULL
-   started_at TIMESTAMPTZ NULL
-   finished_at TIMESTAMPTZ NULL
-   created_at TIMESTAMPTZ

### 7.6 edu_asset

-   id UUID PK
-   lesson_id UUID FK
-   lesson_version_id UUID FK NULL
-   scene_id VARCHAR NULL
-   asset_type VARCHAR
-   storage_key TEXT
-   mime_type VARCHAR
-   size_bytes BIGINT
-   checksum VARCHAR
-   metadata JSONB
-   created_at TIMESTAMPTZ

### 7.7 edu_scene（可选）

MVP 可以只在 IR JSONB
内保存场景。若后续需要场景级查询、复用、锁定和状态统计，再独立建表： -
id UUID PK - lesson_version_id UUID FK - scene_key VARCHAR - scene_order
INTEGER - scene_json JSONB - render_status VARCHAR

------------------------------------------------------------------------

## 8. 异步任务与工作流

### 8.1 任务阶段

``` text
CREATED
  -> PARSING
  -> ANALYZING
  -> SCRIPT_GENERATING
  -> REVIEWING
  -> WAITING_FOR_APPROVAL
  -> RENDERING
  -> COMPLETED
```

失败和取消状态： - `FAILED` - `CANCELLED`

任务阶段应持久化到 PostgreSQL。Redis
仅用于队列和短期协调，不作为唯一状态来源。

### 8.2 任务拆分

建议将长任务拆成小任务：

1.  `parse_source_task`
2.  `analyze_lesson_task`
3.  `generate_ir_task`
4.  `validate_ir_task`
5.  `generate_tts_task`
6.  `render_scene_task`
7.  `compose_video_task`
8.  `finalize_assets_task`

Web 图解可在 IR 保存后立即可用，不必等待视频任务。

### 8.3 幂等与重试

-   每个任务生成 idempotency_key。
-   同一 lesson version + scene + renderer version 可计算渲染缓存键。
-   已完成且缓存有效的场景可复用。
-   对网络/API 临时错误采用有限次数指数退避。
-   Schema 错误、无效参数等确定性错误不应无限重试。
-   任务取消时终止可终止的子进程，并清理临时文件。
-   Worker 崩溃后通过任务租约/超时检测恢复或标记失败。

### 8.4 进度计算

进度由阶段权重组成，例如： - 解析 10% - 分析 10% - 生成 IR 20% - 验证
10% - TTS 10% - 场景渲染 30% - 合成和归档 10%

具体进度必须来自真实阶段状态，不要仅用定时器模拟。

------------------------------------------------------------------------

## 9. 渲染架构

### 9.1 Web Renderer

-   Vue 根据 `scene.type` 和 `visual.component` 选择注册组件。
-   动画参数通过受控动画注册表解释。
-   旁白播放与字幕使用统一的 scene 数据。
-   Web 端不得执行 IR 中的脚本或表达式。
-   未知组件降级为安全的通用场景卡片。

### 9.2 Manim Renderer

-   接收经过校验的 IR 场景。
-   根据允许列表选择模板。
-   将参数传给模板，不把模型输出拼接为任意 Python 代码。
-   在隔离子进程中运行。
-   限制 CPU、内存、执行时间和输出目录。
-   产出场景视频和日志。

### 9.3 Story Renderer

MVP： - 预置图片、用户图片或受控素材。 -
使用缩放、平移、淡入淡出等镜头效果。 - 生成场景片段。

P1： - 调用 ComfyUI 生成场景图。 -
人物设定图作为参考，保持角色视觉一致。 - 记录 prompt、模型版本、seed
和资产引用，便于复现。

### 9.4 TTS 与 FFmpeg

-   每个场景生成音频文件。
-   保存音频时长和资源 ID。
-   使用统一时间轴合成场景、旁白、字幕。
-   字幕字体需支持中文。
-   背景音乐默认关闭或使用明确授权的素材。
-   FFmpeg 参数通过固定模板构造，不接受任意命令字符串。

------------------------------------------------------------------------

## 10. 存储设计

### 10.1 Storage Adapter

定义： - `put(key, file, metadata)` - `get(key)` - `delete(key)` -
`exists(key)` - `get_url(key, expires_in=None)`

本地实现 `LocalStorage`，云端实现 `S3Storage`。MinIO 可作为本地 S3
兼容测试服务，但初期不是必须组件。

### 10.2 推荐目录

``` text
data/
├── uploads/
│   └── {source_id}/original
├── lessons/
│   └── {lesson_id}/
│       ├── versions/
│       │   └── v1/lesson_ir.json
│       ├── scenes/
│       │   ├── scene_001/
│       │   │   ├── image.png
│       │   │   ├── narration.wav
│       │   │   └── scene.mp4
│       │   └── scene_002/
│       └── outputs/
│           ├── lesson.mp4
│           ├── subtitles.srt
│           └── poster.jpg
└── temp/
    └── {job_id}/
```

数据库保存 storage_key，不保存依赖某台机器的绝对路径。

------------------------------------------------------------------------

## 11. 本地部署

### 11.1 推荐服务

基础 Docker Compose： - postgres - redis - api -
worker（可按需要本机运行） - 可选 minio

本机进程： - Vue dev server - Manim/FFmpeg
Worker（若容器环境不适合图形/字体依赖） - 本地 LLM 服务 - 可选 ComfyUI

### 11.2 环境变量示例

``` dotenv
APP_ENV=local
API_HOST=0.0.0.0
API_PORT=8000

DATABASE_URL=postgresql+psycopg://edu:edu_dev@localhost:5432/edumotion
REDIS_URL=redis://localhost:6379/0

STORAGE_BACKEND=local
LOCAL_STORAGE_ROOT=./data

LLM_PROVIDER=local
LLM_BASE_URL=http://localhost:8001/v1
LLM_MODEL=your-instruct-model
LLM_API_KEY=

OCR_PROVIDER=paddleocr
TTS_PROVIDER=cosyvoice

RENDER_WORK_DIR=./data/temp
FFMPEG_BIN=ffmpeg
```

不要把真实密钥提交到 Git。`.env.example` 只放占位值。

### 11.3 启动步骤（目标流程）

``` bash
# 1. 启动基础设施
docker compose -f infra/docker-compose.yml up -d postgres redis

# 2. 后端环境
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 3. Worker（另开终端）
cd backend
celery -A app.workers.celery_app worker --loglevel=info

# 4. 前端（另开终端）
cd frontend
npm install
npm run dev
```

以上为建议启动命令，具体依赖和 Celery app 路径需以实际仓库实现为准。

------------------------------------------------------------------------

## 12. 云端迁移策略

### 阶段 A：单机本地

-   API、数据库、Redis、Worker 在一台开发机或测试机。
-   本地文件存储。
-   模型在本地或通过 Provider 调用。

### 阶段 B：云端单机

-   API 和 Worker 容器化。
-   PostgreSQL 使用持久化卷或托管数据库。
-   对象存储切换 S3。
-   Worker 与 API 分进程部署。

### 阶段 C：GPU Worker 独立扩展

-   CPU Worker：OCR、脚本、任务编排。
-   GPU Worker：ComfyUI、TTS 或本地模型推理。
-   Render Worker：Manim、FFmpeg。
-   根据队列长度和资源使用率扩缩容。

### 阶段 D：服务拆分（确有必要时）

优先拆分： 1. Render Service。 2. Model Inference Service。 3. Asset
Service。

不要为了"微服务化"提前增加分布式事务和运维成本。

------------------------------------------------------------------------

## 13. 安全与可靠性

### 13.1 文件安全

-   MIME 与文件头双重校验。
-   文件大小、页数、图片尺寸上限。
-   PDF/图片解析使用受限进程。
-   文件名和路径由服务端生成。
-   下载资源需检查访问权限。

### 13.2 模型输出安全

-   所有模型输出先过 Pydantic/JSON Schema。
-   Renderer 只执行白名单组件和动画。
-   不执行模型生成的 Python、Shell、JS。
-   对提示词注入和用户输入进行边界处理。
-   记录模型名称、版本、参数和 prompt 版本。

### 13.3 渲染隔离

-   独立低权限用户。
-   独立临时目录。
-   CPU、内存、时长和文件大小限制。
-   禁止渲染容器默认访问宿主机敏感目录。
-   子进程超时后强制终止。
-   清理临时文件并保留必要日志。

### 13.4 数据保护

-   尽量不收集未成年人个人身份信息。
-   上传文件设置保留和删除策略。
-   日志中避免输出原文中的敏感个人信息。
-   生产环境启用认证、授权、TLS 和备份。
-   评估教育场景适用的数据保护和未成年人法规。

------------------------------------------------------------------------

## 14. 可观测性与测试

### 14.1 日志字段

建议每条日志包含： - request_id - lesson_id - job_id - stage -
provider - model - renderer - duration_ms - status - error_code

避免记录密钥和不必要的学生个人信息。

### 14.2 测试层级

**单元测试** - IR Schema。 - 数学验证器。 - 题目分类解析。 - Storage
Adapter。 - 状态流转。

**集成测试** - API 创建 lesson。 - 创建 Celery 任务。 - 生成 IR
并保存版本。 - Worker 渲染场景。 - FFmpeg 合成输出。

**端到端测试** - 文本数学题 → IR → Web 图解 → MP4。 - 图片数学题 → OCR →
IR → 输出。 - 语文短文 → 故事分镜 → Web 图解 → 视频。

### 14.3 质量回归集

建立固定题目集，记录： - 输入原文。 - 期望答案/知识点。 - 关键证据。 -
预期场景类型。 - 已知易错点。

Prompt、模型、IR 或 Renderer 变更后运行回归集，避免质量倒退。

------------------------------------------------------------------------

## 15. 开发阶段与交付顺序

### Sprint 1：基础工程

-   Monorepo。
-   FastAPI、Vue。
-   PostgreSQL、Redis。
-   文件上传。
-   Lesson/Job 基础模型。

### Sprint 2：理解与 IR

-   OCR Provider。
-   LLM Provider。
-   分类与 Planner。
-   Pydantic IR。
-   数学/语文基础 Validator。

### Sprint 3：Web 图解

-   Scene Registry。
-   数学场景组件。
-   故事场景组件。
-   滚动播放器。
-   IR 版本编辑。

### Sprint 4：视频

-   Manim 模板。
-   TTS Provider。
-   FFmpeg Composer。
-   异步渲染与进度。

### Sprint 5：质量与稳定性

-   任务重试。
-   日志。
-   场景级重渲染。
-   回归测试。
-   本地部署文档。

### Sprint 6：语文增强

-   ComfyUI 可选接入。
-   人物设定图。
-   故事场景生成。
-   原文证据定位。

------------------------------------------------------------------------

## 16. 关键架构决策记录（ADR 摘要）

### ADR-001：模块化单体优先

理由：MVP 开发速度快，运维成本低；边界明确后可拆分 Worker。

### ADR-002：Lesson IR 作为核心契约

理由：教学内容与输出渠道解耦，避免多次生成内容不一致。

### ADR-003：程序化动画优先于生成式视频

理由：数学准确性、可控性、成本和可复现性更好。

### ADR-004：渲染异步化

理由：视频任务耗时长，不能占用 API 请求生命周期。

### ADR-005：Provider 抽象

理由：本地模型和云端模型可切换，不锁定某个厂商。

### ADR-006：先 Web Renderer，后视频 Renderer

理由：Web 图解反馈快，能先验证教学脚本质量，再投入视频渲染成本。

------------------------------------------------------------------------

## 17. 架构验收清单

-   [ ] 前端能创建 lesson 并查看任务状态。
-   [ ] 后端能保存原始材料和 IR 版本。
-   [ ] AI 输出经过 Schema 校验。
-   [ ] 数学和语文使用不同 Planner。
-   [ ] Web Renderer 与 Video Renderer 共用 IR。
-   [ ] 视频任务由 Worker 异步执行。
-   [ ] 任务失败有错误码和日志。
-   [ ] 支持场景级重渲染。
-   [ ] Storage 可从本地切换到 S3。
-   [ ] Provider 可切换模型服务。
-   [ ] 渲染过程不执行任意模型代码。
-   [ ] 本地部署可重复执行。