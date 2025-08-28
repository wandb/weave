import logging

from weave.trace.api import init

logger = logging.getLogger(__name__)


def wandb_init_hook() -> None:
    # Try to get the active run path from wandb if we can
    try:
        from wandb.integration.weave import active_run_path
    except Exception:
        return
    if not (run_path := active_run_path()):
        return

    project_path = f"{run_path.entity}/{run_path.project}"
    logger.info(
        f"Active wandb run detected. Using project name from wandb: {project_path}"
    )

    init(project_path)
