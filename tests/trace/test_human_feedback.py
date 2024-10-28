from weave.flow.human_feedback import (
    BinaryFeedback,
    CategoricalFeedback,
    HumanFeedback,
    NumericalFeedback,
    TextFeedback,
)
from weave.trace_server.trace_server_interface import ObjQueryReq


def test_human_feedback_basic(client):
    # create a human feedback spec

    binary_feedback = BinaryFeedback(display_name="my binary")
    text_feedback = TextFeedback(display_name="my text", max_length=100)
    categorical_feedback = CategoricalFeedback(
        display_name="my categorical", options=["option1", "option2"]
    )
    numerical_feedback = NumericalFeedback(display_name="my numerical", min=0, max=100)

    human_feedback = HumanFeedback(
        feedback_fields=[
            binary_feedback,
            text_feedback,
            categorical_feedback,
            numerical_feedback,
        ]
    )

    ref = client.save(human_feedback, "my spec")
    assert ref

    # query it by object type
    objects = client.server.objs_query(
        ObjQueryReq.model_validate(
            {
                "project_id": client._project_id(),
                "filter": {"base_object_classes": ["HumanFeedback"]},
            }
        )
    )

    assert len(objects.objs) == 1
    spec = objects.objs[0]
    assert len(spec.val["feedback_fields"]) == 4
