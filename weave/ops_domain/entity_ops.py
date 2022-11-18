from ..api import op
from . import wb_domain_types
from . import wandb_domain_gql


@op(name="root-entity")
def entity(entityName: str) -> wb_domain_types.Entity:
    return wb_domain_types.Entity(entityName)


@op(name="entity-name")
def entity_name(entity: wb_domain_types.Entity) -> str:
    return entity.entity_name


@op(name="entity-link")
def entity_link(entity: wb_domain_types.Entity) -> wb_domain_types.Link:
    return wb_domain_types.Link(entity.entity_name, f"/{entity.entity_name}")


@op(name="entity-portfolios")
def entity_portfolios(
    entity: wb_domain_types.Entity,
) -> list[wb_domain_types.ArtifactCollection]:
    return wandb_domain_gql.entity_portfolios(entity)
