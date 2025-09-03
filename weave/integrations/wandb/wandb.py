import logging
import os

from weave.trace.api import init

logger = logging.getLogger(__name__)


def wandb_init_hook() -> None:
    if os.environ.get("WANDB_DISABLE_WEAVE"):
        return

    # Try to get the active run path from wandb if we can
    try:
        from wandb.integration.weave import active_run_path
    except (ImportError, ModuleNotFoundError):
        return  # wandb not available
    except Exception as e:
        logger.debug(f"Unexpected wandb error: {e}")
        return
    if not (run_path := active_run_path()):
        return

    project_path = f"{run_path.entity}/{run_path.project}"
    logger.info(
        f"Active wandb run detected. Using project name from wandb: {project_path}"
    )

    init(project_path)
