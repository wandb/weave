import logging
import os

from weave.trace.api import init

logger = logging.getLogger(__name__)


def wandb_init_hook() -> None:
    if os.environ.get("WANDB_DISABLE_WEAVE"):
        return

    # If wandb isn't installed at all, there's nothing to auto-link; stay silent.
    try:
        import wandb  # noqa: F401
    except (ImportError, ModuleNotFoundError):
        return

    # wandb is installed — if the integration surface is missing, the user is
    # on a version that predates wandb<>weave auto-linking.  Log an actionable
    # warning so they know how to re-enable the feature.
    try:
        from wandb.integration.weave import active_run_path
    except (ImportError, ModuleNotFoundError):
        logger.warning(
            "wandb is installed but `wandb.integration.weave` is missing. "
            "Automatic wandb<>weave run linking is disabled. "
            "To enable it, upgrade wandb:\n"
            "    pip install --upgrade 'weave[wandb]'"
        )
        return
    except Exception as e:
        logger.debug("Unexpected wandb error: %s", e)
        return
    if not (run_path := active_run_path()):
        return

    project_path = f"{run_path.entity}/{run_path.project}"
    logger.info(
        "Active wandb run detected. Using project name from wandb: %s", project_path
    )

    init(project_path)
