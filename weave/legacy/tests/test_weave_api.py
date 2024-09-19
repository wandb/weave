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

