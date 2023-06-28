import time
import weave
import wandb
from weave import weave_internal
from weave import weave_types as types
from weave.ecosystem.wandb.panel_time_series import TimeSeries


# Example of end to end integration test
def test_run_logging(user_by_api_key_in_env):
    run = wandb.init(project="project_exists")
    run.log({"a": 1})
    run.finish()

    summary_node = weave.ops.project(run.entity, run.project).run(run.id).summary()["a"]
    summary = weave.use(summary_node)

    assert summary == 1

    is_none_node = weave.ops.project(run.entity, run.project).isNone()

    assert weave.use(is_none_node) == False

    is_none_node = weave.ops.project(run.entity, "project_does_not_exist").isNone()

    assert weave.use(is_none_node) == True


# Test each of the auth strategies
def test_basic_publish_user_by_api_key_in_context(user_by_api_key_in_context):
    return _test_basic_publish(user_by_api_key_in_context)


def test_basic_publish_user_by_api_key_in_env(user_by_api_key_in_env):
    return _test_basic_publish(user_by_api_key_in_env)


def test_basic_publish_user_by_api_key_netrc(user_by_api_key_netrc):
    return _test_basic_publish(user_by_api_key_netrc)


# As of this writing, I don't have a good way to bootstrap cookies
# def test_basic_publish_user_by_http_headers_in_context(user_by_http_headers_in_context):
#     return _test_basic_publish(user_by_http_headers_in_context)


# def test_basic_publish_user_by_http_headers_in_env(user_by_http_headers_in_env):
#     return _test_basic_publish(user_by_http_headers_in_env)


def _test_basic_publish(user_fixture):
    a = weave.publish([1, 2, 3], "weave/list")
    # Getting the ref for `a` is not a final API. Expect
    # that changes to the publish flow will bread this test
    # and you might need to update how you get the ref.
    ref = a.val._ref
    uri = ref.uri
    assert (
        uri
        == f"wandb-artifact:///{user_fixture.username}/weave/list:0cdf3358dc939f961ca9/obj"
    )
    assert weave.ref_base.Ref.from_str(uri).get() == [1, 2, 3]


def test_compile_through_execution(user_by_api_key_netrc):
    run = wandb.init(project="project_exists")
    for i in range(10):
        run.log({"val": i, "cat": i % 2})
    run.finish()

    """
    This test demonstrates successful execution when there is an explicit
    const function instead of a direct node (resulting in an intermediate execution op)
    """
    history_node = weave.ops.project(run.entity, run.project).run(run.id).history2()
    pick = weave_internal.const(history_node).pick("val")
    res = weave.use(pick)
    assert res.to_pylist_notags() == list(range(10))

    """
    This test demonstrates successful execution when there is an explicit
    function-__call__ in the graph)
    """
    const_node = weave_internal.const(
        weave_internal.define_fn(
            {"entity_name": types.String()},
            lambda entity_name: (
                weave.ops.project(entity_name, run.project).run(run.id).history2()
            ),
        )
    )(run.entity)
    pick = const_node.pick("val")
    res = weave.use(pick)
    assert res.to_pylist_notags() == list(range(10))


# def test_panel_timeseries(user_by_api_key_in_env):
#     run = wandb.init(project="project_exists")
#     for i in range(10):
#         time.sleep(0.2)
#         run.log({"val": i, "cat": str(i % 2)})
#     run.finish()

#     history_node = weave.ops.project(run.entity, run.project).run(run.id).history2()
#     panel = TimeSeries(history_node)
#     init_config_node = panel.initialize()
#     init_config = weave.use(init_config_node)
#     panel.config = init_config
#     render_node = panel.render()
#     res = weave.use(render_node)
#     # What to assert here? Should we be getting .contents?
#     assert res != None
