import os

import pytest

import weave
import weave.legacy.context_state
import weave.legacy.wandb_api
import weave.weave_init


def test_create_list_rename_delete():
    os.environ["WEAVE_CACHE_MODE"] = "minimal"

    # create
    art_node = weave.legacy.ops.get("local-artifact:///my-data:latest/obj")
    art_node.set("foo")
    assert weave.use(art_node) == "foo"

    # list
    arts = weave.use(weave.legacy.ops.local_artifacts())
    assert len(arts) == 1
    assert arts[0].name == "my-data"

    # rename
    weave.legacy.ops.rename_artifact(art_node, "my-data2")
    arts = weave.use(weave.legacy.ops.local_artifacts())
    assert len(arts) == 1
    assert arts[0].name == "my-data2"

    # delete
    art_node = weave.legacy.ops.get("local-artifact:///my-data2:latest/obj")
    weave.legacy.ops.delete_artifact(art_node)
    arts = weave.use(weave.legacy.ops.local_artifacts())
    assert len(arts) == 0


def test_weave_finish_unsets_client(client):
    @weave.op
    def foo():
        return 1

    weave.client_context.weave_client.set_weave_client_global(None)
    weave.weave_init._current_inited_client = weave.weave_init.InitializedClient(client)
    weave_client = weave.weave_init._current_inited_client.client
    assert weave.weave_init._current_inited_client is not None

    foo()
    assert len(list(weave_client.calls())) == 1

    weave.finish()

    foo()
    assert len(list(weave_client.calls())) == 1
    assert weave.weave_init._current_inited_client is None
