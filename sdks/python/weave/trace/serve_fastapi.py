import datetime
import inspect
import typing
from typing import Annotated, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from weave_query import cache, op_args, pyfunc_type_util, weave_pydantic  # type: ignore

from weave.trace import errors
from weave.trace.op import Op, is_op
from weave.trace.refs import ObjectRef
from weave.wandb_interface.wandb_api import WandbApiAsync

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

    attrs: dict[str, Op] = {attr: getattr(obj, attr) for attr in dir(obj)}
    op_attrs = {k: v for k, v in attrs.items() if is_op(v)}

    if not op_attrs:
        raise ValueError("No ops found on object")

    if method_name is None:
        if len(op_attrs) > 1:
            raise ValueError(
                "Multiple ops found on object (%s), must specify method_name argument"
                % ", ".join(op_attrs)
            )
        method_name = next(iter(op_attrs))

    if (method := getattr(obj, method_name, None)) is None:
        raise ValueError(f"Method {method_name} not found")

    if not is_op(unbound_method := method.__func__):
        raise ValueError(f"Expected an op, got {unbound_method}")

    try:
        args = pyfunc_type_util.determine_input_type(unbound_method)
    except errors.WeaveDefinitionError as e:
        raise ValueError(
            f"Type for model's method '{method_name}' could not be determined. Did you annotate it with Python types? {e}"
        )
    if not isinstance(args, op_args.OpNamedArgs):
        raise ValueError("predict op must have named args")

    arg_types = args.weave_type().property_types
    del arg_types["self"]

    Item = weave_pydantic.weave_type_to_pydantic(arg_types, name="Item")

    dependencies = []
    if auth_entity:
        dependencies.append(Depends(wandb_auth(auth_entity)))

    app = FastAPI(dependencies=dependencies)

    @app.post(f"/{method_name}", summary=method_name)
    async def method_route(item: Item) -> dict:  # type: ignore
        if inspect.iscoroutinefunction(method):
            result = await method(**item.dict())  # type: ignore
        else:
            result = method(**item.dict())  # type: ignore
        return {"result": result}

    return app
