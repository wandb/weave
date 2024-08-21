import pytest

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import InvalidRequest
from weave.trace_server.interface.query import Query


def test_feedback_apis(client):
    project_id = client._project_id()

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
    with pytest.raises(InvalidRequest):
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
        client.server.feedback_purge(req)


def test_feedback_payload(client):
    project_id = client._project_id()

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


def test_feedback_create_too_large(client):
    project_id = client._project_id()

    value = "a" * 10000
    req = tsi.FeedbackCreateReq(
        project_id=project_id,
        wb_user_id="VXNlcjo0NTI1NDQ=",
        weave_ref="weave:///entity/project/object/name:digest",
        feedback_type="custom",
        payload={"value": value},
    )
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(req)
