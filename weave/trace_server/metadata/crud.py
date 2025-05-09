from typing import Any, Optional

from sqlalchemy.orm import Session

from . import models


def create_configuration(
    db: Session,
    project_id: str,
    type: str,
    value: dict[str, Any],
) -> models.Configuration:
    """Create a new configuration."""
    db_configuration = models.Configuration(
        project_id=project_id, type=type, value=value
    )
    db.add(db_configuration)
    db.commit()
    db.refresh(db_configuration)
    return db_configuration


def get_configuration_by_id(
    db: Session, configuration_id: str
) -> Optional[models.Configuration]:
    """Get a single configuration by its ID."""
    return (
        db.query(models.Configuration)
        .filter(models.Configuration.id == configuration_id)
        .first()
    )


def get_configurations_by_project_id(
    db: Session, project_id: str, skip: int = 0, limit: int = 100
) -> list[models.Configuration]:
    """Get configurations for a specific project_id with pagination."""
    return (
        db.query(models.Configuration)
        .filter(models.Configuration.project_id == project_id)
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_configurations_by_type(
    db: Session, type: str, project_id: str
) -> list[models.Configuration]:
    """Get configurations of a specific type with pagination."""
    return (
        db.query(models.Configuration)
        .filter(models.Configuration.type == type)
        .filter(models.Configuration.project_id == project_id)
        .all()
    )


def update_configuration_value(
    db: Session,
    configuration_id: str,
    value: dict[str, Any],
    type_str: Optional[str] = None,
) -> Optional[models.Configuration]:
    """Update the value and/or type of an existing configuration."""
    db_configuration = get_configuration_by_id(db, configuration_id)
    if db_configuration:
        db_configuration.value = value
        if type_str is not None:
            db_configuration.type = type_str
        db.commit()
        db.refresh(db_configuration)
    return db_configuration


def delete_configuration(
    db: Session, configuration_id: str
) -> Optional[models.Configuration]:
    """Delete a configuration by its ID."""
    db_configuration = get_configuration_by_id(db, configuration_id)
    if db_configuration:
        db.delete(db_configuration)
        db.commit()
    return db_configuration
