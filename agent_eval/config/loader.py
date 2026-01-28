"""YAML configuration loading and validation."""

from __future__ import annotations

from pathlib import Path

import yaml

from .schema import EvalConfig


def load_config(path: str | Path) -> EvalConfig:
    """Load and validate an evaluation configuration from YAML.

    Args:
        path: Path to the YAML configuration file.

    Returns:
        Validated EvalConfig instance.

    Raises:
        FileNotFoundError: If the config file doesn't exist.
        yaml.YAMLError: If the YAML is malformed.
        pydantic.ValidationError: If the config doesn't match schema.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    return EvalConfig.model_validate(raw)


def validate_config(path: str | Path) -> tuple[bool, list[str]]:
    """Validate a configuration file without loading fully.

    Args:
        path: Path to the YAML configuration file.

    Returns:
        Tuple of (is_valid, list of error messages).
    """
    errors: list[str] = []

    try:
        config = load_config(path)
    except FileNotFoundError as e:
        return False, [str(e)]
    except yaml.YAMLError as e:
        return False, [f"YAML parse error: {e}"]
    except Exception as e:
        return False, [f"Validation error: {e}"]

    # Additional semantic validation
    path = Path(path)
    config_dir = path.parent

    # Check skill path exists
    skill_path = config_dir / config.skill.path
    if not skill_path.exists():
        errors.append(f"Skill path not found: {skill_path}")

    # Check layer paths exist
    for layer in config.environment.layers:
        layer_path = config_dir / layer
        if not layer_path.exists():
            errors.append(f"Layer path not found: {layer_path}")

    # Check custom scorer configs exist
    for scorer in config.scoring.custom:
        if scorer.config:
            scorer_config_path = config_dir / scorer.config
            if not scorer_config_path.exists():
                errors.append(f"Scorer config not found: {scorer_config_path}")

    return len(errors) == 0, errors
