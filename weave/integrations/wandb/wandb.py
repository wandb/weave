import logging
import os

from weave.trace.api import init

logger = logging.getLogger(__name__)


def wandb_init_hook() -> None:
    if os.environ.get("WANDB_DISABLE_WEAVE"):
        return

    # Check if wandb is available
    try:
        import wandb
        
        # When wandb is available, set WEAVE_SILENT to true by default if not explicitly set
        # This reduces log noise when using wandb
        if os.getenv("WEAVE_SILENT") is None:
            os.environ["WEAVE_SILENT"] = "true"
            
    except (ImportError, ModuleNotFoundError):
        pass  # wandb not available, continue without setting WEAVE_SILENT

    # Try to get the active run path from wandb if we can
    try:
        from wandb.integration.weave import active_run_path
    except (ImportError, ModuleNotFoundError):
        return  # wandb integration not available
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
