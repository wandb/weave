import typing

import wandb

import weave
from weave.legacy.weave import context_state as _context
from weave.legacy.weave.wandb_interface.wandb_stream_table import StreamTable

from ...legacy.weave.panels_py import generator_templates

_loading_builtins_token = _context.set_loading_built_ins()


@weave.type()
class DummyBoardConfig:
    pass


board_input_type = weave.types.List(
    weave.types.TypedDict({"a": weave.types.optional(weave.types.String())})
)


@weave.op(  # type: ignore
    name="py_board-dummy_board",
    hidden=True,
    input_type={
        "input_node": weave.types.Function(
            {},
            board_input_type,
        )
    },
)
def dummy_board(
    input_node,
    config: typing.Optional[DummyBoardConfig] = None,
) -> weave.legacy.weave.panels.Group:
    assert board_input_type.assign_type(input_node.type)

    control_items = [
        weave.legacy.weave.panels.GroupPanel(
            input_node,
            id="data",
        ),
    ]

    return weave.legacy.weave.panels.Board(vars=control_items, panels=[])


generator_templates.template_registry.register(
    "py_board-dummy_board",
    "Simple Board",
    "Seed a board with a simple visualization of this table.",
)

_context.clear_loading_built_ins(_loading_builtins_token)


def assert_valid_node(node):
    _assert_valid_node_raw(node)

    # This part of the test simulates what happens when JS makes
    # a request since it is not guaranteed to know the correct type.
    node.type = weave.types.Any()
    _assert_valid_node_raw(node)


def _assert_valid_node_raw(node):
    templates_node = generator_templates.get_board_templates_for_node(node)

    templates = weave.use(templates_node)

    # Assert that the dummy board is successfully assigned
    assert len([t for t in templates if t["op_name"] == "py_board-dummy_board"]) == 1

    dummy_node = dummy_board(node, None)
    output_group = weave.use(dummy_node)

    # Assert the out template is successfully generated
    assert isinstance(output_group, weave.legacy.weave.panels.Group)

    data_node = output_group.config.items["sidebar"].config.items["data"]

    # assert that the node sent to the generator is the same as the node that is used
    # Note: this is a heuristic, but probably close enough
    assert isinstance(data_node, weave.legacy.weave.graph.OutputNode)
    assert data_node.from_op.name == node.from_op.name
    assert str(data_node) == str(node)


def assert_invalid_node(node):
    templates_node = generator_templates.get_board_templates_for_node(node)

    templates = weave.use(templates_node)

    assert len([t for t in templates if t["op_name"] == "py_board-dummy_board"]) == 0


def test_templates_for_run_logs_valid(user_by_api_key_in_env):
    run = wandb.init(project="project_exists")
    run.log({"a": "hello"})
    run.finish()

    run_history_node = (
        weave.legacy.weave.ops.project(run.entity, run.project).run(run.id).history()
    )

    assert_valid_node(run_history_node)


def test_templates_for_run_logs_invalid(user_by_api_key_in_env):
    run = wandb.init(project="project_exists")
    run.log({"a": 42})
    run.finish()

    run_history_node = (
        weave.legacy.weave.ops.project(run.entity, run.project).run(run.id).history()
    )

    assert_invalid_node(run_history_node)


def test_templates_for_logged_table_valid(user_by_api_key_in_env):
    run = wandb.init(project="project_exists")
    run.log({"table": wandb.Table(data=[["hello"]], columns=["a"])})
    run.finish()

    table_node = (
        weave.legacy.weave.ops.project(run.entity, run.project)
        .run(run.id)
        .summary()["table"]
        .table()
        .rows()
    )

    assert_valid_node(table_node)


def test_templates_for_logged_table_invalid(user_by_api_key_in_env):
    run = wandb.init(project="project_exists")
    run.log({"table": wandb.Table(data=[[42]], columns=["a"])})
    run.finish()

    table_node = (
        weave.legacy.weave.ops.project(run.entity, run.project)
        .run(run.id)
        .summary()["table"]
        .table()
        .rows()
    )

    assert_invalid_node(table_node)


def test_templates_for_stream_table_valid(user_by_api_key_in_env):
    st = StreamTable(
        "test_table",
        project_name="stream-tables",
        entity_name=user_by_api_key_in_env.username,
        _disable_async_file_stream=True,
    )
    st.log({"a": "hello"})
    st.finish()

    rows_node = st.rows()

    assert_valid_node(rows_node)


def test_templates_for_stream_table_invalid(user_by_api_key_in_env):
    st = StreamTable(
        "test_table",
        project_name="stream-tables",
        entity_name=user_by_api_key_in_env.username,
        _disable_async_file_stream=True,
    )
    st.log({"a": 1})
    st.finish()

    rows_node = st.rows()

    assert_invalid_node(rows_node)
