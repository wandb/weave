"""
The purpose of this utility is to simply ensure that a W&B project exists
"""
from wandb.sdk.internal.internal_api import Api as InternalApi

def ensure_project_exists(entity_name: str, project_name: str) -> None:
    api = InternalApi(
        {"entity": entity_name, "project": project_name}
    )
    # Since `UpsertProject` will fail if the user does not have permission to create a project
    # we must first check if the project exists
    project = api.project(entity=entity_name, project=project_name)
    if project is None:
        project = api.upsert_project(entity=entity_name, project=project_name)
        if project is None:
            raise Exception(f"Failed to create project {entity_name}/{project_name}")
    return
