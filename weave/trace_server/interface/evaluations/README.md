# Weave Evaluation System

This directory contains the interface definitions for Weave's evaluation system, which provides a structured way to manage machine learning model evaluations, including model classes, instances, inputs, and generation results.

## Overview

The evaluation system is built around a consistent ORM-like pattern with the following core concepts:

- **ModelClass**: Defines a class of models with the same type signature
- **ModelInstance**: A specific instance of a ModelClass with fixed configuration
- **InputPayload**: Input data for model evaluation
- **GenerationResult**: The output from running a ModelInstance on an InputPayload
- **TaskDefinition**: Defines a modeling task with input/output types
- **TaskExample**: Example data for a task
- **ScorerClass**: Defines a class of scorers with the same type signature
- **ScorerInstance**: A specific instance of a ScorerClass with fixed configuration
- **ScoreResult**: The result of running a ScorerInstance on evaluation data
- **ExampleLabel**: Ground truth label for a TaskExample
- **Summary**: Aggregated evaluation results that freeze the example set for reproducibility

## Architecture Pattern

Each entity follows a consistent pattern with these components:

### 1. Property Classes

Each entity has three property classes:

```python
class EntityNameMutableProperties(BaseModel):
    # Properties that can be changed after creation
    ...

class EntityNameImmutableProperties(BaseModel):
    # Properties that cannot be changed after creation
    ...

class EntityNameUserDefinedProperties(
    BaseModel, 
    EntityNameMutableProperties, 
    EntityNameImmutableProperties
):
    # Combines both mutable and immutable properties
    ...
```

### 2. Main Entity Class

```python
class EntityName(EntityNameUserDefinedProperties):
    id: str  # Every entity has a unique ID
```

### 3. CRUD Request/Response Classes

For each entity, there are request and response classes for CRUD operations:

- `CreateEntityNameReq` / `CreateEntityNameRes`
- `GetEntityNameReq` / `GetEntityNameRes`
- `UpdateEntityNameReq` / `UpdateEntityNameRes`
- `DeleteEntityNameReq` / `DeleteEntityNameRes`

### 4. Mixin Interface

Each entity has an abstract mixin that defines the async CRUD operations:

```python
class TSEIMEntityNameMixin(ABC):
    @abstractmethod
    async def async_create_entity_name(...) -> ...: ...
    
    @abstractmethod
    async def async_get_entity_name(...) -> ...: ...
    
    @abstractmethod
    async def async_update_entity_name(...) -> ...: ...
    
    @abstractmethod
    async def async_delete_entity_name(...) -> ...: ...
```

## Entities

### ModelClass

Represents a class of models that conform to the same type signature.

**Mutable Properties:**
- `name`: str - The name of the model class
- `description`: Optional[str] - Description of the model class

**Immutable Properties:**
- `config_type`: JSONSchema - Schema for model configuration
- `input_type`: JSONSchema - Schema for model inputs
- `output_type`: JSONSchema - Schema for model outputs

### ModelInstance

A specific instance of a ModelClass with fixed configuration.

**Mutable Properties:**
- `hyperparameters`: dict[str, Any] - Tunable parameters

**Immutable Properties:**
- `model_class_id`: str - Reference to the ModelClass
- `config`: Any - Fixed configuration for this instance

### InputPayload

Input data for model evaluation.

**Mutable Properties:**
- None

**Immutable Properties:**
- `payload_schema`: JSONSchema - Schema of the payload
- `payload_value`: Any - The actual input data

### GenerationResult

The result of running a ModelInstance on an InputPayload.

**Mutable Properties:**
- None

**Immutable Properties:**
- `model_instance_id`: str - Reference to the ModelInstance
- `input_payload_id`: str - Reference to the InputPayload
- `result`: Any - The generation output

### TaskDefinition

Defines a modeling task by specifying the input and output types.

**Mutable Properties:**
- `name`: str - The name of the task
- `description`: Optional[str] - Description of the task

**Immutable Properties:**
- `signature`: TypedSignature - The input/output type signature for the task

### TaskExample

A specific example for a task that can be used for evaluation.

**Mutable Properties:**
- None

**Immutable Properties:**
- `task_definition_id`: str - Reference to the TaskDefinition
- `input_payload_id`: str - Reference to the InputPayload

### ScorerClass

Represents a class of scorers that conform to the same type signature.

**Mutable Properties:**
- `name`: str - The name of the scorer class
- `description`: Optional[str] - Description of the scorer class

**Immutable Properties:**
- `model_input_schema`: JSONSchema - Schema for model inputs
- `model_output_schema`: JSONSchema - Schema for model outputs
- `example_label_schema`: JSONSchema - Schema for example labels
- `score_output_schema`: JSONSchema - Schema for the score output
- `config_schema`: JSONSchema - Configuration schema for scorer instances

### ScorerInstance

A specific instance of a ScorerClass with fixed configuration.

**Mutable Properties:**
- None

**Immutable Properties:**
- `scorer_class_id`: str - Reference to the ScorerClass
- `config`: Any - Fixed configuration for this instance

### ScoreResult

The result of running a ScorerInstance on evaluation data.

**Mutable Properties:**
- None

**Immutable Properties:**
- `scorer_instance_id`: str - Reference to the ScorerInstance
- `generation_result_id`: str - Reference to the GenerationResult being scored
- `example_label_id`: str - Reference to the ExampleLabel (ground truth)
- `input_payload_id`: str - Reference to the InputPayload
- `comparison_id`: Optional[str] - Reference for comparative scoring
- `score`: Any - The actual score output
- `reason`: Optional[str] - Explanation or reasoning for the score

### ExampleLabel

Ground truth label for a TaskExample.

**Mutable Properties:**
- `description`: Optional[str] - Description of the label

**Immutable Properties:**
- `task_example_id`: str - Reference to the TaskExample
- `label_key`: str - The key/name for this label type
- `label_schema`: JSONSchema - Schema of the label value
- `label_value`: Any - The actual label/ground truth value

### Summary

Aggregated evaluation results that freeze the specific set of examples used, ensuring reproducibility even as tasks evolve.

**Mutable Properties:**
- `name`: Optional[str] - Name of the summary
- `description`: Optional[str] - Description of the summary

**Immutable Properties:**
- `model_instance_id`: str - Reference to the ModelInstance evaluated
- `task_definition_id`: str - Reference to the TaskDefinition
- `scorer_instance_id`: str - Reference to the ScorerInstance used
- `task_example_ids`: List[str] - Frozen list of TaskExample IDs used
- `example_label_ids`: List[str] - Frozen list of ExampleLabel IDs used
- `score_result_ids`: List[str] - The individual ScoreResult IDs
- `aggregate_metrics`: dict[str, Any] - Aggregated metrics (e.g., mean, std, min, max)
- `metadata`: Optional[dict[str, Any]] - Additional context (e.g., evaluation date)

## Usage Example

```python
# 1. Create a model class
model_class_req = CreateModelClassReq(
    properties=ModelClassUserDefinedProperties(
        name="GPT-4 Text Generator",
        description="Text generation using GPT-4",
        config_type={"type": "object", "properties": {"temperature": {"type": "number"}}},
        input_type={"type": "object", "properties": {"prompt": {"type": "string"}}},
        output_type={"type": "object", "properties": {"text": {"type": "string"}}}
    )
)
model_class_res = await evaluator.async_create_model_class(model_class_req)

# 2. Create a model instance
model_instance_req = CreateModelInstanceReq(
    properties=ModelInstanceUserDefinedProperties(
        model_class_id=model_class_res.id,
        config={"temperature": 0.7},
        hyperparameters={"max_tokens": 1000}
    )
)
model_instance_res = await evaluator.async_create_model_instance(model_instance_req)

# 3. Create an input payload
input_payload_req = CreateInputPayloadReq(
    properties=InputPayloadUserDefinedProperties(
        payload_schema={"type": "object", "properties": {"prompt": {"type": "string"}}},
        payload_value={"prompt": "Write a haiku about programming"}
    )
)
input_payload_res = await evaluator.async_create_input_payload(input_payload_req)

# 4. Create a generation result
generation_result_req = CreateGenerationResultReq(
    properties=GenerationResultUserDefinedProperties(
        model_instance_id=model_instance_res.id,
        input_payload_id=input_payload_res.id,
        result={"text": "Code flows like water\nBugs hide in syntax corners\nDebugger finds truth"}
    )
)
generation_result_res = await evaluator.async_create_generation_result(generation_result_req)

# 5. Create a task definition
task_definition_req = CreateTaskDefinitionReq(
    properties=TaskDefinitionUserDefinedProperties(
        name="Text Generation Task",
        description="Generate text from a prompt",
        signature=TypedSignature(
            input_schema={"type": "object", "properties": {"prompt": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"text": {"type": "string"}}}
        )
    )
)
task_definition_res = await evaluator.async_create_task_definition(task_definition_req)

# 6. Create a task example
task_example_req = CreateTaskExampleReq(
    properties=TaskExampleUserDefinedProperties(
        task_definition_id=task_definition_res.id,
        input_payload_id=input_payload_res.id
    )
)
task_example_res = await evaluator.async_create_task_example(task_example_req)

# 7. Create an example label
example_label_req = CreateExampleLabelReq(
    properties=ExampleLabelUserDefinedProperties(
        task_example_id=task_example_res.id,
        label_key="expected_output",
        label_schema={"type": "object", "properties": {"text": {"type": "string"}}},
        label_value={"text": "Code in silicon\nElectrons dance through logic\nPrograms come alive"},
        description="A well-formed haiku about programming"
    )
)
example_label_res = await evaluator.async_create_example_label(example_label_req)

# 8. Create a scorer class
scorer_class_req = CreateScorerClassReq(
    properties=ScorerClassUserDefinedProperties(
        name="BLEU Scorer",
        description="Scores text similarity using BLEU metric",
        model_input_schema={"type": "object", "properties": {"prompt": {"type": "string"}}},
        model_output_schema={"type": "object", "properties": {"text": {"type": "string"}}},
        example_label_schema={"type": "object", "properties": {"text": {"type": "string"}}},
        score_output_schema={
            "type": "object",
            "properties": {
                "score": {"type": "number"},
                "explanation": {"type": "string"}
            }
        },
        config_schema={
            "type": "object",
            "properties": {
                "n_gram": {"type": "integer", "default": 4}
            }
        }
    )
)
scorer_class_res = await evaluator.async_create_scorer_class(scorer_class_req)

# 9. Create a scorer instance
scorer_instance_req = CreateScorerInstanceReq(
    properties=ScorerInstanceUserDefinedProperties(
        scorer_class_id=scorer_class_res.id,
        config={"n_gram": 4}
    )
)
scorer_instance_res = await evaluator.async_create_scorer_instance(scorer_instance_req)

# 10. Create a score result
score_result_req = CreateScoreResultReq(
    properties=ScoreResultUserDefinedProperties(
        scorer_instance_id=scorer_instance_res.id,
        generation_result_id=generation_result_res.id,
        example_label_id=example_label_res.id,
        input_payload_id=input_payload_res.id,
        score={
            "score": 0.65,
            "explanation": "Partial match on structure and keywords"
        },
        reason="BLEU-4 score computed with smoothing"
    )
)
score_result_res = await evaluator.async_create_score_result(score_result_req)

# 11. Create a summary (after running multiple examples)
# Assume we have lists of example_ids, label_ids, and score_result_ids
summary_req = CreateSummaryReq(
    properties=SummaryUserDefinedProperties(
        name="GPT-4 Haiku Generation Evaluation",
        description="Evaluation of GPT-4 on haiku generation task",
        model_instance_id=model_instance_res.id,
        task_definition_id=task_definition_res.id,
        scorer_instance_id=scorer_instance_res.id,
        task_example_ids=[task_example_res.id],  # In practice, this would be many examples
        example_label_ids=[example_label_res.id],
        score_result_ids=[score_result_res.id],
        aggregate_metrics={
            "mean": 0.65,
            "std": 0.12,
            "min": 0.45,
            "max": 0.89,
            "count": 1
        },
        metadata={
            "evaluation_date": "2024-01-15T10:30:00Z",
            "evaluation_config": {"batch_size": 32}
        }
    )
)
summary_res = await evaluator.async_create_summary(summary_req)
```

## Design Decisions

### Why Mutable vs Immutable Properties?

- **Immutable properties** represent the core identity and configuration of an entity that should not change after creation
- **Mutable properties** allow for updates to metadata, parameters, or status without affecting the entity's core identity
- This separation ensures data integrity and makes the system's behavior more predictable

### Why the TSEIM Prefix?

TSEIM stands for "Trace Server Evaluation Interface Mixin" - this prefix helps distinguish these interfaces from other mixins in the codebase.

### Why Abstract Mixins?

The abstract mixin pattern allows:
- Multiple implementations (e.g., database-backed, in-memory, remote API)
- Easy testing with mock implementations
- Clear separation between interface and implementation

### Why Freeze Examples in Summary?

Tasks can evolve over time with new examples being added or removed. By freezing the specific set of examples, labels, and scores used in a Summary, we ensure:
- **Reproducibility**: You can always trace back exactly which data was used
- **Consistency**: Comparisons between summaries are meaningful
- **Auditability**: Historical evaluations remain intact even as tasks change

## Future Extensions

The system is designed to be extensible. Planned additions include:

- **EvaluationRun**: Track the execution of evaluations
- **Dataset**: Collections of input/output pairs for evaluation
- **Benchmark**: Standardized evaluation scenarios
- **Comparison**: Direct comparison between different model instances

## Contributing

When adding new entities, follow the established pattern:

1. Create a new file named `entityName.py` (use camelCase for the filename)
2. Define the four property classes (Mutable, Immutable, UserDefined, and main entity)
3. Create all CRUD request/response classes
4. Define the abstract mixin with properly named async methods
5. Add the mixin to `TraceServerEvaluationInterfaceMixin` in `__init__.py`
6. Update this README with the new entity documentation

## Common Types

### JSONSchema

Used throughout the system to define schemas for inputs, outputs, and configurations. This should be a valid JSON Schema object.

### TypedSignature

Defined in `common.py`, combines input and output schemas:
```python
class TypedSignature(BaseModel):
    input_schema: JSONSchema
    output_schema: JSONSchema
``` 