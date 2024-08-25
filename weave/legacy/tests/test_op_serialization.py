import pytest

import weave
import weave.legacy.weave

ops = weave.legacy.weave.registry_mem.memory_registry.list_ops()


def output_type_dict_is_const_function_node(output_type_dict):
    return (
        "nodeType" in output_type_dict
        and output_type_dict["nodeType"] == "const"
        and "type" in output_type_dict["type"]
        and output_type_dict["type"]["type"] == "function"
    )


def const_funtion_node_val(node_dict):
    return node_dict["val"]


def assert_node_dict_free_of_get_ops(node_dict):
    if node_dict["nodeType"] == "output":
        assert node_dict["fromOp"]["name"] != "get"
        for input_node in node_dict["fromOp"]["inputs"].values():
            assert_node_dict_free_of_get_ops(input_node)


def assert_valid_output_type(op_dict):
    output_type_dict = op_dict["output_type"]
    if not output_type_dict_is_const_function_node(output_type_dict):
        return
    assert_node_dict_free_of_get_ops(const_funtion_node_val(output_type_dict))


@pytest.mark.parametrize("op_name, op", [(op.name, op) for op in ops])
def test_explicit_experiment_construction(op_name, op):
    # Just make sure that this is successful
    try:
        op_as_dict = op.to_dict()
    except weave.errors.WeaveSerializeError:
        # Don't check these for now, it indicates the op had a callable output type.
        # We are not currently sending those to WeaveJS
        return
    assert op_as_dict is not None

    print(op_as_dict)
    assert_valid_output_type(op_as_dict)
