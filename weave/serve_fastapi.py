import datetime
import inspect
import typing
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials

try:
    from typing import Annotated
# Support python 3.8
except ImportError:
    from typing_extensions import Annotated  # type: ignore

from weave.legacy import cache, op_args
from weave.legacy.artifact_wandb import WandbArtifactRef
from weave.legacy.wandb_api import WandbApiAsync, WandbApiContext, wandb_api_context
from weave.trace import op
from weave.trace.refs import ObjectRef, OpRef
from weave.trace.vals import TraceObject

from . import errors, pyfunc_type_util, weave_pydantic
from . import weave_types as types
from .legacy.monitoring import monitor

key_cache: cache.LruTimeWindowCache[str, typing.Optional[bool]] = (
    cache.LruTimeWindowCache(datetime.timedelta(minutes=5))
)

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
    obj_ref: ObjectRef,
    method_name: typing.Optional[str] = None,
    auth_entity: typing.Optional[str] = None,
) -> FastAPI:
    obj = obj_ref.get()

    attrs: dict[str, op.Op] = {attr: getattr(obj, attr) for attr in dir(obj)}
    op_attrs = {k: v for k, v in attrs.items() if isinstance(v, op.Op)}
    if not op_attrs:
        raise ValueError("No ops found on object")

    if method_name is None:
        if len(op_attrs) > 1:
            raise ValueError(
                "Multiple ops found on object (%s), must specify method_name argument"
                % ", ".join(op_attrs)
            )
        method_name = next(iter(op_attrs))

    bound_method_op = typing.cast(op.Op, getattr(obj, method_name))
    if not isinstance(bound_method_op, op.Op):
        raise ValueError(f"Expected an op, got {bound_method_op}")

    try:
        bound_method_op_args = pyfunc_type_util.determine_input_type(
            bound_method_op.resolve_fn
        )
    except errors.WeaveDefinitionError as e:
        raise ValueError(
            f"Type for model's method '{method_name}' could not be determined. Did you annotate it with Python types? {e}"
        )
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
        if inspect.iscoroutinefunction(bound_method_op.resolve_fn):
            result = await bound_method_op(**item.dict())  # type: ignore
        else:
            result = bound_method_op(**item.dict())  # type: ignore
        return {"result": result}

    return app
