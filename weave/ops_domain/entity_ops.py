from ..api import op
from . import wb_domain_types
from . import wandb_domain_gql


@op(name="root-entity")
def entity(entityName: str) -> wb_domain_types.Entity:
    return wb_domain_types.Entity(entityName)


@op(name="entity-name")
def entity_name(entity: wb_domain_types.Entity) -> str:
    return entity.entity_name


@op(name="entity-isTeam")
def entity_is_team(entity: wb_domain_types.Entity) -> bool:
    return wandb_domain_gql.entity_is_team(entity)


@op(name="entity-link")
def entity_link(entity: wb_domain_types.Entity) -> wb_domain_types.Link:
    return wb_domain_types.Link(entity.entity_name, f"/{entity.entity_name}")


@op(name="entity-portfolios")
def entity_portfolios(
    entity: wb_domain_types.Entity,
) -> list[wb_domain_types.ArtifactCollection]:
    return wandb_domain_gql.entity_portfolios(entity)


@op(name="entity-projects")
def entity_projects(
    entity: wb_domain_types.Entity,
) -> list[wb_domain_types.Project]:
    return wandb_domain_gql.entity_projects(entity)
