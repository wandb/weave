"""Implementation of the hook interface."""

import datetime
import os
import subprocess
from typing import Dict, List, Optional

from bumpversion.config.models import Config
from bumpversion.context import get_context
from bumpversion.exceptions import HookError
from bumpversion.ui import get_indented_logger
from bumpversion.versioning.models import Version

PREFIX = "BVHOOK_"

logger = get_indented_logger(__name__)


def run_command(script: str, environment: Optional[dict] = None) -> subprocess.CompletedProcess:
    """Runs command-line programs using the shell."""
    if not isinstance(script, str):
        raise TypeError(f"`script` must be a string, not {type(script)}")
    if environment and not isinstance(environment, dict):
        raise TypeError(f"`environment` must be a dict, not {type(environment)}")
    return subprocess.run(
        script, env=environment, encoding="utf-8", shell=True, text=True, capture_output=True, check=False
    )


def base_env(config: Config) -> Dict[str, str]:
    """Provide the base environment variables."""
    return {
        f"{PREFIX}NOW": datetime.datetime.now().isoformat(),
        f"{PREFIX}UTCNOW": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        **os.environ,
        **scm_env(config),
    }


def scm_env(config: Config) -> Dict[str, str]:
    """Provide the scm environment variables."""
    scm = config.scm_info
    return {
        f"{PREFIX}COMMIT_SHA": scm.commit_sha or "",
        f"{PREFIX}DISTANCE_TO_LATEST_TAG": str(scm.distance_to_latest_tag) or "0",
        f"{PREFIX}IS_DIRTY": str(scm.dirty),
        f"{PREFIX}BRANCH_NAME": scm.branch_name or "",
        f"{PREFIX}SHORT_BRANCH_NAME": scm.short_branch_name or "",
        f"{PREFIX}CURRENT_VERSION": scm.current_version or "",
        f"{PREFIX}CURRENT_TAG": scm.current_tag or "",
    }


def version_env(version: Version, version_prefix: str) -> Dict[str, str]:
    """Provide the environment variables for each version component with a prefix."""
    return {f"{PREFIX}{version_prefix}{part.upper()}": version[part].value for part in version}


def new_version_env(config: Config, current_version: Version, new_version: Version) -> Dict[str, str]:
    """Provide the environment dictionary for new_version serialized and tag name."""
    ctx = get_context(config, current_version, new_version)
    new_version_string = config.version_config.serialize(new_version, ctx)
    ctx["new_version"] = new_version_string
    new_version_tag = config.tag_name.format(**ctx)
    return {f"{PREFIX}NEW_VERSION": new_version_string, f"{PREFIX}NEW_VERSION_TAG": new_version_tag}


def get_setup_hook_env(config: Config, current_version: Version) -> Dict[str, str]:
    """Provide the environment dictionary for `setup_hook`s."""
    return {**base_env(config), **scm_env(config), **version_env(current_version, "CURRENT_")}


def get_pre_commit_hook_env(config: Config, current_version: Version, new_version: Version) -> Dict[str, str]:
    """Provide the environment dictionary for `pre_commit_hook`s."""
    return {
        **base_env(config),
        **scm_env(config),
        **version_env(current_version, "CURRENT_"),
        **version_env(new_version, "NEW_"),
        **new_version_env(config, current_version, new_version),
    }


def get_post_commit_hook_env(config: Config, current_version: Version, new_version: Version) -> Dict[str, str]:
    """Provide the environment dictionary for `post_commit_hook`s."""
    return {
        **base_env(config),
        **scm_env(config),
        **version_env(current_version, "CURRENT_"),
        **version_env(new_version, "NEW_"),
        **new_version_env(config, current_version, new_version),
    }


def run_hooks(hooks: List[str], env: Dict[str, str], dry_run: bool = False) -> None:
    """Run a list of command-line programs using the shell."""
    logger.indent()
    for script in hooks:
        if dry_run:
            logger.debug(f"Would run {script!r}")
            continue
        logger.debug(f"Running {script!r}")
        logger.indent()
        result = run_command(script, env)
        if result.returncode != 0:
            logger.warning(result.stdout)
            logger.warning(result.stderr)
            raise HookError(f"{script!r} exited with {result.returncode}. ")
        else:
            logger.debug(f"Exited with {result.returncode}")
            logger.debug(result.stdout)
            logger.debug(result.stderr)
        logger.dedent()
    logger.dedent()


def run_setup_hooks(config: Config, current_version: Version, dry_run: bool = False) -> None:
    """Run the setup hooks."""
    env = get_setup_hook_env(config, current_version)
    if config.setup_hooks:
        running = "Would run" if dry_run else "Running"
        logger.info(f"{running} setup hooks:")
    else:
        logger.info("No setup hooks defined")
        return

    run_hooks(config.setup_hooks, env, dry_run)


def run_pre_commit_hooks(
    config: Config, current_version: Version, new_version: Version, dry_run: bool = False
) -> None:
    """Run the pre-commit hooks."""
    env = get_pre_commit_hook_env(config, current_version, new_version)

    if config.pre_commit_hooks:
        running = "Would run" if dry_run else "Running"
        logger.info(f"{running} pre-commit hooks:")
    else:
        logger.info("No pre-commit hooks defined")
        return

    run_hooks(config.pre_commit_hooks, env, dry_run)


def run_post_commit_hooks(
    config: Config, current_version: Version, new_version: Version, dry_run: bool = False
) -> None:
    """Run the post-commit hooks."""
    env = get_post_commit_hook_env(config, current_version, new_version)
    if config.post_commit_hooks:
        running = "Would run" if dry_run else "Running"
        logger.info(f"{running} post-commit hooks:")
    else:
        logger.info("No post-commit hooks defined")
        return

    run_hooks(config.post_commit_hooks, env, dry_run)
