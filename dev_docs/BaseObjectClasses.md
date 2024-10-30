# BaseObjectClasses

## Refresher on Objects and object storage

In Weave, we have a general-purpose data storage system for objects.
The payloads themselves are completely free-form - basically anything that can be JSON-serialized.
Users can "publish" runtime objects to weave using `weave.publish`.
For example:

```python
config = {"model_name": "my_model", "model_version": "1.0"}
ref = weave.publish(config, name="my_model_config")
```

This will create a new object "version" in the collection called "my_model_config".
These can then be retrieved using `weave.ref().get()`:

```python
config = weave.ref("my_model_config").get()
```

Sometimes users are working with standard structured classes like `dataclasses` or `pydantic.BaseModel`. 
In such cases, we have special serialization and deserialization logic that allows for cleaner serialization patterns.
For example, let's say the user does:

```python
class ModelConfig(weave.Object):
    model_name: str
    model_version: str
```

Then the user can publish an instance of `ModelConfig` as follows:

```python
config = ModelConfig(model_name="my_model", model_version="1.0")
ref = weave.publish(config)
```

This will result in an on-disk payload that looks like:

```json
{
    "model_name": "my_model",
    "model_version": "1.0",
    "_class_name": "ModelConfig",
    "_bases": ["Object", "BaseModel"]
}
```

And additionally, the user can query for all objects of the `ModelConfig` class using the `base_object_classes` filter in `objs_query` or `POST objs/query`.
Effectively, this is like creating a virtual table for that class.

**Terminology**: We use the term "weave Object" (capital "O") to refer to instances of classes that subclass `weave.Object`.

**Technical note**: the "base_object_class" is the first subtype of "Object", not the _class_name. 
For example, let's say the class heirarchy is:
* `A -> Object -> BaseModel`, then the `base_object_class` filter will be "A".
* `B -> A -> Object -> BaseModel`, then the `base_object_class` filter will still be "A"!

Finally, the Weave library itself utilizes this mechanism for common objects like `Model`, `Dataset`, `Evaluation`, etc...
This allows the user to subclass these objects to add additional metadata or functionality, while categorizing them in the same virtual table.

## The need for validation
Objects, like people, sometimes need validation. Many of our Objects (eg. `Model`) don't really need validation as they are completely free-form and up to the user to definie the properties.
However, there is an increasing need to have a well-defined schema for certain configuration objects - where those objects are tightly defined by Weave, not the user.
In such cases, it is important to have a standard, validated schema that can be shared across the python sdk, the http api, the DB, the frontend UI, and the typescript sdk.

### Motivating example:
Let's consider that we are defining a new concept "Leaderboard". We want to store this as a configuration object in Weave.
Let's say that it's pydantic representation is:

```python
class LeaderboardColumn(BaseModel):
    name: str
    description: str
    evaluation_obj: str # <- reference to an Evaluation object
    metric_name: str
    lower_is_better: bool

class Leaderboard(BaseModel):
    name: str
    description: str
    columns: List[LeaderboardColumn]
```

We want to be able to store & query `Leaderboards` efficiently and ensure they always have a well-defined schema. Therefore we need:
1. An ability to validate the schema at insertion time
2. An ability to create such objects view the REST API
3. An ability to construct, publish, & query these objects:
    * via the HTTP API (future: would be nice to have these types inside the openapi schema)
    * from Python SDK (need a `weave.Object` subclass)
    * from Typescript SDK (TBD - not yet supported, but need the ability to generate the correct utilities)
    * from Frontend UI (need a generated Zod schema & hooks to validate the data)
        * Ideally, with static type-safety.

And all of the above should be generated from a single source of truth: the pydantic schema.

### Solution
1. We define a set of "validated base object classes" in a common location.
2. We use that:
    1. At the DB layer to validate insertion schemas
    2. Can be published from the python sdk
       * Note: figuring out the interplay with `weave.Object` is tricky here. There are a few issues:
            1. We don't want to depend on the weave sdk inside the common interface, meaning the class heirarchy is inherently divergent
            2. Without `weave.Object`:
                * Our python serialization layer's `is_instance` checks will not maintain behavior
                * (Seems fine?) No ref tracing or nested deserialization. Actually, i think we do want to avoid this.
                * (Seems fine?) No "handle_relocatable_object" behavior
            3. We still want to have the same bases array in the final payload
            - I think all of this can be resolved by extended the base_object_class to also look for `BaseObject` (objects that are pure data schema: only fields)
    3. Can be used in the frontend UI layer
        * via generated Zod types & hooks
    4. Future: Exposed in the OpenAPI schema
    5. Future: Generates Typescript SDK types
    
