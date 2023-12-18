import time
import typing
import os
import dataclasses

from . import urls
from . import graph as _graph
from . import graph_mapper as _graph_mapper
from . import storage as _storage
from . import ref_base as _ref_base
from . import artifact_wandb as _artifact_wandb
from . import wandb_api as _wandb_api
from . import trace as _trace
from . import weave_internal as _weave_internal
from . import errors as _errors
from . import ops as _ops
from . import util as _util
from . import context as _context
from . import context_state as _context_state
from . import graph_client as _graph_client
from . import graph_client_context as _graph_client_context
from weave import monitoring as _monitoring
from weave.monitoring import monitor as _monitor

# exposed as part of api
from . import weave_types as types
from . import types_numpy as _types_numpy
from . import errors
from .decorators import weave_class, op, mutation, type
from .op_args import OpVarArgs
from .op_def import OpDef
from . import usage_analytics
from .context import (
    use_fixed_server_port,
    use_frontend_devmode,
    # eager_execution,
    # lazy_execution,
)
from .server import capture_weave_server_logs
from .val_const import const
from .file_base import File, Dir
from .dispatch import RuntimeConstNode

from .weave_internal import define_fn

Node = _graph.Node


def save(node_or_obj, name=None):
    if isinstance(node_or_obj, _graph.Node):
        return _ops.save(node_or_obj, name=name)
    else:
        # If the user does not provide a branch, then we explicitly set it to
        # the default branch, "latest".
        branch = None
        name_contains_branch = name is not None and ":" in name
        if not name_contains_branch:
            branch = "latest"
        ref = _storage.save(node_or_obj, name=name, branch=branch)
        if name is None:
            # if the user didn't provide a name, the returned reference
            # will be to the specific version
            uri = ref.uri
        else:
            # otherwise the reference will be to whatever branch was provided
            # or the "latest" branch if only a name was provided.
            uri = ref.branch_uri
        return _ops.get(str(uri))


def get(ref_str):
    obj = _storage.get(ref_str)
    ref = _storage._get_ref(obj)
    return _weave_internal.make_const_node(ref.type, obj)


def use(nodes, client=None):
    usage_analytics.use_called()
    if client is None:
        client = _context.get_client()
    return _weave_internal.use(nodes, client)


def _get_ref(obj):
    if isinstance(obj, _storage.Ref):
        return obj
    ref = _storage.get_ref(obj)
    if ref is None:
        raise _errors.WeaveApiError("obj is not a weave object: %s" % obj)
    return ref


def versions(obj):
    if isinstance(obj, _graph.ConstNode):
        obj = obj.val
    elif isinstance(obj, _graph.OutputNode):
        obj = use(obj)
    ref = _get_ref(obj)
    return ref.versions()


def expr(obj):
    ref = _get_ref(obj)
    return _trace.get_obj_expr(ref)


def type_of(obj: typing.Any) -> types.Type:
    return types.TypeRegistry.type_of(obj)


def weave(obj: typing.Any) -> RuntimeConstNode:
    return _weave_internal.make_const_node(type_of(obj), obj)  # type: ignore


def from_pandas(df):
    return _ops.pandas_to_awl(df)


#### Newer API below


def init(project_name: str) -> _graph_client.GraphClient:
    from . import wandb_api
    from . import monitoring

    fields = project_name.split("/")
    if len(fields) == 1:
        api = wandb_api.get_wandb_api_sync()
        try:
            entity_name = api.default_entity_name()
        except AttributeError:
            raise errors.WeaveWandbAuthenticationException(
                'weave init requires wandb. Run "wandb login"'
            )
        project_name = fields[0]
    elif len(fields) == 2:
        entity_name, project_name = fields
    else:
        raise ValueError(
            'project_name must be of the form "<project_name>" or "<entity_name>/<project_name>"'
        )
    if not entity_name:
        raise ValueError("entity_name must be non-empty")
    client = _graph_client.GraphClient(entity_name, project_name)
    _graph_client_context._graph_client.set(client)
    print("Ensure you have the prototype UI running with `weave ui`")
    print(
        f"View project at {urls.project_path(entity_name, project_name)}"
    )
    return client


def publish(obj: typing.Any, name: str) -> _artifact_wandb.WandbArtifactRef:
    if "/" not in name:
        client = _graph_client_context.get_graph_client()
        if not client:
            raise ValueError(
                "Call weave.init() first, or pass <project>/<name> for name"
            )
        name = f"{client.project_name}/{name}"

    ref = _storage.publish(obj, name)  # type: ignore
    print(f"Published {ref.type.root_type_class().name} to {ref.ui_url}")

    # Have to manually put the ref on the obj, this is supposed to happen at
    # a lower level, but we use a mapper in _direct_publish that I think changes
    # the object identity
    _ref_base._put_ref(obj, ref)
    return ref


def ref(uri: str) -> _artifact_wandb.WandbArtifactRef:
    if not "://" in uri:
        client = _graph_client_context.get_graph_client()
        if not client:
            raise ValueError("Call weave.init() first, or pass a fully qualified uri")
        if "/" in uri:
            raise ValueError("'/' not currently supported in short-form URI")
        name_version = uri
        if ":" not in name_version:
            name_version = f"{name_version}:latest"
        uri = f"wandb-artifact:///{client.entity_name}/{client.project_name}/{name_version}/obj"

    ref = _ref_base.Ref.from_str(uri)
    if not isinstance(ref, _artifact_wandb.WandbArtifactRef):
        raise ValueError(f"Expected a wandb artifact ref, got {ref}")
    ref.type
    return ref


import contextlib


@contextlib.contextmanager
def attributes(attributes: typing.Dict[str, typing.Any]) -> typing.Iterator:
    cur_attributes = {**_monitor._attributes.get()}
    cur_attributes.update(attributes)

    token = _monitor._attributes.set(cur_attributes)
    try:
        yield
    finally:
        _monitor._attributes.reset(token)


def serve(
    model_ref: _artifact_wandb.WandbArtifactRef,
    method_name: typing.Optional[str] = None,
    auth_entity: typing.Optional[str] = None,
    port: int = 9996,
    thread: bool = False,
) -> typing.Optional[str]:
    import uvicorn
    from .serve_fastapi import object_method_app

    client = _graph_client_context.require_graph_client()

    print(f"Serving {model_ref}")
    print(f"Server docs at http://localhost:{port}/docs")
    os.environ["PROJECT_NAME"] = client.entity_project
    os.environ["MODEL_REF"] = str(model_ref)

    wandb_api_ctx = _wandb_api.get_wandb_api_context()
    app = object_method_app(model_ref, method_name=method_name, auth_entity=auth_entity)
    trace_attrs = _monitor._attributes.get()

    def run():
        with _wandb_api.wandb_api_context(wandb_api_ctx):
            with _context_state.eager_execution():
                with _context.execution_client():
                    with attributes(trace_attrs):
                        uvicorn.run(app, host="0.0.0.0", port=port)

    if _util.is_notebook():
        thread = True
    if thread:
        from threading import Thread

        t = Thread(target=run, daemon=True)
        t.start()
        time.sleep(1)
        return "http://localhost:%d" % port
    else:
        run()
    return None
