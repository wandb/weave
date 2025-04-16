from pydantic import BaseModel

import weave
from weave.trace.objectify import register_object
from weave.trace_server.interface.query import Query
from weave.trace_server.trace_server_interface import RefsReadBatchReq


def test_publish_round_trip_query_object(client) -> None:
    query_raw = {
        "$expr": {
            "$gt": [
                {"$getField": "completion_token_cost"},
                {"$literal": 25},
            ],
        }
    }
    query = Query(**query_raw)
    ref = weave.publish(query)
    res = client.server.refs_read_batch(RefsReadBatchReq(refs=[ref.uri()]))
    query_2 = Query.model_validate(res.vals[0])
    assert query_2 == query


def test_publish_round_trip_register_object_nested(client) -> None:
    class Inner(BaseModel):
        name: str

    @register_object
    class Outer(BaseModel):
        inner: Inner

        @classmethod
        def from_obj(cls, obj):
            return cls.model_validate(obj.unwrap(), from_attributes=True)

    outer = Outer(inner=Inner(name="test"))
    outer_ref = weave.publish(outer)
    outer_gotten = outer_ref.get()
    assert isinstance(outer_gotten, Outer)
    assert isinstance(outer_gotten.inner, Inner)
    assert outer_gotten.inner.name == "test"
    assert outer == outer_gotten
