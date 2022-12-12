import pytest

from weave.ops_primitives import list_
from .. import graph
from ..weave_internal import make_const_node
from .. import weave_types as types
from .. import api
from .. import ops
from .. import serialize
from .. import registry_mem
from .. import op_args
import weave
from . import fixture_fakewandb as fwb

response = {
    "project": {
        **fwb.project_payload,  # type: ignore
        "artifact_deb0808078813ae7a9f36b68caf5bedc": fwb.artifactVersion_payload,
    }
}


def test_serialize(fake_wandb):
    fake_wandb.add_mock(lambda q, ndx: response)
    proj = ops.project("stacey", "mendeleev")
    av = proj.artifactVersion("test_res_1fwmcd3q", "v0")
    file = av.file("test_results.table.json")
    table = file.table()
    rows = table.rows()
    filter_fn = api.define_fn(
        {"row": types.TypedDict({})}, lambda row: row["new"] + 100
    )
    filtered = rows.map(filter_fn)

    ser = serialize.serialize([filtered])
    deser = serialize.deserialize(ser)
    ser2 = serialize.serialize(deser)
    assert ser == ser2


def test_serialize_nested_function():
    rows = api.save([{"a": [1, 2]}])
    filtered = rows.filter(
        api.define_fn(
            {"row": types.TypedDict({"a": types.List(types.Int())})},
            lambda row: ops.numbers_avg(
                row["a"].map(api.define_fn({"row": types.Int()}, lambda row: row + 1))
            ),
        )
    )

    ser = serialize.serialize([filtered])
    deser = serialize.deserialize(ser)
    ser2 = serialize.serialize(deser)
    assert ser == ser2


@pytest.mark.skip(reason="we allow this now")
def test_op_compat():
    ops = registry_mem.memory_registry.list_ops()
    issues = []
    for a in range(len(ops) - 1):
        for b in range(a + 1, len(ops)):
            a_op = ops[a]
            b_op = ops[b]

            if not isinstance(a_op.input_type, op_args.OpNamedArgs) or not isinstance(
                b_op.input_type, op_args.OpNamedArgs
            ):
                continue

            a_op_common_name = a_op.common_name
            b_op_common_name = b_op.common_name

            if a_op_common_name != b_op_common_name:
                continue

            a_assign_has_invalid = False
            b_assign_has_invalid = False
            for a_arg, b_arg in zip(
                a_op.input_type.arg_types.values(), b_op.input_type.arg_types.values()
            ):
                if callable(a_arg) or callable(b_arg):
                    continue

                if not a_assign_has_invalid:
                    if not a_arg.assign_type(b_arg):
                        a_assign_has_invalid = True

                if not b_assign_has_invalid:
                    if not b_arg.assign_type(a_arg):
                        b_assign_has_invalid = True

                if a_assign_has_invalid and b_assign_has_invalid:
                    break

            if not a_assign_has_invalid and not b_assign_has_invalid:
                issues.append(
                    f"Ops {a_op.name} and {b_op.name} are parametrically ambiguous"
                )
            elif not a_assign_has_invalid:
                issues.append(f"Op {b_op.name} is strictly bound by op {a_op.name}")
            elif not b_assign_has_invalid:
                issues.append(f"Op {a_op.name} is strictly bound by op {b_op.name}")
    if len(issues) > 0:
        sep = "\n\t*  "
        raise Exception("Found op ambiguities:" + sep + sep.join(issues))


@pytest.mark.parametrize(
    "val_type, val",
    [
        # Case 0: ConstNode, no const type, normal val
        (types.String(), "hello"),
        # Case 1: ConstNode, no const type, type val
        (types.TypeType(), types.String()),
        # Case 2: ConstNode, const type, normal val
        (types.Const(types.String(), "hello"), "hello"),
        # Case 3: ConstNode, const type, type val
        (types.Const(types.TypeType(), types.String()), types.String()),
    ],
)
def test_const_node_serialize(val_type, val):
    node = make_const_node(val_type, val)
    node = graph.Node.node_from_json(node.to_json())
    assert node.type == val_type
    assert node.val == val


def test_union_dicts():
    nodeA = make_const_node(types.TypedDict({"a": types.Int()}), {"a": 1})
    nodeB = make_const_node(types.TypedDict({"b": types.Int()}), {"b": 1})
    nodeC = list_.make_list(a=nodeA, b=nodeB)
    nodeD = nodeC["a"]
    assert weave.use(nodeD) == [1, None]
