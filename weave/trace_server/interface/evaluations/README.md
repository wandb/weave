# Weave Evaluation System

This directory contains the interface definitions for Weave's evaluation system, which provides a structured way to manage machine learning model evaluations, including model classes, instances, inputs, and generation results.

## Overview

The evaluation system is built around a consistent ORM-like pattern with the following core concepts:

- **ModelClass**: Defines a class of models with the same type signature
- **ModelInstance**: A specific instance of a ModelClass with fixed configuration
- **InputPayload**: Input data for model evaluation
- **GenerationResult**: The output from running a ModelInstance on an InputPayload
- **TaskDefinition**: Defines a modeling task with input/output types
- **TaskExample**: Example data for a task (not yet implemented)

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
class EntityName(BaseModel, EntityNameUserDefinedProperties):
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

## Future Extensions

The system is designed to be extensible. Planned additions include:

- **TaskExample**: Provide example inputs/outputs for tasks (interface exists but not yet implemented)
- **EvaluationRun**: Track the execution of evaluations
- **MetricResult**: Store computed metrics from evaluations
- **Dataset**: Collections of input/output pairs for evaluation
- **Benchmark**: Standardized evaluation scenarios

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