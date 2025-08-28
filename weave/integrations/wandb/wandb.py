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
    if not (entity := run_path.entity):
        return
    if not (project := run_path.project):
        return

    project_name = f"{entity}/{project}"
    logger.info(
        f"Active wandb run detected. Using project name from wandb: {project_name}"
    )

    init(project_name)
