from redis import __version__ as redis_version

from app.celery_app import celery_app


def _version_tuple(value: str) -> tuple[int, int, int]:
    parts = []
    for component in value.split(".")[:3]:
        digits = "".join(character for character in component if character.isdigit())
        parts.append(int(digits or "0"))
    return tuple((parts + [0, 0, 0])[:3])


def test_redis_client_meets_kombu_transport_minimum():
    version = _version_tuple(redis_version)
    assert (6, 1, 0) <= version < (7, 0, 0)


def test_video_tasks_have_soft_and_hard_time_limits():
    soft_limit = celery_app.conf.task_soft_time_limit
    hard_limit = celery_app.conf.task_time_limit
    assert soft_limit > 0
    assert hard_limit > soft_limit
