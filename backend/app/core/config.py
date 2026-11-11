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
    celery_task_soft_time_limit_seconds: int = 900
    celery_task_time_limit_seconds: int = 960

    tts_provider: str = "edge"
    tts_voice: str = "zh-CN-XiaoxiaoNeural"
    tts_rate: str = "+0%"

    ffmpeg_bin: str = "ffmpeg"
    video_output_dir: str = "./data/renders"
    video_fps: int = 12
    video_scene_seconds: int = 3


settings = Settings()
