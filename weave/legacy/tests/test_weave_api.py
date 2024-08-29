import os

import pytest

import weave
import weave.legacy.weave.context_state
import weave.legacy.weave.wandb_api
import weave.trace.weave_init


def test_create_list_rename_delete():
    os.environ["WEAVE_CACHE_MODE"] = "minimal"

    # create
    art_node = weave.legacy.weave.ops.get("local-artifact:///my-data:latest/obj")
    art_node.set("foo")
    assert weave.use(art_node) == "foo"

    # list
    arts = weave.use(weave.legacy.weave.ops.local_artifacts())
    assert len(arts) == 1
    assert arts[0].name == "my-data"

    # rename
    weave.legacy.weave.ops.rename_artifact(art_node, "my-data2")
    arts = weave.use(weave.legacy.weave.ops.local_artifacts())
    assert len(arts) == 1
    assert arts[0].name == "my-data2"

    # delete
    art_node = weave.legacy.weave.ops.get("local-artifact:///my-data2:latest/obj")
    weave.legacy.weave.ops.delete_artifact(art_node)
    arts = weave.use(weave.legacy.weave.ops.local_artifacts())
    assert len(arts) == 0


def test_weave_finish_unsets_client(client):
    @weave.op
    def foo():
        return 1

    weave.trace.client_context.weave_client.set_weave_client_global(None)
    weave.trace.weave_init._current_inited_client = (
        weave.trace.weave_init.InitializedClient(client)
    )
    weave_client = weave.trace.weave_init._current_inited_client.client
    assert weave.trace.weave_init._current_inited_client is not None

    foo()
    assert len(list(weave_client.get_calls())) == 1

    weave.finish()

    foo()
    assert len(list(weave_client.get_calls())) == 1
    assert weave.trace.weave_init._current_inited_client is None
