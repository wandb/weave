import typing
import datetime
import inspect
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from typing import Optional

try:
    from typing import Annotated
# Support python 3.8
except ImportError:
    from typing_extensions import Annotated  # type: ignore

from . import weave_types as types
from . import op_args
from . import weave_pydantic
from . import op_def
from . import cache
from .monitoring import monitor
from .wandb_api import WandbApiAsync, wandb_api_context, WandbApiContext

from .artifact_wandb import WandbArtifactRef

key_cache: cache.LruTimeWindowCache[
    str, typing.Optional[bool]
] = cache.LruTimeWindowCache(datetime.timedelta(minutes=5))

api: Optional[WandbApiAsync] = None


def wandb_auth(
    entity: str,
) -> typing.Callable[
    [typing.Optional[str]], typing.Coroutine[typing.Any, typing.Any, bool]
]:
    async def auth_inner(key: Annotated[Optional[str], Depends(api_key)]) -> bool:
        global api
        if api is None:
            api = WandbApiAsync()
        if key is None:
            raise HTTPException(status_code=401, detail="Missing API Key")
        if len(key.split("-")[-1]) != 40:
            raise HTTPException(status_code=401, detail="Invalid API Key")

        authed = key_cache.get(key)
        if isinstance(authed, bool):
            return authed
        authed = await api.can_access_entity(entity, api_key=key)
        if not authed:
            raise HTTPException(status_code=403, detail="Permission Denied")
        key_cache.set(key, authed)
        return authed

    return auth_inner


def api_key(
    credentials: Annotated[
        Optional[HTTPBasicCredentials],
        Depends(
            HTTPBasic(
                auto_error=False,
                description="Set your username to api and password to a W&B API Key",
            )
        ),
    ],
    x_wandb_api_key: Annotated[
        Optional[str], Header(description="Optional W&B API Key")
    ] = None,
) -> Optional[str]:
    if x_wandb_api_key:
        return x_wandb_api_key
    elif credentials and credentials.password:
        return credentials.password
    else:
        return None


def object_method_app(
    obj_ref: WandbArtifactRef,
    method_name: typing.Optional[str] = None,
    auth_entity: typing.Optional[str] = None,
) -> FastAPI:
    # Import weaveflow to trigger eager mode and ensure we have weaveflow weave
    # types loaded.
    from weave import weaveflow

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

    dependencies = []
    if auth_entity:
        dependencies.append(Depends(wandb_auth(auth_entity)))

    app = FastAPI(dependencies=dependencies)

    @app.post(f"/{method_name}", summary=method_name)
    async def method_route(item: Item) -> dict:  # type: ignore
        if inspect.iscoroutinefunction(bound_method_op.raw_resolve_fn):
            result = await bound_method_op(**item.dict())  # type: ignore
        else:
            result = bound_method_op(**item.dict())  # type: ignore
        return {"result": result}

    return app
