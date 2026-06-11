from typing import Annotated, Any, TypeAlias

import pydantic
from weave_server_sdk.models import CallsFilter, Query, SortBy


def _reject_unknown_keys(obj: dict, model: type[pydantic.BaseModel]) -> None:
    """Raise for dict keys the model does not declare.

    The generated SDK models allow extra fields (forward compatibility on
    responses), but user-supplied dicts at this boundary should fail fast on
    typos like the strict legacy models did.
    """
    allowed = set(model.model_fields)
    for field in model.model_fields.values():
        if field.alias:
            allowed.add(field.alias)
    if extras := set(obj) - allowed:
        raise ValueError(
            f"Extra inputs are not permitted: {sorted(extras)} for {model.__name__}"
        )


def cast_to_calls_filter(obj: Any) -> CallsFilter:
    if isinstance(obj, CallsFilter):
        return obj

    if isinstance(obj, pydantic.BaseModel):
        # Foreign model families (e.g. legacy tsi.CallsFilter) are
        # field-compatible; re-validate.
        return CallsFilter.model_validate(obj.model_dump(by_alias=True))

    if isinstance(obj, dict):
        _reject_unknown_keys(obj, CallsFilter)
        return CallsFilter(**obj)

    raise TypeError(f"Unable to cast to CallsFilter: {obj}")


def cast_to_sort_by(obj: Any) -> SortBy:
    if isinstance(obj, SortBy):
        return obj

    if isinstance(obj, pydantic.BaseModel):
        return SortBy.model_validate(obj.model_dump(by_alias=True))

    if isinstance(obj, dict):
        _reject_unknown_keys(obj, SortBy)
        return SortBy(**obj)

    raise TypeError(f"Unable to cast to SortBy: {obj}")


def cast_to_query(obj: Any) -> Query:
    if isinstance(obj, Query):
        return obj

    if isinstance(obj, pydantic.BaseModel):
        return Query.model_validate(obj.model_dump(by_alias=True))

    if isinstance(obj, dict):
        _reject_unknown_keys(obj, Query)
        return Query(**obj)

    raise TypeError(f"Unable to cast to Query: {obj}")


CallsFilterLike: TypeAlias = Annotated[
    CallsFilter, pydantic.BeforeValidator(cast_to_calls_filter)
]
SortByLike: TypeAlias = Annotated[SortBy, pydantic.BeforeValidator(cast_to_sort_by)]
QueryLike: TypeAlias = Annotated[Query, pydantic.BeforeValidator(cast_to_query)]
