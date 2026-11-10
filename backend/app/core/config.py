from celery import Celery
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    app_name: str = "EduMotion AI"
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:5173"]

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout_seconds: float = 45.0

    redis_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    celery_result_expires_seconds: int = 604800

    tts_provider: str = "edge"
    tts_voice: str = "zh-CN-XiaoxiaoNeural"
    tts_rate: str = "+0%"

    ffmpeg_bin: str = "ffmpeg"
    video_output_dir: str = "./data/renders"
    video_fps: int = 12
    video_scene_seconds: int = 3


settings = Settings()

celery_app = Celery(
    "edumotion",
    broker=settings.redis_url,
    backend=settings.celery_result_backend,
    include=["app.services.problem_explanation"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    result_expires=settings.celery_result_expires_seconds,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={"app.services.problem_explanation.generate_problem_video_task": {"queue": "videos"}},
)
