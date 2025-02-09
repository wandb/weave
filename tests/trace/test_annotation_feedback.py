import pytest
from pydantic import BaseModel, Field

import weave
from weave import AnnotationSpec
from weave.trace_server.clickhouse_trace_server_batched import InvalidRequest
from weave.tsi.trace_server_interface import FeedbackCreateReq, ObjQueryReq


def test_human_feedback_basic(client):
    # create a human feedback spec

    col1 = AnnotationSpec(
        name="Numerical field #1",
        description="A numerical field with a range of -1 to 1",
        field_schema={
            "type": "number",
            "minimum": -1,
            "maximum": 1,
        },
        unique_among_creators=True,
        op_scope=None,
    )
    ref1 = weave.publish(col1, "my numerical spec")
    assert ref1

    col2 = AnnotationSpec(
        name="Text field #1",
        field_schema={"type": "string", "maxLength": 100},
        op_scope=["weave:///entity/project/op/name:digest"],
    )
    ref2 = weave.publish(col2, "my text spec")
    assert ref2

    # query it by object type
    objects = client.server.objs_query(
        ObjQueryReq.model_validate(
            {
                "project_id": client._project_id(),
                "filter": {"base_object_classes": ["AnnotationSpec"]},
            }
        )
    )

    assert len(objects.objs) == 2
    assert objects.objs[0].val["name"] == "Numerical field #1"
    assert objects.objs[1].val["name"] == "Text field #1"
    assert (
        objects.objs[0].val["description"]
        == "A numerical field with a range of -1 to 1"
    )
    assert not objects.objs[1].val["description"]
    assert not objects.objs[0].val["op_scope"]
    assert objects.objs[1].val["op_scope"] == ["weave:///entity/project/op/name:digest"]
    assert objects.objs[0].val["field_schema"] == {
        "type": "number",
        "minimum": -1,
        "maximum": 1,
    }
    assert objects.objs[1].val["field_schema"] == {
        "type": "string",
        "maxLength": 100,
    }

    # Attempt to add valid and invalid payloads
    client.server.feedback_create(
        FeedbackCreateReq.model_validate(
            {
                "project_id": client._project_id(),
                "weave_ref": "weave:///entity/project/call/name:digest",
                "feedback_type": "wandb.annotation." + ref1.name,
                "annotation_ref": ref1.uri(),
                "payload": {"value": 0},
            }
        )
    )

    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            FeedbackCreateReq.model_validate(
                {
                    "project_id": client._project_id(),
                    "weave_ref": "weave:///entity/project/call/name:digest",
                    "feedback_type": "wandb.annotation." + ref1.name,
                    "annotation_ref": ref1.uri(),
                    "payload": {"value": 42},
                }
            )
        )


def test_field_schema_with_pydantic_model(client):
    # Test using a Pydantic model as field_schema
    class FeedbackModel(BaseModel):
        rating: int = Field(ge=1, le=5, description="Rating from 1 to 5")
        comment: str = Field(max_length=200, description="Optional comment")
        category: str = Field(enum=["good", "bad", "neutral"])

    col = AnnotationSpec(
        name="Pydantic Model Feedback",
        description="A feedback spec using a Pydantic model schema",
        field_schema=FeedbackModel,
    )
    ref = weave.publish(col, "pydantic model spec")
    assert ref

    # Query and verify the converted schema
    objects = client.server.objs_query(
        ObjQueryReq.model_validate(
            {
                "project_id": client._project_id(),
                "filter": {"base_object_classes": ["AnnotationSpec"]},
            }
        )
    )

    # Find our new spec
    pydantic_spec = next(
        obj for obj in objects.objs if obj.val["name"] == "Pydantic Model Feedback"
    )

    # Verify the schema was properly converted
    assert pydantic_spec.val["field_schema"]["type"] == "object"
    assert "properties" in pydantic_spec.val["field_schema"]
    assert set(pydantic_spec.val["field_schema"]["properties"].keys()) == {
        "rating",
        "comment",
        "category",
    }

    # Verify specific field constraints were preserved
    rating_schema = pydantic_spec.val["field_schema"]["properties"]["rating"]
    assert rating_schema["type"] == "integer"
    assert rating_schema["minimum"] == 1
    assert rating_schema["maximum"] == 5

    comment_schema = pydantic_spec.val["field_schema"]["properties"]["comment"]
    assert comment_schema["type"] == "string"
    assert comment_schema["maxLength"] == 200

    category_schema = pydantic_spec.val["field_schema"]["properties"]["category"]
    assert category_schema["type"] == "string"
    assert set(category_schema["enum"]) == {"good", "bad", "neutral"}

    # Attempt to add valid and invalid payloads
    client.server.feedback_create(
        FeedbackCreateReq.model_validate(
            {
                "project_id": client._project_id(),
                "weave_ref": "weave:///entity/project/call/name:digest",
                "feedback_type": "wandb.annotation." + ref.name,
                "annotation_ref": ref.uri(),
                "payload": {
                    "value": {
                        "rating": 1,
                        "comment": "Good work!",
                        "category": "good",
                    }
                },
            }
        )
    )

    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            FeedbackCreateReq.model_validate(
                {
                    "project_id": client._project_id(),
                    "weave_ref": "weave:///entity/project/call/name:digest",
                    "feedback_type": "wandb.annotation." + ref.name,
                    "annotation_ref": ref.uri(),
                    "payload": {
                        "value": {
                            "rating": "not a number",
                            "comment": "Good work!",
                            "category": "good",
                        }
                    },
                }
            )
        )


def test_field_schema_with_pydantic_field(client):
    # Test various field types
    rating_field = Field(ge=1, le=5, description="Rating from 1 to 5")
    text_field = Field(
        min_length=10,
        max_length=100,
        pattern="^[A-Za-z ]+$",
        description="Text feedback",
    )
    enum_field = Field(
        enum=["excellent", "good", "fair", "poor"], description="Category selection"
    )

    # Test rating field
    col1 = AnnotationSpec(
        name="Rating Field",
        description="A rating field using Pydantic Field",
        field_schema=(int, rating_field),
    )
    ref1 = weave.publish(col1, "rating field spec")
    assert ref1

    # Test text field
    col2 = AnnotationSpec(
        name="Text Field",
        description="A text field using Pydantic Field",
        field_schema=(str, text_field),
    )
    ref2 = weave.publish(col2, "text field spec")
    assert ref2

    # Test enum field
    col3 = AnnotationSpec(
        name="Enum Field",
        description="An enum field using Pydantic Field",
        field_schema=(str, enum_field),
    )
    ref3 = weave.publish(col3, "enum field spec")
    assert ref3

    # Query and verify all specs
    objects = client.server.objs_query(
        ObjQueryReq.model_validate(
            {
                "project_id": client._project_id(),
                "filter": {"base_object_classes": ["AnnotationSpec"]},
            }
        )
    )

    # Find our specs
    rating_spec = next(obj for obj in objects.objs if obj.val["name"] == "Rating Field")
    text_spec = next(obj for obj in objects.objs if obj.val["name"] == "Text Field")
    enum_spec = next(obj for obj in objects.objs if obj.val["name"] == "Enum Field")

    # Verify rating field schema
    assert rating_spec.val["field_schema"]["minimum"] == 1
    assert rating_spec.val["field_schema"]["maximum"] == 5
    assert rating_spec.val["field_schema"]["description"] == "Rating from 1 to 5"

    # Verify text field schema
    assert text_spec.val["field_schema"]["minLength"] == 10
    assert text_spec.val["field_schema"]["maxLength"] == 100
    assert text_spec.val["field_schema"]["pattern"] == "^[A-Za-z ]+$"
    assert text_spec.val["field_schema"]["description"] == "Text feedback"

    # Verify enum field schema
    assert text_spec.val["field_schema"]["type"] == "string"
    assert set(enum_spec.val["field_schema"]["enum"]) == {
        "excellent",
        "good",
        "fair",
        "poor",
    }
    assert enum_spec.val["field_schema"]["description"] == "Category selection"


def test_annotation_spec_validation():
    # Test validation with direct schema
    number_spec = AnnotationSpec(
        name="Number Rating",
        field_schema={
            "type": "number",
            "minimum": 1,
            "maximum": 5,
        },
    )

    # Valid cases
    assert number_spec.value_is_valid(3)
    assert number_spec.value_is_valid(1)
    assert number_spec.value_is_valid(5)

    # Invalid cases
    assert not number_spec.value_is_valid(0)  # too low
    assert not number_spec.value_is_valid(6)  # too high
    assert not number_spec.value_is_valid("3")  # wrong type

    # Test validation with Pydantic model schema
    class FeedbackModel(BaseModel):
        rating: int = Field(ge=1, le=5)
        comment: str = Field(max_length=100)
        tags: list[str] = Field(min_length=1, max_length=3)

    model_spec = AnnotationSpec(name="Complex Feedback", field_schema=FeedbackModel)

    # Valid cases
    assert model_spec.value_is_valid(
        {"rating": 4, "comment": "Good work!", "tags": ["positive", "helpful"]}
    )

    # Invalid cases
    assert not model_spec.value_is_valid(
        {
            "rating": 4,
            "comment": "Good work!",
            # missing tags
        }
    )

    assert not model_spec.value_is_valid(
        {
            "rating": 6,  # invalid rating
            "comment": "Good work!",
            "tags": ["positive"],
        }
    )

    assert not model_spec.value_is_valid(
        {
            "rating": 4,
            "comment": "Good work!",
            "tags": [],  # empty tags list
        }
    )

    # Test validation with Pydantic Field schema
    enum_field = Field(enum=["excellent", "good", "fair", "poor"])
    enum_spec = AnnotationSpec(name="Simple Enum", field_schema=(str, enum_field))

    # Valid cases
    assert enum_spec.value_is_valid("good")
    assert enum_spec.value_is_valid("excellent")

    # Invalid cases
    assert not enum_spec.value_is_valid("invalid_choice")
    assert not enum_spec.value_is_valid(123)


def test_annotation_spec_validation_with_complex_types():
    # Test nested object validation
    class Address(BaseModel):
        street: str
        city: str
        zip_code: str = Field(pattern=r"^\d{5}$")

    class PersonFeedback(BaseModel):
        name: str
        age: int = Field(ge=0, le=120)
        addresses: list[Address] = Field(min_length=1, max_length=3)

    person_spec = AnnotationSpec(name="Person Feedback", field_schema=PersonFeedback)

    # Valid case
    assert person_spec.value_is_valid(
        {
            "name": "John Doe",
            "age": 30,
            "addresses": [
                {"street": "123 Main St", "city": "Springfield", "zip_code": "12345"}
            ],
        }
    )

    # Invalid cases
    assert not person_spec.value_is_valid(
        {
            "name": "John Doe",
            "age": 30,
            "addresses": [
                {
                    "street": "123 Main St",
                    "city": "Springfield",
                    "zip_code": "123",  # invalid zip code
                }
            ],
        }
    )

    assert not person_spec.value_is_valid(
        {
            "name": "John Doe",
            "age": 150,  # invalid age
            "addresses": [
                {
                    "street": "123 Main St",
                    "city": "Springfield",
                    "zip_code": "12345",
                }
            ],
        }
    )


def test_annotation_spec_validate_return_value():
    # Test with a simple numeric schema
    number_spec = AnnotationSpec(
        name="Number Rating",
        field_schema={
            "type": "number",
            "minimum": 1,
            "maximum": 5,
        },
    )

    # Valid cases should return True
    assert number_spec.value_is_valid(3)
    assert number_spec.value_is_valid(1)
    assert number_spec.value_is_valid(5)

    # Invalid cases should return False
    assert not number_spec.value_is_valid(0)  # too low
    assert not number_spec.value_is_valid(6)  # too high
    assert not number_spec.value_is_valid("3")  # wrong type

    # Test with a Pydantic model schema
    class FeedbackModel(BaseModel):
        rating: int = Field(ge=1, le=5)
        comment: str = Field(max_length=100)
        tags: list[str] = Field(min_length=1, max_length=3)

    model_spec = AnnotationSpec(name="Complex Feedback", field_schema=FeedbackModel)

    # Valid case should return True
    assert model_spec.value_is_valid(
        {"rating": 4, "comment": "Good work!", "tags": ["positive", "helpful"]}
    )

    # Invalid cases should return False
    assert not model_spec.value_is_valid(
        {
            "rating": 4,
            "comment": "Good work!",
            # missing tags
        }
    )

    assert not model_spec.value_is_valid(
        {
            "rating": 6,  # invalid rating
            "comment": "Good work!",
            "tags": ["positive"],
        }
    )
    assert not model_spec.value_is_valid(
        {
            "rating": 4,
            "comment": "Good work!",
            "tags": [],  # empty tags list
        }
    )

    # Test with a Pydantic Field schema
    enum_spec = AnnotationSpec(
        name="Simple Enum",
        field_schema=(str, Field(enum=["excellent", "good", "fair", "poor"])),
    )

    # Valid cases should return True
    assert enum_spec.value_is_valid("good")
    assert enum_spec.value_is_valid("excellent")

    # Invalid cases should return False
    assert not enum_spec.value_is_valid("invalid_choice")
    assert not enum_spec.value_is_valid(123)


def test_annotation_feedback_sdk(client):
    number_spec = AnnotationSpec(
        name="Number Rating",
        field_schema={
            "type": "number",
            "minimum": 1,
            "maximum": 5,
        },
    )
    ref = weave.publish(number_spec, "number spec")
    assert ref

    @weave.op()
    def do_call():
        return 3

    do_call()
    do_call()

    calls = do_call.calls()
    assert len(list(calls)) == 2

    # Add annotation feedback
    calls[0].feedback.add(
        "wandb.annotation.number-spec",
        {"value": 3},
        annotation_ref=ref.uri(),
    )

    # Query the feedback
    feedback = calls[0].feedback.refresh()
    assert len(feedback) == 1
    assert feedback[0].payload["value"] == 3
    assert feedback[0].annotation_ref == ref.uri()

    # no annotation_ref
    with pytest.raises(ValueError):
        calls[0].feedback.add("wandb.annotation.number_rating", {"value": 3})

    # empty annotation_ref
    with pytest.raises(ValueError):
        calls[0].feedback.add(
            "wandb.annotation.number_rating", {"value": 3}, annotation_ref=""
        )

    # invalid annotation_ref
    with pytest.raises(ValueError):
        calls[0].feedback.add("number_rating", {"value": 3}, annotation_ref="ssss")

    # no wandb.annotation prefix
    with pytest.raises(
        ValueError,
        match="To add annotation feedback, feedback_type must conform to the format: 'wandb.annotation.<name>'.",
    ):
        calls[0].feedback.add("number_rating", {"value": 3}, annotation_ref=ref.uri())
