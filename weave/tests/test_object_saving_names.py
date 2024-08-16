import weave
from weave.trace_server.refs_internal import quote_select


class A(weave.Object):
    x: int


def test_publish_weave_object_instantiated_with_invalid_name(client):
    a = A(x=1, name="must:be/quoted")

    ref = weave.publish(a)
    a2 = ref.get()
    assert a2.name == "must:be/quoted"  # should be unquoted as normal
    assert a2.ref.name == quote_select("must:be/quoted")


def test_publish_weave_object_updated_with_invalid_name(client):
    a = A(x=1)
    a.name = "must:be/quoted"

    ref = weave.publish(a)
    a2 = ref.get()
    assert a2.name == "must:be/quoted"  # should be unquoted as normal
    assert a2.ref.name == quote_select("must:be/quoted")


def test_publish_weave_object_published_with_invalid_name(client):
    a = A(x=1)

    ref = weave.publish(a, "must:be/quoted")
    a2 = ref.get()
    assert a2.ref.name == quote_select("must:be/quoted")  # ref should be quoted
