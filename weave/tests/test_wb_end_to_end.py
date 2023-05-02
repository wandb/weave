import weave
import wandb

# Example of end to end integration test
def test_run_logging(user_by_api_key_in_env):
    run = wandb.init()
    run.log({"a": 1})
    run.finish()

    summary_node = weave.ops.project(run.entity, run.project).run(run.id).summary()
    summary = weave.use(summary_node)

    assert summary.get("a") == 1


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
    a = weave.publish([1, 2, 3], "weave_ops/list")
    # Getting the ref for `a` is not a final API. Expect
    # that changes to the publish flow will bread this test
    # and you might need to update how you get the ref.
    ref = a.val._ref
    uri = ref.uri
    assert (
        uri
        == f"wandb-artifact:///{user_fixture.username}/weave_ops/list:0cdf3358dc939f961ca9/obj"
    )
    assert weave.ref_base.Ref.from_str(uri).get() == [1, 2, 3]
