from pydantic import BaseModel

from weave.trace_server.interface.base_models.action_base_models import (
    ActionDispatchFilter,
    ConfiguredAction,
)


def base_model_name(base_model_class: type[BaseModel]) -> str:
    return base_model_class.__name__


def base_model_dump(base_model_obj: BaseModel) -> dict:
    d = base_model_obj.model_dump()
    d["_class_name"] = base_model_name(base_model_obj.__class__)
    d["_bases"] = [base_model_name(b) for b in base_model_obj.__class__.mro()[1:-1]]
    return d


base_models: list[type[BaseModel]] = [ConfiguredAction, ActionDispatchFilter]
