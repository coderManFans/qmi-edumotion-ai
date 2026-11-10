from celery import Celery

from app.core.config import settings


celery_app = Celery(
    "edumotion",
    broker=settings.redis_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.problem_video"],
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
    task_routes={"app.tasks.problem_video.generate_problem_video_task": {"queue": "videos"}},
)
