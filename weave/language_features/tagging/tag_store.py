"""
This file contains the data structures and methods used to manage the in-memory
state of tagged objects. Crticailly, it relies on two private global objects:

* `_OBJ_TAGS_MEM_MAP` - used to map the python id of an object to a dictionary of
    tags. This is used to store the tags for an object.
* `_VISITED_OBJ_IDS` - used to keep track of the python ids of objects that are
    currently being visited. This is used to prevent infinite recursion when
    determing the type of tagged objects.

The primary user-facing functions are:

* `add_tags` - used to add tags to an object
* `find_tag` - used to recursively lookup the tag for a given object

"""
import logging
import contextvars
from contextlib import contextmanager
import typing
import weakref


from ... import box
from ... import weave_types as types
from ... import errors


from ... import engine_trace

from collections import defaultdict

statsd = engine_trace.statsd()  # type: ignore

NodeTagStoreType = dict[int, dict[str, typing.Any]]
TagStoreType = defaultdict[int, NodeTagStoreType]


# Private global objects used to store the tags for objects
_OBJ_TAGS_MEM_MAP: contextvars.ContextVar[
    typing.Optional[TagStoreType]  # shape: {node_id: {obj_id: {tag_key: tag_value}}}
] = contextvars.ContextVar("obj_tags_mem_map", default=None)

# Current node id for scoping tags
_OBJ_TAGS_CURR_NODE_ID: contextvars.ContextVar[int] = contextvars.ContextVar(
    "obj_tags_curr_node", default=-1
)


# gets the current tag memory map for the current node
def _current_obj_tag_mem_map() -> typing.Optional[NodeTagStoreType]:
    node_tags = _OBJ_TAGS_MEM_MAP.get()
    if node_tags is None:
        return None
    return node_tags[_OBJ_TAGS_CURR_NODE_ID.get()]


def current_tag_store_size() -> int:
    current_mmap = _OBJ_TAGS_MEM_MAP.get()
    if current_mmap is not None:
        n_tag_store_entries = sum(len(current_mmap[key]) for key in current_mmap)
    else:
        n_tag_store_entries = 0
    return n_tag_store_entries


def record_current_tag_store_size() -> None:
    n_tag_store_entries = current_tag_store_size()
    logging.info(f"Current number of tag store entries: {n_tag_store_entries}")
    statsd.gauge("weave.tag_store.num_entries", n_tag_store_entries)


@contextmanager
def with_tag_store_state(
    curr_node_id: int, tags_mem_map: typing.Optional[TagStoreType]
) -> typing.Iterator[None]:
    tag_store_token = _OBJ_TAGS_MEM_MAP.set(tags_mem_map)
    curr_node_id_token = _OBJ_TAGS_CURR_NODE_ID.set(curr_node_id)
    yield
    _OBJ_TAGS_CURR_NODE_ID.reset(curr_node_id_token)
    _OBJ_TAGS_MEM_MAP.reset(tag_store_token)


# sets the current node with optionally merged in parent tags
@contextmanager
def set_curr_node(node_id: int, parent_node_ids: list[int]) -> typing.Iterator[None]:
    node_tags = _OBJ_TAGS_MEM_MAP.get()
    if node_tags is None:
        raise errors.WeaveInternalError("No tag store context")
    token = _OBJ_TAGS_CURR_NODE_ID.set(node_id)
    for parent_id in parent_node_ids:
        node_tags[node_id].update(node_tags[parent_id])
    try:
        yield None
    finally:
        _OBJ_TAGS_CURR_NODE_ID.reset(token)


# Private global objects used to keep track of the python ids of objects that are
# currently being visited.
_VISITED_OBJ_IDS: contextvars.ContextVar[set[int]] = contextvars.ContextVar(
    "visited_obj_ids", default=set()
)


# Callers can create an isolated tagging context by using this context manager
# This is primarily used by the executor to prevent tags from leaking between
# different executions. See execute.py for it's usage.
# Only creates a new context for the top-level call in the stack. Re-entrant calls
# will use the same context.
@contextmanager
def isolated_tagging_context() -> typing.Iterator[None]:
    created_context = False
    if _OBJ_TAGS_MEM_MAP.get() is None:
        created_context = True
        token = _OBJ_TAGS_MEM_MAP.set(defaultdict(dict))
    try:
        yield None
    finally:
        if created_context:
            _OBJ_TAGS_MEM_MAP.reset(token)


@contextmanager
def new_tagging_context() -> typing.Iterator[None]:
    token = _OBJ_TAGS_MEM_MAP.set(defaultdict(dict))
    try:
        yield None
    finally:
        _OBJ_TAGS_MEM_MAP.reset(token)


# Callers can indicate that an object is being visited by using this context manager
# This is primarily used by the TaggedValueType::type_of_instance method to prevent
# infinite recursion when determining the type of tagged objects.
@contextmanager
def with_visited_obj(obj: typing.Any) -> typing.Iterator[None]:
    id_val = get_id(obj)
    assert id_val == get_id(box.box(obj)), "Can only tag boxed objects"
    visited_obj_ids = _VISITED_OBJ_IDS.get()
    visited_obj_ids.add(id_val)
    try:
        yield None
    finally:
        visited_obj_ids.remove(id_val)


def _remove_tags(mem_map: dict[int, typing.Any], id_val: int) -> None:
    node_tags = _OBJ_TAGS_MEM_MAP.get()
    if node_tags is None:
        return
    # The tags can be on any node, so we need to check all of them.
    # This is algorithmically inefficient and could be a serious performance
    # problem.
    for node_id, tag_map in node_tags.items():
        if id_val in tag_map:
            del tag_map[id_val]


def get_id(obj: typing.Any) -> int:
    if box.cannot_have_weakref(obj):
        if obj._id is not None:
            return obj._id
        obj._id = box.make_id()
        return obj._id
    return id(obj)


# Adds a dictionary of tags to an object
def add_tags(
    obj: typing.Any,
    tags: dict[str, typing.Any],
    give_precedence_to_existing_tags: bool = False,
) -> typing.Any:
    mem_map = _current_obj_tag_mem_map()
    if mem_map is None:
        raise errors.WeaveInternalError("No tag store context")
    id_val = get_id(obj)
    if not box.cannot_have_weakref(obj) and id_val not in mem_map:
        # Ensure we cleanup the tags when the object is garbage collected.
        # Python is happy to reuse IDs after they are freed!
        try:
            weakref.finalize(obj, _remove_tags, mem_map, id_val)
        except:
            # Extreme bug here!
            # Can't box pydantic objects, like those from langchain.
            # TODO: fix
            pass
    assert box.is_boxed(obj), "Can only tag boxed objects"
    existing_tags = get_tags(obj) if is_tagged(obj) else {}
    if give_precedence_to_existing_tags:
        mem_map[id_val] = {**tags, **existing_tags}
    else:
        mem_map[id_val] = {**existing_tags, **tags}
    return obj


# Gets the dictionary of tags assocaited with the given object
# Note: this is not recursive, it only returns the tags directly assocaited with
# the given object
def get_tags(obj: typing.Any) -> dict[str, typing.Any]:
    id_val = get_id(obj)
    if id_val in _VISITED_OBJ_IDS.get():
        raise ValueError("Cannot get tags for an object that is being visited")

    current_mem_map = _current_obj_tag_mem_map()
    if current_mem_map is None:
        return {}
    if id_val not in current_mem_map:
        return {}
    return current_mem_map[id_val]


# Recursively looks up the tag for the object, given a key and target tag_type.
def find_tag(
    obj: typing.Any, key: str, tag_type: types.Type = types.Any()
) -> typing.Any:
    # TODO: Implement tag type filtering using tag_type
    cur_tags = get_tags(obj)
    if key in cur_tags:
        return cur_tags[key]
    else:
        for parent in cur_tags.values():
            if is_tagged(parent):
                par_tag = find_tag(parent, key)
                if par_tag is not None:
                    return par_tag
    return None


# Returns true if the given object has been tagged
def is_tagged(obj: typing.Any) -> bool:
    id_val = get_id(obj)
    if id_val in _VISITED_OBJ_IDS.get():
        return False
    mem_map = _current_obj_tag_mem_map()
    if mem_map is None:
        return False

    return id_val in mem_map


def clear_tag_store() -> None:
    tag_store = _OBJ_TAGS_MEM_MAP.get()
    cur_obj_tag_mem_map = _OBJ_TAGS_CURR_NODE_ID.get()

    if tag_store is not None:
        tag_store.clear()

    if cur_obj_tag_mem_map is not None:
        _OBJ_TAGS_CURR_NODE_ID.set(-1)
