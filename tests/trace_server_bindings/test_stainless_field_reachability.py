"""Every field of a bound request model must have a way to reach the server.

The binding turns a request model into keyword arguments for a generated client method
and sends what the method does not declare through `extra_body` (see
`weave/trace_server_bindings/stainless_request_kwargs.py`). A GET route carries no body,
so there such a field has nowhere to go and the binding raises instead of losing it.

The callsites are read off the binding's source rather than listed, because 24 of the 73
still sit in binding methods that no test in this directory calls, and a hand-written
list would miss the next route the same way. The checks compare signatures instead of
driving requests, because most bound models need a hand-built payload.
"""

from __future__ import annotations

import ast
import functools
import inspect
import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.agents import types as agent_types
from weave.trace_server_bindings import stainless_remote_http_trace_server as binding
from weave.trace_server_bindings.stainless_request_kwargs import (
    NO_BODY_METHODS,
    _declared_params,
)
from weave.vendor.weave_server_sdk import Client as StainlessClient

_MODEL_MODULES = {"tsi": tsi, "agent_types": agent_types}
_CLIENT_PREFIX = "self._stainless_client."
_HELPER = "build_request_kwargs"

# A generated resource method writes its HTTP verb by calling `self._get`, `self._post`
# and so on; nothing else in the vendored client records it.
_VERB = re.compile(r"self\._(get|post|put|delete|patch)\(")


@dataclass(frozen=True)
class _Callsite:
    """One place where the binding turns a request model into client keyword arguments."""

    binding_method: str
    line: int
    model_path: str | None
    api_path: str
    exclude: frozenset[str]

    @property
    def where(self) -> str:
        return f"{self.binding_method}:{self.line}"


@dataclass(frozen=True)
class _Bound(_Callsite):
    """A callsite whose request model and generated method both resolved."""

    model: type[BaseModel]
    api: Any


@functools.cache
def _client() -> StainlessClient:
    return StainlessClient(base_url="http://example.com", username="", password="")


def _attribute(root: Any, path: str) -> Any:
    for part in path.split("."):
        root = getattr(root, part)
    return root


def _own_nodes(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.AST]:
    """Nodes written in `fn` itself, not in a function defined inside it."""
    nested: set[int] = set()
    for node in ast.walk(fn):
        if node is not fn and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nested.update(id(child) for child in ast.walk(node))
    return [n for n in ast.walk(fn) if id(n) not in nested]


def _excluded_fields(call: ast.Call) -> frozenset[str]:
    for keyword in call.keywords:
        if keyword.arg == "exclude":
            return frozenset(ast.literal_eval(e) for e in keyword.value.elts)
    return frozenset()


def _binding_tree() -> ast.Module:
    return ast.parse(inspect.getsource(binding))


def _binding_functions() -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [
        node
        for node in ast.walk(_binding_tree())
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def _is_dump_attribute(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "model_dump"


def _assigned_names(node: ast.AST) -> list[str]:
    """Plain names a statement binds."""
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)):
        targets = [node.target]
    else:
        return []
    return [t.id for t in targets if isinstance(t, ast.Name)]


def _holds_a_dump(value: ast.expr, dumps: set[str]) -> bool:
    """Whether `value` can be a request dump, given names already known to hold one."""
    if isinstance(value, ast.Call):
        return _is_dump_attribute(value.func) or (
            isinstance(value.func, ast.Name) and value.func.id in dumps
        )
    if _is_dump_attribute(value):
        return True
    if isinstance(value, ast.Name):
        return value.id in dumps
    if isinstance(value, ast.NamedExpr):
        return _holds_a_dump(value.value, dumps)
    if isinstance(value, ast.IfExp):
        return _holds_a_dump(value.body, dumps) or _holds_a_dump(value.orelse, dumps)
    if isinstance(value, ast.Dict):
        merged = [
            item
            for key, item in zip(value.keys, value.values, strict=True)
            if key is None
        ]
        return any(_holds_a_dump(item, dumps) for item in merged)
    return False


def _splatted_request_dumps() -> list[str]:
    """Calls that splat a request dump rather than what the helper built.

    The walk is name-level and reads this binding only. It follows a chain of plain
    reassignments, a merge into a dict display, a conditional expression, and a name
    bound to `model_dump` itself. It does not follow a dump that another function
    returns or is handed, one laundered through `dict()`, `|` or `.copy()`, a dict the
    helper filled and a later statement mutated, or anything outside this module.

    It errs towards flagging: any `model_dump` counts, not only a request's, and a name
    that held a dump anywhere in the function keeps counting as one.
    """
    splatted = []
    for scope in _binding_functions():
        dumps: set[str] = set()
        assigned = [
            (name, node.value)
            for node in ast.walk(scope)
            for name in _assigned_names(node)
        ]
        for _ in range(len(assigned)):
            dumps |= {n for n, value in assigned if _holds_a_dump(value, dumps)}
        splatted += [
            f"{scope.name}:{node.lineno}"
            for node in ast.walk(scope)
            if isinstance(node, ast.Call)
            for keyword in node.keywords
            if keyword.arg is None and _holds_a_dump(keyword.value, dumps)
        ]
    return sorted(set(splatted))


def _callsites() -> tuple[_Callsite, ...]:
    found = []
    for fn in _binding_functions():
        annotation = next((a.annotation for a in fn.args.args if a.arg == "req"), None)
        req_model = ast.unparse(annotation) if annotation is not None else None
        for node in _own_nodes(fn):
            if not isinstance(node, ast.Call):
                continue
            callee = ast.unparse(node.func)
            if callee == "self._stainless_request":
                # The helper also excludes the fields the callsite hands to the
                # generated method itself.
                api = next(
                    (a for a in node.args if _CLIENT_PREFIX in ast.unparse(a)), None
                )
                exclude = _excluded_fields(node) | {
                    k.arg for k in node.keywords if k.arg and k.arg != "exclude"
                }
                found.append(
                    _Callsite(
                        fn.name,
                        node.lineno,
                        req_model,
                        ast.unparse(api) if api is not None else "",
                        frozenset(exclude),
                    )
                )
            elif callee == _HELPER:
                dumped = ast.unparse(node.args[0])
                found.append(
                    _Callsite(
                        fn.name,
                        node.lineno,
                        req_model if dumped == "req" else None,
                        ast.unparse(node.args[1]),
                        _excluded_fields(node),
                    )
                )
    return tuple(found)


def _bound_callsites() -> tuple[_Bound, ...]:
    bound = []
    for site in _callsites():
        if site.model_path is None or not site.api_path.startswith(_CLIENT_PREFIX):
            continue
        module, _, model_path = site.model_path.partition(".")
        bound.append(
            _Bound(
                binding_method=site.binding_method,
                line=site.line,
                model_path=site.model_path,
                api_path=site.api_path,
                exclude=site.exclude,
                model=_attribute(_MODEL_MODULES[module], model_path),
                api=_attribute(_client(), site.api_path[len(_CLIENT_PREFIX) :]),
            )
        )
    return tuple(bound)


def _overflow(site: _Bound) -> set[str]:
    """Fields the dump sends that the generated method does not declare."""
    sent = set(site.model.model_fields) - site.exclude
    return sent - _declared_params(site.api.__func__)


def test_no_request_dump_is_splatted_outside_the_helper():
    """Test that a route written without the helper cannot slip past this file."""
    assert _splatted_request_dumps() == []


def test_the_source_walk_still_reads_every_callsite_but_two():
    """Test that the source walk keeps resolving everything it resolved when written."""
    # `_stainless_request` receives the generated method as an argument, and the
    # feedback fallback dumps a batch item rather than its own `req` parameter.
    resolved = {(b.binding_method, b.line) for b in _bound_callsites()}
    unread = sorted(
        s.binding_method
        for s in _callsites()
        if (s.binding_method, s.line) not in resolved
    )

    assert unread == ["_stainless_request", "send_feedback_batch"]


def test_the_no_body_route_list_matches_the_routes_the_binding_calls():
    """Test that the list guarding against a silently dropped body has not gone stale."""
    get_routes = set()
    for site in _bound_callsites():
        verbs = set(_VERB.findall(inspect.getsource(site.api.__func__)))
        assert verbs != set(), (
            f"{site.where}: no HTTP verb found in {site.api.__qualname__}; the "
            f"vendored client's request helpers may have been renamed"
        )
        if verbs == {"get"}:
            get_routes.add(site.api.__qualname__)

    assert get_routes == set(NO_BODY_METHODS)


def test_no_request_field_needs_a_body_on_a_route_that_sends_none():
    """Test that no field on a GET route depends on extra_body, which is dropped there."""
    unsendable = [
        (site.where, site.api.__qualname__, field)
        for site in _bound_callsites()
        if site.api.__qualname__ in NO_BODY_METHODS
        for field in sorted(_overflow(site))
    ]

    assert unsendable == []
