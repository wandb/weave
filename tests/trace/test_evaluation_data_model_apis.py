# def test_evaluation_workflow(trace_server):
#     trace_server.create_model


import asyncio

import pytest

from weave.trace_server.interface.evaluations.common import TypedSignature
from weave.trace_server.interface.evaluations.EvaluationSummary import (
    CreateEvaluationSummaryReq,
    EvaluationSummaryUserDefinedProperties,
    GetEvaluationSummaryReq,
)
from weave.trace_server.interface.evaluations.ExampleLabel import (
    CreateExampleLabelReq,
    ExampleLabelUserDefinedProperties,
)
from weave.trace_server.interface.evaluations.GenerationResult import (
    CreateGenerationResultReq,
    GenerationResultUserDefinedProperties,
)
from weave.trace_server.interface.evaluations.InputPayload import (
    CreateInputPayloadReq,
    GetInputPayloadReq,
    InputPayloadUserDefinedProperties,
)
from weave.trace_server.interface.evaluations.ModelClass import (
    CreateModelClassReq,
    DeleteModelClassReq,
    GetModelClassReq,
    ModelClassMutableProperties,
    ModelClassUserDefinedProperties,
    UpdateModelClassReq,
)
from weave.trace_server.interface.evaluations.ModelInstance import (
    CreateModelInstanceReq,
    GetModelInstanceReq,
    ModelInstanceMutableProperties,
    ModelInstanceUserDefinedProperties,
    UpdateModelInstanceReq,
)
from weave.trace_server.interface.evaluations.sample_implementation import (
    SampleImplementation,
)
from weave.trace_server.interface.evaluations.ScorerClass import (
    CreateScorerClassReq,
    ScorerClassUserDefinedProperties,
)
from weave.trace_server.interface.evaluations.ScoreResult import (
    CreateScoreResultReq,
    GetScoreResultReq,
    ScoreResultUserDefinedProperties,
)
from weave.trace_server.interface.evaluations.ScorerInstance import (
    CreateScorerInstanceReq,
    ScorerInstanceUserDefinedProperties,
)
from weave.trace_server.interface.evaluations.TaskDefinition import (
    CreateTaskDefinitionReq,
    GetTaskDefinitionReq,
    TaskDefinitionMutableProperties,
    TaskDefinitionUserDefinedProperties,
    UpdateTaskDefinitionReq,
)
from weave.trace_server.interface.evaluations.TaskExample import (
    CreateTaskExampleReq,
    TaskExampleUserDefinedProperties,
)


@pytest.fixture
def evaluator():
    """Create a fresh evaluator instance for each test"""
    return SampleImplementation()


@pytest.fixture
def sample_json_schema():
    """Sample JSON schema for testing"""
    return {"type": "object", "properties": {"value": {"type": "string"}}}


# Helper functions to create test data
async def create_model_class(
    evaluator, name="Test Model", description="Test Description"
):
    """Helper to create a model class"""
    req = CreateModelClassReq(
        properties=ModelClassUserDefinedProperties(
            name=name,
            description=description,
            signature=TypedSignature(
                input_schema={
                    "type": "object",
                    "properties": {"prompt": {"type": "string"}},
                },
                output_schema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                },
            ),
            config_schema={
                "type": "object",
                "properties": {"temperature": {"type": "number"}},
            },
        )
    )
    res = await evaluator.async_create_model_class(req)
    return res.id


async def create_model_instance(evaluator, model_class_id):
    """Helper to create a model instance"""
    req = CreateModelInstanceReq(
        properties=ModelInstanceUserDefinedProperties(
            name="Test Model Instance",
            description="Test instance description",
            model_class_id=model_class_id,
            config={"temperature": 0.7, "max_tokens": 100},
        )
    )
    res = await evaluator.async_create_model_instance(req)
    return res.id


async def create_input_payload(evaluator):
    """Helper to create an input payload"""
    req = CreateInputPayloadReq(
        properties=InputPayloadUserDefinedProperties(
            payload_schema={
                "type": "object",
                "properties": {"prompt": {"type": "string"}},
            },
            payload_value={"prompt": "Test prompt"},
        )
    )
    res = await evaluator.async_create_input_payload(req)
    return res.id


async def create_task_definition(evaluator):
    """Helper to create a task definition"""
    req = CreateTaskDefinitionReq(
        properties=TaskDefinitionUserDefinedProperties(
            name="Test Task",
            description="Test task description",
            signature=TypedSignature(
                input_schema={"type": "object"}, output_schema={"type": "object"}
            ),
        )
    )
    res = await evaluator.async_create_task_definition(req)
    return res.id


async def create_scorer_class(evaluator):
    """Helper to create a scorer class"""
    req = CreateScorerClassReq(
        properties=ScorerClassUserDefinedProperties(
            name="Test Scorer",
            description="Test scorer description",
            model_input_schema={"type": "object"},
            model_output_schema={"type": "object"},
            example_label_schema={"type": "object"},
            score_output_schema={
                "type": "object",
                "properties": {"score": {"type": "number"}},
            },
            config_schema={"type": "object"},
        )
    )
    res = await evaluator.async_create_scorer_class(req)
    return res.id


# Test ModelClass CRUD operations
@pytest.mark.asyncio
async def test_model_class_crud(evaluator):
    # Create
    create_req = CreateModelClassReq(
        properties=ModelClassUserDefinedProperties(
            name="GPT-4 Text Generator",
            description="Text generation model",
            signature=TypedSignature(
                input_schema={
                    "type": "object",
                    "properties": {"prompt": {"type": "string"}},
                },
                output_schema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                },
            ),
            config_schema={
                "type": "object",
                "properties": {"temperature": {"type": "number"}},
            },
        )
    )
    create_res = await evaluator.async_create_model_class(create_req)
    assert create_res.id is not None
    model_class_id = create_res.id

    # Read
    get_req = GetModelClassReq(id=model_class_id)
    get_res = await evaluator.async_get_model_class(get_req)
    assert get_res.result is not None
    assert get_res.result.id == model_class_id
    assert get_res.result.name == "GPT-4 Text Generator"
    assert get_res.result.description == "Text generation model"

    # Update
    update_req = UpdateModelClassReq(
        id=model_class_id,
        updates=ModelClassMutableProperties(
            name="Updated GPT-4", description="Updated description"
        ),
    )
    await evaluator.async_update_model_class(update_req)

    # Verify update
    get_res = await evaluator.async_get_model_class(get_req)
    assert get_res.result.name == "Updated GPT-4"
    assert get_res.result.description == "Updated description"

    # Delete
    delete_req = DeleteModelClassReq(id=model_class_id)
    await evaluator.async_delete_model_class(delete_req)

    # Verify deletion
    with pytest.raises(ValueError, match=f"ModelClass {model_class_id} not found"):
        await evaluator.async_get_model_class(get_req)


# Test ModelInstance with relationships
@pytest.mark.asyncio
async def test_model_instance_with_relationships(evaluator):
    # First create a model class
    model_class_id = await create_model_class(evaluator)

    # Create model instance
    create_req = CreateModelInstanceReq(
        properties=ModelInstanceUserDefinedProperties(
            name="GPT-4 Instance",
            description="Test instance",
            model_class_id=model_class_id,
            config={
                "temperature": 0.7,
                "model": "gpt-4",
                "max_tokens": 1000,
                "top_p": 0.9,
            },
        )
    )
    create_res = await evaluator.async_create_model_instance(create_req)
    instance_id = create_res.id

    # Read instance
    get_req = GetModelInstanceReq(id=instance_id)
    get_res = await evaluator.async_get_model_instance(get_req)
    assert get_res.result is not None
    assert get_res.result.model_class_id == model_class_id
    assert get_res.result.config["temperature"] == 0.7

    # Update name and description
    update_req = UpdateModelInstanceReq(
        id=instance_id,
        updates=ModelInstanceMutableProperties(
            name="Updated GPT-4 Instance", description="Updated description"
        ),
    )
    await evaluator.async_update_model_instance(update_req)

    # Verify update
    get_res = await evaluator.async_get_model_instance(get_req)
    assert get_res.result.name == "Updated GPT-4 Instance"
    assert get_res.result.description == "Updated description"


# Test relationship validation
@pytest.mark.asyncio
async def test_model_instance_invalid_reference(evaluator):
    # Try to create instance with non-existent model class
    create_req = CreateModelInstanceReq(
        properties=ModelInstanceUserDefinedProperties(
            name="Invalid Instance", model_class_id="non-existent-id", config={}
        )
    )

    with pytest.raises(ValueError, match="ModelClass non-existent-id not found"):
        await evaluator.async_create_model_instance(create_req)


# Test complete evaluation workflow
@pytest.mark.asyncio
async def test_complete_evaluation_workflow(evaluator):
    # 1. Create model class
    model_class_id = await create_model_class(
        evaluator, "Text Generator", "Generates text from prompts"
    )

    # 2. Create model instance
    model_instance_id = await create_model_instance(evaluator, model_class_id)

    # 3. Create input payload
    input_payload_id = await create_input_payload(evaluator)

    # 4. Create generation result
    gen_result_req = CreateGenerationResultReq(
        properties=GenerationResultUserDefinedProperties(
            model_instance_id=model_instance_id,
            input_payload_id=input_payload_id,
            result={"text": "Generated text output"},
        )
    )
    gen_result_res = await evaluator.async_create_generation_result(gen_result_req)
    generation_result_id = gen_result_res.id

    # 5. Create task definition
    task_def_id = await create_task_definition(evaluator)

    # 6. Create task example
    task_example_req = CreateTaskExampleReq(
        properties=TaskExampleUserDefinedProperties(
            task_definition_id=task_def_id, input_payload_id=input_payload_id
        )
    )
    task_example_res = await evaluator.async_create_task_example(task_example_req)
    task_example_id = task_example_res.id

    # 7. Create example label
    label_req = CreateExampleLabelReq(
        properties=ExampleLabelUserDefinedProperties(
            task_example_id=task_example_id,
            label_key="expected_output",
            label_schema={"type": "object", "properties": {"text": {"type": "string"}}},
            label_value={"text": "Expected text output"},
            description="Ground truth for this example",
        )
    )
    label_res = await evaluator.async_create_example_label(label_req)
    label_id = label_res.id

    # 8. Create scorer class
    scorer_class_id = await create_scorer_class(evaluator)

    # 9. Create scorer instance
    scorer_instance_req = CreateScorerInstanceReq(
        properties=ScorerInstanceUserDefinedProperties(
            scorer_class_id=scorer_class_id, config={"threshold": 0.8}
        )
    )
    scorer_instance_res = await evaluator.async_create_scorer_instance(
        scorer_instance_req
    )
    scorer_instance_id = scorer_instance_res.id

    # 10. Create score result
    score_req = CreateScoreResultReq(
        properties=ScoreResultUserDefinedProperties(
            scorer_instance_id=scorer_instance_id,
            generation_result_id=generation_result_id,
            example_label_id=label_id,
            input_payload_id=input_payload_id,
            score={"score": 0.85, "explanation": "Good match"},
            reason="Semantic similarity score",
        )
    )
    score_res = await evaluator.async_create_score_result(score_req)

    # Verify we can read the score
    get_score_req = GetScoreResultReq(id=score_res.id)
    get_score_res = await evaluator.async_get_score_result(get_score_req)
    assert get_score_res.ScoreResult is not None
    assert get_score_res.ScoreResult.score["score"] == 0.85
    assert get_score_res.ScoreResult.reason == "Semantic similarity score"

    # 11. Create evaluation summary
    summary_req = CreateEvaluationSummaryReq(
        properties=EvaluationSummaryUserDefinedProperties(
            name="Test Evaluation Summary",
            description="Summary of the evaluation run",
            model_instance_id=model_instance_id,
            task_definition_id=task_def_id,
            scorer_instance_id=scorer_instance_id,
            task_example_ids=[task_example_id],
            example_label_ids=[label_id],
            score_result_ids=[score_res.id],
            aggregate_metrics={
                "mean": 0.85,
                "std": 0.0,
                "min": 0.85,
                "max": 0.85,
                "count": 1,
            },
            metadata={
                "evaluation_date": "2024-01-15T10:30:00Z",
                "evaluation_config": {"batch_size": 1},
            },
        )
    )
    summary_res = await evaluator.async_create_evaluation_summary(summary_req)

    # Verify we can read the summary
    get_summary_req = GetEvaluationSummaryReq(id=summary_res.id)
    get_summary_res = await evaluator.async_get_evaluation_summary(get_summary_req)
    assert get_summary_res.EvaluationSummary is not None
    assert get_summary_res.EvaluationSummary.name == "Test Evaluation Summary"
    assert get_summary_res.EvaluationSummary.aggregate_metrics["mean"] == 0.85
    assert len(get_summary_res.EvaluationSummary.task_example_ids) == 1
    assert len(get_summary_res.EvaluationSummary.score_result_ids) == 1


# Test deletion cascading behavior
@pytest.mark.asyncio
async def test_deletion_does_not_cascade(evaluator):
    """Test that deleting parent entities doesn't automatically cascade"""
    # Create model class and instance
    model_class_id = await create_model_class(evaluator)
    model_instance_id = await create_model_instance(evaluator, model_class_id)

    # Delete model class
    delete_req = DeleteModelClassReq(id=model_class_id)
    await evaluator.async_delete_model_class(delete_req)

    # Model instance should still exist (no cascading delete)
    get_req = GetModelInstanceReq(id=model_instance_id)
    get_res = await evaluator.async_get_model_instance(get_req)
    assert get_res.result is not None


# Test all entity types basic CRUD
@pytest.mark.asyncio
async def test_all_entities_basic_crud(evaluator):
    """Test basic CRUD for all entity types"""
    # InputPayload
    input_req = CreateInputPayloadReq(
        properties=InputPayloadUserDefinedProperties(
            payload_schema={"type": "string"}, payload_value="test input"
        )
    )
    input_res = await evaluator.async_create_input_payload(input_req)
    get_input_req = GetInputPayloadReq(id=input_res.id)
    get_input_res = await evaluator.async_get_input_payload(get_input_req)
    assert get_input_res.InputPayload.payload_value == "test input"

    # TaskDefinition
    task_req = CreateTaskDefinitionReq(
        properties=TaskDefinitionUserDefinedProperties(
            name="Classification Task",
            description="Classify text",
            signature=TypedSignature(
                input_schema={"type": "string"},
                output_schema={"type": "string", "enum": ["positive", "negative"]},
            ),
        )
    )
    task_res = await evaluator.async_create_task_definition(task_req)
    get_task_req = GetTaskDefinitionReq(id=task_res.id)
    get_task_res = await evaluator.async_get_task_definition(get_task_req)
    assert get_task_res.TaskDefinition.name == "Classification Task"

    # Update task definition
    update_task_req = UpdateTaskDefinitionReq(
        id=task_res.id,
        updates=TaskDefinitionMutableProperties(name="Updated Classification Task"),
    )
    await evaluator.async_update_task_definition(update_task_req)
    get_task_res = await evaluator.async_get_task_definition(get_task_req)
    assert get_task_res.TaskDefinition.name == "Updated Classification Task"


# Test error handling
@pytest.mark.asyncio
async def test_error_handling(evaluator):
    """Test various error conditions"""
    # Get non-existent entity
    get_req = GetModelClassReq(id="non-existent")
    with pytest.raises(ValueError, match="ModelClass non-existent not found"):
        await evaluator.async_get_model_class(get_req)

    # Update non-existent entity
    update_req = UpdateModelClassReq(
        id="non-existent", updates=ModelClassMutableProperties(name="New name")
    )
    with pytest.raises(ValueError, match="not found"):
        await evaluator.async_update_model_class(update_req)

    # Delete non-existent entity
    delete_req = DeleteModelClassReq(id="non-existent")
    with pytest.raises(ValueError, match="not found"):
        await evaluator.async_delete_model_class(delete_req)

    # Create with duplicate ID (implementation specific)
    model_class_id = await create_model_class(evaluator)
    # Force duplicate by manipulating the store
    evaluator.model_classes.deleted.discard(model_class_id)
    with pytest.raises(ValueError, match="already exists"):
        evaluator.model_classes.create(model_class_id, {"id": model_class_id})


# Test concurrent operations
@pytest.mark.asyncio
async def test_concurrent_operations(evaluator):
    """Test concurrent creation of entities"""
    # Create multiple model classes concurrently
    tasks = []
    for i in range(10):
        req = CreateModelClassReq(
            properties=ModelClassUserDefinedProperties(
                name=f"Model {i}",
                description=f"Description {i}",
                signature=TypedSignature(
                    input_schema={"type": "object"}, output_schema={"type": "object"}
                ),
                config_schema={"type": "object"},
            )
        )
        tasks.append(evaluator.async_create_model_class(req))

    results = await asyncio.gather(*tasks)

    # All should have unique IDs
    ids = [res.id for res in results]
    assert len(ids) == len(set(ids))  # All unique

    # Verify all were created
    for res in results:
        get_req = GetModelClassReq(id=res.id)
        get_res = await evaluator.async_get_model_class(get_req)
        assert get_res.result is not None


# Test complex relationships
@pytest.mark.asyncio
async def test_complex_relationships(evaluator):
    """Test entities with multiple relationships"""
    # Create base entities
    model_class_id = await create_model_class(evaluator)
    model_instance_id = await create_model_instance(evaluator, model_class_id)
    input_payload_id = await create_input_payload(evaluator)

    # Create generation result
    gen_result_req = CreateGenerationResultReq(
        properties=GenerationResultUserDefinedProperties(
            model_instance_id=model_instance_id,
            input_payload_id=input_payload_id,
            result={"output": "test"},
        )
    )
    gen_result_res = await evaluator.async_create_generation_result(gen_result_req)

    # Create task and example
    task_def_id = await create_task_definition(evaluator)
    task_example_req = CreateTaskExampleReq(
        properties=TaskExampleUserDefinedProperties(
            task_definition_id=task_def_id, input_payload_id=input_payload_id
        )
    )
    task_example_res = await evaluator.async_create_task_example(task_example_req)

    # Create label
    label_req = CreateExampleLabelReq(
        properties=ExampleLabelUserDefinedProperties(
            task_example_id=task_example_res.id,
            label_key="output",
            label_schema={"type": "object"},
            label_value={"output": "expected"},
        )
    )
    label_res = await evaluator.async_create_example_label(label_req)

    # Create scorer and score
    scorer_class_id = await create_scorer_class(evaluator)
    scorer_instance_req = CreateScorerInstanceReq(
        properties=ScorerInstanceUserDefinedProperties(
            scorer_class_id=scorer_class_id, config={}
        )
    )
    scorer_instance_res = await evaluator.async_create_scorer_instance(
        scorer_instance_req
    )

    # Create score result with all relationships
    score_req = CreateScoreResultReq(
        properties=ScoreResultUserDefinedProperties(
            scorer_instance_id=scorer_instance_res.id,
            generation_result_id=gen_result_res.id,
            example_label_id=label_res.id,
            input_payload_id=input_payload_id,
            score={"value": 0.9},
        )
    )
    score_res = await evaluator.async_create_score_result(score_req)

    # Verify all relationships are intact
    get_score_req = GetScoreResultReq(id=score_res.id)
    get_score_res = await evaluator.async_get_score_result(get_score_req)
    assert get_score_res.ScoreResult.scorer_instance_id == scorer_instance_res.id
    assert get_score_res.ScoreResult.generation_result_id == gen_result_res.id
    assert get_score_res.ScoreResult.example_label_id == label_res.id
    assert get_score_res.ScoreResult.input_payload_id == input_payload_id


# Test EvaluationSummary validation
@pytest.mark.asyncio
async def test_evaluation_summary_validation(evaluator):
    """Test that EvaluationSummary validates all referenced entities exist"""
    # Create required entities
    model_class_id = await create_model_class(evaluator)
    model_instance_id = await create_model_instance(evaluator, model_class_id)
    task_def_id = await create_task_definition(evaluator)
    scorer_class_id = await create_scorer_class(evaluator)
    scorer_instance_req = CreateScorerInstanceReq(
        properties=ScorerInstanceUserDefinedProperties(
            scorer_class_id=scorer_class_id, config={}
        )
    )
    scorer_instance_res = await evaluator.async_create_scorer_instance(
        scorer_instance_req
    )

    # Try to create summary with non-existent references
    summary_req = CreateEvaluationSummaryReq(
        properties=EvaluationSummaryUserDefinedProperties(
            name="Invalid Summary",
            model_instance_id=model_instance_id,
            task_definition_id=task_def_id,
            scorer_instance_id=scorer_instance_res.id,
            task_example_ids=["non-existent-example"],
            example_label_ids=[],
            score_result_ids=[],
            aggregate_metrics={},
        )
    )

    with pytest.raises(ValueError, match="TaskExample non-existent-example not found"):
        await evaluator.async_create_evaluation_summary(summary_req)


def test_evaluation_interface():
    """Main test that runs all async tests"""
    # This test is called by pytest and runs all the async tests
    pass  # The actual tests are marked with @pytest.mark.asyncio
