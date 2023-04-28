import wandb
import pytest
import weave
import os
import json
from contextlib import contextmanager

from weave.artifact_local import LocalArtifact


@weave.type()
class RawElement:
    internal: str


@weave.type()
class RawData:
    elements: list[RawElement]


@pytest.mark.parametrize(
    "raw_data",
    [
        # Primitive types
        1,
        # Container types
        [1, 2, 3],
        # Custom Types
        RawElement("test"),
        # Nested types
        RawData([RawElement("1"), RawElement("2"), RawElement("3")]),
    ],
)
def test_local_save(raw_data):
    raw_ref = weave.storage.save(raw_data, "raw_data")
    raw_uri = raw_ref.uri
    new_ref = weave.ref_base.Ref.from_str(raw_uri)
    new_data = new_ref.get()
    assert id(raw_data) != id(new_data)
    assert raw_data == new_data


def _assert_path_contents(path: str, contents: dict):
    assert os.path.exists(path)
    entries = os.listdir(path)
    entries_set = set(entries)
    content_set = set(list(contents.keys()))
    assert len(content_set - entries_set) == 0

    for subpath, content in contents.items():
        if content == None:
            continue
        with open(os.path.join(path, subpath)) as f:
            content_json = json.load(f)

        assert content_json == content


@contextmanager
def _ref_equality_patch():
    old_eq = weave.ref_base.Ref.__eq__
    weave.ref_base.Ref.__eq__ = (
        lambda self, other: isinstance(other, weave.ref_base.Ref)
        and self.obj == other.obj
    )
    try:
        yield
    finally:
        weave.ref_base.Ref.__eq__ = old_eq


def _assert_equal_values(a, b):
    with _ref_equality_patch():
        assert a == b


def _assert_equal_nodes(a, b):
    assert a.to_json() == b.to_json()


def _get_uri_from_get_node(node):
    return node.from_op.inputs["uri"].val


def _assert_uri_is_locally_saved(uri):
    assert uri.startswith("local-artifact://")


def _assert_uri_is_remotely_published(uri):
    assert uri.startswith("wandb-artifact://")


def _get_local_dir_from_uri(uri):
    art = weave.ref_base.Ref.from_str(uri).artifact
    if isinstance(art, LocalArtifact):
        return art._read_dirname
    else:
        return art._saved_artifact.download()


def _test_save_or_publish(user_data, contents, use_publish=False, exp_user_data=None):
    if exp_user_data is None:
        exp_user_data = user_data
    if use_publish:
        saved_node = weave.publish(user_data)
    else:
        saved_node = weave.save(user_data)

    # Step 1: Verify the loaded object is equal to the original object
    saved_value = weave.use(saved_node)
    if isinstance(exp_user_data, weave.graph.Node):
        _assert_equal_nodes(saved_value, exp_user_data)
    else:
        _assert_equal_values(saved_value, exp_user_data)

    # Step 2: Verify serialized representation is correct
    uri = _get_uri_from_get_node(saved_node)
    if use_publish:
        _assert_uri_is_remotely_published(uri)
    else:
        _assert_uri_is_locally_saved(uri)

    local_dir = _get_local_dir_from_uri(uri)

    _assert_path_contents(local_dir, contents)


def _test_save(user_data, contents, exp_user_data=None):
    _test_save_or_publish(user_data, contents, False, exp_user_data)


def _test_publish(user_data, contents, exp_user_data=None):
    _test_save_or_publish(user_data, contents, True, exp_user_data)


def _test_simple_value(test_method):
    test_method(
        1,
        {
            "obj.type.json": "int",
            "obj.object.json": 1,
        },
    )


def test_simple_value_save():
    _test_simple_value(_test_save)


def test_simple_value_publish(use_local_wandb_backend):
    _test_simple_value(_test_publish)


def _test_simple_node(test_method):
    test_method(
        weave.ops.make_const_node(weave.types.Int(), 1),
        {
            "obj.type.json": {
                "inputTypes": {},
                "outputType": "int",
                "type": "function",
            },
            "obj.object.json": {"nodeType": "const", "type": "int", "val": 1},
        },
    )


def test_simple_node_save():
    _test_simple_node(_test_save)


def test_simple_node_publish(use_local_wandb_backend):
    _test_simple_node(_test_publish)


def _test_structured_value(test_method):
    test_method(
        [{"a": 1}, {"a": 2}],
        {
            "obj.type.json": {
                "objectType": {"propertyTypes": {"a": "int"}, "type": "typedDict"},
                "type": "list",
            },
            "obj.list.json": [{"a": 1}, {"a": 2}],
        },
    )


def test_structured_value_save():
    _test_structured_value(_test_save)


def test_structured_value_publish(use_local_wandb_backend):
    _test_structured_value(_test_publish)


def _test_structured_node(test_method):
    test_method(
        weave.ops.make_list(a=weave.ops.dict_(a=1), b=weave.ops.dict_(a=2)),
        {
            "obj.type.json": {
                "type": "function",
                "inputTypes": {},
                "outputType": {
                    "type": "list",
                    "objectType": {"type": "typedDict", "propertyTypes": {"a": "int"}},
                },
            },
            "obj.object.json": {
                "nodeType": "output",
                "type": {
                    "type": "list",
                    "objectType": {"type": "typedDict", "propertyTypes": {"a": "int"}},
                },
                "fromOp": {
                    "name": "list",
                    "inputs": {
                        "a": {
                            "nodeType": "output",
                            "type": {
                                "type": "typedDict",
                                "propertyTypes": {"a": "int"},
                            },
                            "fromOp": {
                                "name": "dict",
                                "inputs": {
                                    "a": {"nodeType": "const", "type": "int", "val": 1}
                                },
                            },
                        },
                        "b": {
                            "nodeType": "output",
                            "type": {
                                "type": "typedDict",
                                "propertyTypes": {"a": "int"},
                            },
                            "fromOp": {
                                "name": "dict",
                                "inputs": {
                                    "a": {"nodeType": "const", "type": "int", "val": 2}
                                },
                            },
                        },
                    },
                },
            },
        },
    )


def test_structured_node_save():
    _test_structured_node(_test_save)


def test_structured_node_publish(use_local_wandb_backend):
    _test_structured_node(_test_publish)


def _test_referential_saved_value(test_method):
    saved_a_node = weave.save({"a": 1})
    saved_a_value = weave.use(saved_a_node)
    uri = _get_uri_from_get_node(saved_a_node)
    test_method(
        [saved_a_value, {"a": 2}],
        {
            "obj.type.json": {
                "type": "list",
                "objectType": {
                    "type": "union",
                    "members": [
                        {
                            "type": "Ref",
                            "objectType": {
                                "type": "typedDict",
                                "propertyTypes": {"a": "int"},
                            },
                        },
                        {"type": "typedDict", "propertyTypes": {"a": "int"}},
                    ],
                },
            },
            "obj.list.json": [{"_union_id": 0, "_val": uri}, {"a": 2, "_union_id": 1}],
        },
        [saved_a_value._ref, {"a": 2}],
    )


def test_referential_saved_value_save():
    _test_referential_saved_value(_test_save)


def test_referential_saved_value_publish(use_local_wandb_backend):
    _test_referential_saved_value(_test_publish)
    assert False  # TODO (Tim): We actually need to modify this so that we check for the correctly modified internal URI


def _test_referential_saved_node(test_method):
    saved_a_node = weave.save(weave.ops.dict_(a=1))
    uri = _get_uri_from_get_node(saved_a_node)
    test_method(
        weave.ops.make_list(a=saved_a_node, b=weave.ops.dict_(a=2)),
        {
            "obj.type.json": {
                "type": "function",
                "inputTypes": {},
                "outputType": {
                    "type": "list",
                    "objectType": {
                        "type": "union",
                        "members": [
                            {
                                "type": "function",
                                "inputTypes": {},
                                "outputType": {
                                    "type": "typedDict",
                                    "propertyTypes": {"a": "int"},
                                },
                            },
                            {"type": "typedDict", "propertyTypes": {"a": "int"}},
                        ],
                    },
                },
            },
            "obj.object.json": {
                "nodeType": "output",
                "type": {
                    "type": "list",
                    "objectType": {
                        "type": "union",
                        "members": [
                            {
                                "type": "function",
                                "inputTypes": {},
                                "outputType": {
                                    "type": "typedDict",
                                    "propertyTypes": {"a": "int"},
                                },
                            },
                            {"type": "typedDict", "propertyTypes": {"a": "int"}},
                        ],
                    },
                },
                "fromOp": {
                    "name": "list",
                    "inputs": {
                        "a": {
                            "nodeType": "output",
                            "type": {
                                "type": "function",
                                "inputTypes": {},
                                "outputType": {
                                    "type": "typedDict",
                                    "propertyTypes": {"a": "int"},
                                },
                            },
                            "fromOp": {
                                "name": "get",
                                "inputs": {
                                    "uri": {
                                        "nodeType": "const",
                                        "type": "string",
                                        "val": uri,
                                    }
                                },
                            },
                        },
                        "b": {
                            "nodeType": "output",
                            "type": {
                                "type": "typedDict",
                                "propertyTypes": {"a": "int"},
                            },
                            "fromOp": {
                                "name": "dict",
                                "inputs": {
                                    "a": {"nodeType": "const", "type": "int", "val": 2}
                                },
                            },
                        },
                    },
                },
            },
        },
    )


def test_referential_saved_node_save():
    _test_referential_saved_node(_test_save)


def test_referential_saved_node_publish(use_local_wandb_backend):
    _test_referential_saved_node(_test_publish)
    assert False  # TODO (Tim): We actually need to modify this so that we check for the correctly modified internal URI


def _test_referential_published_value(test_method):
    saved_a_node = weave.publish({"a": 1})
    saved_a_value = weave.use(saved_a_node)
    uri = _get_uri_from_get_node(saved_a_node)
    test_method(
        [saved_a_value, {"a": 2}],
        {
            "obj.type.json": {
                "type": "list",
                "objectType": {
                    "type": "union",
                    "members": [
                        {
                            "type": "Ref",
                            "objectType": {
                                "type": "typedDict",
                                "propertyTypes": {"a": "int"},
                            },
                        },
                        {"type": "typedDict", "propertyTypes": {"a": "int"}},
                    ],
                },
            },
            "obj.list.json": [{"_union_id": 0, "_val": uri}, {"a": 2, "_union_id": 1}],
        },
        [saved_a_value._ref, {"a": 2}],
    )


def test_referential_published_value_save(use_local_wandb_backend):
    _test_referential_published_value(_test_save)


def test_referential_published_value_publish(use_local_wandb_backend):
    _test_referential_published_value(_test_publish)


def _test_referential_published_node(test_method):
    saved_a_node = weave.publish(weave.ops.dict_(a=1))
    uri = _get_uri_from_get_node(saved_a_node)
    test_method(
        weave.ops.make_list(a=saved_a_node, b=weave.ops.dict_(a=2)),
        {
            "obj.type.json": {
                "type": "function",
                "inputTypes": {},
                "outputType": {
                    "type": "list",
                    "objectType": {
                        "type": "union",
                        "members": [
                            {
                                "type": "function",
                                "inputTypes": {},
                                "outputType": {
                                    "type": "typedDict",
                                    "propertyTypes": {"a": "int"},
                                },
                            },
                            {"type": "typedDict", "propertyTypes": {"a": "int"}},
                        ],
                    },
                },
            },
            "obj.object.json": {
                "nodeType": "output",
                "type": {
                    "type": "list",
                    "objectType": {
                        "type": "union",
                        "members": [
                            {
                                "type": "function",
                                "inputTypes": {},
                                "outputType": {
                                    "type": "typedDict",
                                    "propertyTypes": {"a": "int"},
                                },
                            },
                            {"type": "typedDict", "propertyTypes": {"a": "int"}},
                        ],
                    },
                },
                "fromOp": {
                    "name": "list",
                    "inputs": {
                        "a": {
                            "nodeType": "output",
                            "type": {
                                "type": "function",
                                "inputTypes": {},
                                "outputType": {
                                    "type": "typedDict",
                                    "propertyTypes": {"a": "int"},
                                },
                            },
                            "fromOp": {
                                "name": "get",
                                "inputs": {
                                    "uri": {
                                        "nodeType": "const",
                                        "type": "string",
                                        "val": uri,
                                    }
                                },
                            },
                        },
                        "b": {
                            "nodeType": "output",
                            "type": {
                                "type": "typedDict",
                                "propertyTypes": {"a": "int"},
                            },
                            "fromOp": {
                                "name": "dict",
                                "inputs": {
                                    "a": {"nodeType": "const", "type": "int", "val": 2}
                                },
                            },
                        },
                    },
                },
            },
        },
    )


def test_referential_published_node_save(use_local_wandb_backend):
    _test_referential_published_node(_test_save)


def test_referential_published_node_publish(use_local_wandb_backend):
    _test_referential_published_node(_test_publish)
