import wandb
import weave
from weave.weave_internal import const
from .. import context_state as _context

_loading_builtins_token = _context.set_loading_built_ins()


@weave.op(
    returns_expansion_node=True,
)
def lazy_add(a: int, b: int) -> int:
    return const(a) + const(b)  # type: ignore


@weave.op(
    returns_expansion_node=True,
)
def lazy_history(entity_name: str, project_name: str, run_name: str) -> list[dict]:
    return weave.ops.project(entity_name, project_name).run(run_name).history2()


_context.clear_loading_built_ins(_loading_builtins_token)


def test_lazy_add():
    node = lazy_add(1, 2)
    assert weave.use(node) == 3


def test_lazy_history(user_by_api_key_in_env):
    run = wandb.init(project="project_exists")
    for i in range(10):
        run.log({"val": i, "cat": str(i % 2)})
    run.finish()

    history_node = lazy_history(run.entity, run.project, run.id)

    # First assert that the raw history is simple and no projection occurs
    # raw_history = weave.use(history_node)
    # assert raw_history.to_pylist_raw() == [{"_step": i} for i in range(10)]

    # Next, assert that projection works
    history_val = weave.use(history_node["val"])
    assert history_val == list(range(10))
