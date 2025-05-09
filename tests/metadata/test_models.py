import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from weave.trace_server.metadata.models import Configuration  # Adjusted import path


def test_create_and_get_configuration(db_session):
    """Test creating and retrieving a Configuration object."""
    project_id = str(uuid.uuid4())
    config_type = "test_type"
    config_value = {"key": "value"}

    # Create configuration
    new_config = Configuration(
        project_id=project_id, type=config_type, value=config_value
    )
    db_session.add(new_config)
    db_session.commit()
    db_session.refresh(new_config)

    assert new_config.id is not None
    assert new_config.project_id == project_id
    assert new_config.type == config_type
    assert new_config.value == config_value

    # Retrieve configuration
    retrieved_config = (
        db_session.query(Configuration).filter_by(id=new_config.id).first()
    )

    assert retrieved_config is not None
    assert retrieved_config.id == new_config.id
    assert retrieved_config.project_id == project_id
    assert retrieved_config.type == config_type
    assert retrieved_config.value == config_value

    # Test __repr__ (optional, but good for coverage)
    assert (
        repr(retrieved_config)
        == f"<Configuration(id='{new_config.id}', project_id='{project_id}', type='{config_type}')>"
    )


def test_configuration_project_id_not_nullable(db_session):
    """Test that project_id cannot be null."""
    with pytest.raises(IntegrityError):
        config = Configuration(project_id=None, type="test_type", value={"k": "v"})
        db_session.add(config)
        db_session.commit()


def test_configuration_type_not_nullable(db_session):
    """Test that type cannot be null."""
    with pytest.raises(IntegrityError):
        config = Configuration(
            project_id=str(uuid.uuid4()), type=None, value={"k": "v"}
        )
        db_session.add(config)
        db_session.commit()


def test_create_multiple_configurations_and_filter(db_session):
    """Test creating multiple configurations and filtering them."""
    project1_id = str(uuid.uuid4())
    project2_id = str(uuid.uuid4())
    type1 = "dashboard_settings"
    type2 = "user_preferences"

    configs_data = [
        {"project_id": project1_id, "type": type1, "value": {"theme": "dark"}},
        {"project_id": project1_id, "type": type2, "value": {"notifications": "on"}},
        {"project_id": project2_id, "type": type1, "value": {"layout": "compact"}},
    ]

    for data in configs_data:
        db_session.add(Configuration(**data))
    db_session.commit()

    # Filter by project1_id
    p1_configs = db_session.query(Configuration).filter_by(project_id=project1_id).all()
    assert len(p1_configs) == 2
    p1_types = {c.type for c in p1_configs}
    assert {type1, type2} == p1_types

    # Filter by project2_id and type1
    p2_type1_configs = (
        db_session.query(Configuration)
        .filter_by(project_id=project2_id, type=type1)
        .all()
    )
    assert len(p2_type1_configs) == 1
    assert p2_type1_configs[0].value == {"layout": "compact"}

    # Filter by non-existent type for project1
    p1_non_existent_configs = (
        db_session.query(Configuration)
        .filter_by(project_id=project1_id, type="non_existent_type")
        .all()
    )
    assert len(p1_non_existent_configs) == 0


@pytest.mark.parametrize(
    "json_value",
    [
        {"detail": "simple object"},
        [{"id": 1, "name": "item1"}, {"id": 2, "name": "item2"}],
        "a string value",
        12345,
        True,
        False,
    ],
)
def test_configuration_different_json_values(db_session, json_value):
    """Test storing and retrieving different types of valid JSON in the value field."""
    project_id = str(uuid.uuid4())
    config_type = "json_test"

    new_config = Configuration(
        project_id=project_id, type=config_type, value=json_value
    )
    db_session.add(new_config)
    db_session.commit()
    db_session.refresh(new_config)

    retrieved_config = (
        db_session.query(Configuration).filter_by(id=new_config.id).first()
    )
    assert retrieved_config is not None
    assert retrieved_config.value == json_value


def test_update_configuration(db_session):
    """Test updating an existing Configuration object."""
    project_id = str(uuid.uuid4())
    config = Configuration(
        project_id=project_id, type="initial_type", value={"k1": "v1"}
    )
    db_session.add(config)
    db_session.commit()
    db_session.refresh(config)

    # Update the configuration
    config_id = config.id
    updated_type = "updated_type"
    updated_value = {"k2": "v2"}

    config_to_update = db_session.query(Configuration).filter_by(id=config_id).first()
    config_to_update.type = updated_type
    config_to_update.value = updated_value
    db_session.commit()
    db_session.refresh(config_to_update)

    # Verify update
    retrieved_config = db_session.query(Configuration).filter_by(id=config_id).first()
    assert retrieved_config.type == updated_type
    assert retrieved_config.value == updated_value
    assert (
        retrieved_config.project_id == project_id
    )  # Ensure other fields are unchanged


def test_delete_configuration(db_session):
    """Test deleting a Configuration object."""
    config = Configuration(project_id=str(uuid.uuid4()), type="to_delete", value={})
    db_session.add(config)
    db_session.commit()
    db_session.refresh(config)

    config_id = config.id

    # Delete the configuration
    db_session.delete(config)
    db_session.commit()

    # Verify deletion
    deleted_config = db_session.query(Configuration).filter_by(id=config_id).first()
    assert deleted_config is None
