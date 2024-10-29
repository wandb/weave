from weave.actions_worker.celery_app import app

from . import tasks  # noqa: F401

# Define the result expiration time in seconds (24 hours)
RESULT_EXPIRES = 24 * 60 * 60  # 24 hours in seconds

# Optional configuration, see the application user guide.
app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    result_expires=RESULT_EXPIRES,
    broker_connection_retry_on_startup=True,
)
