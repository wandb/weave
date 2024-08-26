import weave
import weave.trace.weave_init


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
    assert len(list(weave_client.calls())) == 1

    weave.finish()

    foo()
    assert len(list(weave_client.calls())) == 1
    assert weave.trace.weave_init._current_inited_client is None
