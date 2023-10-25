import typing
from fastapi import FastAPI

from . import weave_types as types
from . import op_args
from . import weave_pydantic
from . import op_def
from .monitoring import monitor

from .artifact_wandb import WandbArtifactRef


def object_method_app(
    obj_ref: WandbArtifactRef, method_name: typing.Optional[str] = None
) -> FastAPI:
    obj = obj_ref.get()
    obj_weave_type = types.TypeRegistry.type_of(obj)
    if not isinstance(obj_weave_type, types.ObjectType):
        raise ValueError(
            f"Expected an object (created by @weave.type()), got {obj_weave_type}"
        )

    op_attrs: dict[str, op_def.OpDef] = {
        attr: value
        for attr, value in obj.__class__.__dict__.items()
        if isinstance(value, op_def.OpDef)
    }
    if not op_attrs:
        raise ValueError("No ops found on object")

    if method_name is None:
        if len(op_attrs) > 1:
            raise ValueError(
                "Multiple ops found on object (%s), must specify method_name argument"
                % ", ".join(op_attrs)
            )
        method_name = next(iter(op_attrs))

    bound_method_op = typing.cast(op_def.OpDef, getattr(obj, method_name))
    if not isinstance(bound_method_op, op_def.OpDef):
        raise ValueError(f"Expected an op, got {bound_method_op}")

    bound_method_op_args = bound_method_op.input_type
    if not isinstance(bound_method_op_args, op_args.OpNamedArgs):
        raise ValueError("predict op must have named args")

    arg_types = bound_method_op_args.weave_type().property_types
    del arg_types["self"]

    Item = weave_pydantic.weave_type_to_pydantic(arg_types, name="Item")

    app = FastAPI()

    @app.post(f"/{method_name}", summary=method_name)
    def method_route(item: Item) -> dict:  # type: ignore
        result = bound_method_op(**item.dict())  # type: ignore
        return {"result": result}

    return app
