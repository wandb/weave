import pytest

from tests.trace.util import FAKE_NOT_IMPLEMENTED
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import InvalidRequest
from weave.trace_server.interface.query import Query


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_feedback_apis(client):
    project_id = client.project_id

    # Emoji from Jamie
    req = tsi.FeedbackCreateReq(
        project_id=project_id,
        wb_user_id="VXNlcjo0NTI1NDQ=",
        weave_ref="weave:///entity/project/object/name:digest",
        feedback_type="wandb.reaction.1",
        payload={"emoji": "🎱"},
    )
    res = client.server.feedback_create(req)
    assert len(res.id) == 36
    assert res.payload["alias"] == ":pool_8_ball:"
    id_emoji_1 = res.id

    # Another emoji from Jamie
    req = tsi.FeedbackCreateReq(
        project_id=project_id,
        wb_user_id="VXNlcjo0NTI1NDQ=",
        weave_ref="weave:///entity/project/object/name:digest",
        feedback_type="wandb.reaction.1",
        payload={"emoji": "👍🏻"},
    )
    res = client.server.feedback_create(req)
    assert len(res.id) == 36
    assert res.payload["detoned_alias"] == ":thumbs_up:"
    id_emoji_2 = res.id

    # Emoji from Shawn
    req = tsi.FeedbackCreateReq(
        project_id=project_id,
        wb_user_id="VXNlcjoxOQ==",
        weave_ref="weave:///entity/project/object/name:digest",
        feedback_type="wandb.reaction.1",
        payload={"emoji": "👍"},
    )
    res = client.server.feedback_create(req)
    assert len(res.id) == 36
    assert res.payload["detoned_alias"] == ":thumbs_up:"
    id_emoji_3 = res.id

    # Note from Jamie
    req = tsi.FeedbackCreateReq(
        project_id=project_id,
        wb_user_id="VXNlcjo0NTI1NDQ=",
        weave_ref="weave:///entity/project/object/name:digest",
        feedback_type="wandb.note.1",
        payload={"note": "this is a note"},
    )
    res = client.server.feedback_create(req)
    assert len(res.id) == 36
    id_note = res.id

    # Custom from Jamie
    req = tsi.FeedbackCreateReq(
        project_id=project_id,
        wb_user_id="VXNlcjo0NTI1NDQ=",
        weave_ref="weave:///entity/project/object/name:digest",
        feedback_type="custom",
        payload={"key": "value"},
    )
    res = client.server.feedback_create(req)
    assert len(res.id) == 36
    id_custom_1 = res.id

    # Custom on another object
    req = tsi.FeedbackCreateReq(
        project_id=project_id,
        wb_user_id="VXNlcjo0NTI1NDQ=",
        weave_ref="weave:///entity/project/object/name2:digest",
        feedback_type="custom",
        payload={"key": "value"},
    )
    res = client.server.feedback_create(req)
    assert len(res.id) == 36
    id_custom_2 = res.id

    # Try querying on the published feedback
    req = tsi.FeedbackQueryReq(
        project_id=project_id,
        fields=["count(*)"],
    )
    res = client.server.feedback_query(req)
    assert res.result[0]["count(*)"] == 6

    req = tsi.FeedbackQueryReq(
        project_id=project_id,
        fields=["count(*)"],
        query=Query(
            **{
                "$expr": {
                    "$eq": [
                        {"$getField": "feedback_type"},
                        {"$literal": "wandb.reaction.1"},
                    ],
                }
            }
        ),
    )
    res = client.server.feedback_query(req)
    assert res.result[0]["count(*)"] == 3

    req = tsi.FeedbackQueryReq(
        project_id=project_id,
        fields=["count(*)"],
        query=Query(
            **{
                "$expr": {
                    "$eq": [
                        {"$getField": "weave_ref"},
                        {"$literal": "weave:///entity/project/object/name:digest"},
                    ],
                }
            }
        ),
    )
    res = client.server.feedback_query(req)
    assert res.result[0]["count(*)"] == 5

    # Purge one feedback
    req = tsi.FeedbackPurgeReq(
        project_id=project_id,
        query=Query(
            **{
                "$expr": {
                    "$eq": [
                        {"$getField": "id"},
                        {"$literal": id_note},
                    ],
                }
            }
        ),
    )
    res = client.server.feedback_purge(req)

    req = tsi.FeedbackQueryReq(
        project_id=project_id,
        fields=["count(*)"],
    )
    res = client.server.feedback_query(req)
    assert res.result[0]["count(*)"] == 5

    # Purge multiple feedbacks
    req = tsi.FeedbackPurgeReq(
        project_id=project_id,
        query=Query(
            **{
                "$expr": {
                    "$or": [
                        {
                            "$eq": [
                                {"$getField": "id"},
                                {"$literal": id_custom_1},
                            ],
                        },
                        {
                            "$eq": [
                                {"$getField": "id"},
                                {"$literal": id_custom_2},
                            ],
                        },
                    ]
                }
            }
        ),
    )
    res = client.server.feedback_purge(req)

    req = tsi.FeedbackQueryReq(
        project_id=project_id,
        fields=["count(*)"],
    )
    res = client.server.feedback_query(req)
    assert res.result[0]["count(*)"] == 3

    # Purging with a different shaped query raises
    req = tsi.FeedbackPurgeReq(
        project_id=project_id,
        query=Query(
            **{
                "$expr": {
                    "$eq": [
                        {"$getField": "feedback_type"},
                        {"$literal": "wandb.reaction.1"},
                    ],
                }
            }
        ),
    )
    with pytest.raises(InvalidRequest):
        client.server.feedback_purge(req)


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_agent_user_feedback_emoji_tag_is_detoned(client):
    def create(scorer_tags):
        return client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=client.project_id,
                wb_user_id="VXNlcjoxOQ==",
                weave_ref="weave:///entity/project/object/name:digest",
                feedback_type="wandb.agent_user_feedback",
                payload={},
                scorer_tags=scorer_tags,
            )
        )

    # The emoji thumb is detoned (skin-tone variants collapse to one alias).
    res = create(["👍🏽"])
    assert res.payload["detoned_alias"] == ":thumbs_up:"

    # A non-emoji tag gets no alias.
    res = create(["looks-good"])
    assert "detoned_alias" not in res.payload


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_feedback_payload(client):
    project_id = client.project_id

    # Emoji from Jamie
    req = tsi.FeedbackCreateReq(
        project_id=project_id,
        wb_user_id="VXNlcjo0NTI1NDQ=",
        weave_ref="weave:///entity/project/object/name:digest",
        feedback_type="wandb.reaction.1",
        payload={"emoji": "🎱"},
    )
    res = client.server.feedback_create(req)
    assert len(res.id) == 36
    assert res.payload["alias"] == ":pool_8_ball:"
    id_emoji_1 = res.id

    # Try querying on the published feedback
    req = tsi.FeedbackQueryReq(
        project_id=project_id,
    )
    res = client.server.feedback_query(req)
    payload = res.result[0]["payload"]
    assert isinstance(payload, dict)
    assert payload["emoji"] == "🎱"


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_feedback_create_too_large(client):
    project_id = client.project_id

    value = "a" * (1 << 21)  # > 1 MiB, past the limit
    req = tsi.FeedbackCreateReq(
        project_id=project_id,
        wb_user_id="VXNlcjo0NTI1NDQ=",
        weave_ref="weave:///entity/project/object/name:digest",
        feedback_type="custom",
        payload={"value": value},
    )
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(req)


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_feedback_query_created_at_filter(client):
    """created_at filters accept ISO-8601 strings (regression for WB-34897).

    ClickHouse rejects ISO `T`/`Z` strings against the `created_at`
    DateTime64 column unless the server normalizes them, so this exercises the
    feedback_query path end-to-end with a `created_at` bound and asserts on the
    returned rows.
    """
    project_id = client.project_id
    created = client.server.feedback_create(
        tsi.FeedbackCreateReq(
            project_id=project_id,
            wb_user_id="VXNlcjoxOQ==",
            weave_ref="weave:///entity/project/object/name:digest",
            feedback_type="custom",
            payload={"key": "value123"},
        )
    )

    def query_since(bound: str) -> list[dict]:
        res = client.server.feedback_query(
            tsi.FeedbackQueryReq(
                project_id=project_id,
                fields=["id", "feedback_type", "payload"],
                query=Query(
                    **{
                        "$expr": {
                            "$gte": [
                                {"$getField": "created_at"},
                                {"$literal": bound},
                            ]
                        }
                    }
                ),
            )
        )
        return res.result

    # A far-past bound returns the row just created; a far-future bound returns
    # nothing. Both bounds carry the ISO `T`/`Z` shape that previously 500'd.
    rows = query_since("2000-01-01T00:00:00.000000Z")
    assert len(rows) == 1
    assert rows[0] == {
        "id": created.id,
        "feedback_type": "custom",
        "payload": {"key": "value123"},
    }
    assert query_since("2999-01-01T00:00:00.000000Z") == []
