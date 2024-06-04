import pytest

import weave
import os


def test_create_list_rename_delete():
    os.environ["WEAVE_CACHE_MODE"] = "minimal"

    # create
    art_node = weave.ops.get("local-artifact:///my-data:latest/obj")
    art_node.set("foo")
    assert weave.use(art_node) == "foo"

    # list
    arts = weave.use(weave.ops.local_artifacts())
    assert len(arts) == 1
    assert arts[0].name == "my-data"

    # rename
    weave.ops.rename_artifact(art_node, "my-data2")
    arts = weave.use(weave.ops.local_artifacts())
    assert len(arts) == 1
    assert arts[0].name == "my-data2"

    # delete
    art_node = weave.ops.get("local-artifact:///my-data2:latest/obj")
    weave.ops.delete_artifact(art_node)
    arts = weave.use(weave.ops.local_artifacts())
    assert len(arts) == 0


def test_weave_finish_unsets_client(client):
    @weave.op()
    def test_op(message: str) -> str:
        return message

    calls = list(client.calls())
    assert len(calls) == 0

    assert test_op("hello") == "hello"
    calls = list(client.calls())
    assert len(calls) == 1

    weave.finish()
    assert test_op("hello2") == "hello2"
    calls = list(client.calls())
    assert len(calls) == 1
