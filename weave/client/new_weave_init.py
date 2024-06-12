import threading
from contextlib import contextmanager
from functools import cached_property, partial
from typing import Callable, Optional

import sentry_sdk

from weave import autopatch, trace_sentry
from weave.client.wandb_init import get_username
from weave.trace_server import sqlite_trace_server
from weave.trace_server.remote_http_trace_server import RemoteHTTPTraceServer
from weave.trace_server.trace_server_interface import TraceServerInterface

# class TraceServer:
#     @classmethod
#     def from_env(cls): ...


# Alternatively, mixin for each discrete component:
class CallMixin:
    server: TraceServerInterface

    def get_call(self): ...
    def create_call(self): ...
    def finish_call(self): ...
    def fail_call(self): ...
    def delete_call(self): ...


class ObjectMixin:
    server: TraceServerInterface

    def get_object(self): ...
    def create_object(self): ...


class Api(CallMixin, ObjectMixin):
    server: TraceServerInterface


# Or just use reader/writer more like go
class ReaderInterfaceMixin:
    def get_trace(self): ...
    def get_call(self): ...
    def get_object(self): ...
    def get_op(self): ...


class WriterInterfaceMixin:
    def save_trace(self): ...  # the create, finish, etc. are impl details
    def save_call(self): ...
    def save_object(self): ...
    def save_op(self): ...


class Client(ReaderInterfaceMixin, WriterInterfaceMixin):
    # def __init__(self, *, server: Optional[TraceServerInterface] = None):
    # TODO: remove server arg
    def __init__(self, entity: str, project: str, server=None):
        self.entity = entity
        self.project = project
        # TODO: on init, check the server version and print

    @classmethod
    def from_env(cls):
        ...  # load relevant env and contextvars
        entity = ...
        project = ...
        return cls(entity, project)

    def get(self, ref): ...  # get back from a uri
    def save(self, val, name, branch): ...  # typedispatch the thing to save

    # mixin puts the reader methods here
    # mixin puts the writer methods here


# forget contexts, let's just use globals for now and then revisit
global_client: Optional[Client] = None
global_client_lock = threading.Lock()
# There is also a run context?  idk what this is


def get_global_client() -> Client:
    return global_client


def set_global_client(client: Client) -> None:
    global global_client
    if client is not None and global_client is None:
        with global_client_lock:
            if global_client is None:
                global_client = client

    elif client is None and global_client is not None:
        with global_client_lock:
            if global_client is not None:
                global_client = None


##################################################################


@contextmanager
def temp_weave_context(entity, project):
    client = init_weave(entity, project)
    yield client
    finish_weave()


def init_weave(
    entity: str,
    project: str,
    server: Optional[TraceServerInterface] = None,
) -> Client:
    server = RemoteHTTPTraceServer.from_env()
    client = Client(entity, project, server)

    set_global_client(client)
    # TODO: move gc context to this new global to re-enable
    # autopatch.autopatch()
    sentry_configure_scope(entity, project)

    return client


def finish_weave():
    ...
    # zero out global state
    sentry_reset_scope()

    # TODO: move gc context to this new global to re-enable
    # autopatch.reset_autopatch()
    set_global_client(None)

    # flush any messages stuck in the queue
    ...


def sentry_configure_scope(entity: str, project: str):
    username = get_username()
    user_context = {"username": username} if username else None
    trace_sentry.global_trace_sentry.configure_scope(
        {
            "entity_name": entity,
            "project_name": project,
            "user": user_context,
        }
    )


def sentry_reset_scope():
    with sentry_sdk.configure_scope() as scope:
        scope.clear()


##################################################################


# TODO: more flexible but maybe not necesasry
def init_weave_generic(
    entity: str,
    project: str,
    server_func: Callable[..., TraceServerInterface],
) -> Client:
    server = server_func()
    client = Client(entity, project, server)

    set_global_client(client)
    autopatch.autopatch()
    sentry_configure_scope(entity, project)

    return client


def setup_local():
    server = sqlite_trace_server.SqliteTraceServer("weave.db")
    server.setup_tables()
    return server


init_weave_local = partial(init_weave_generic, server_func=setup_local)
