# Feedback Data Model

This document outlines an investigation designed to inform the datamodel changes / usage Feedback in Weave.

## Current Data Model

Today, Feedback has a very simple data model (see weave/trace_server/migrations/003_feedback.up.sql):

```sql
CREATE TABLE feedback (
    /*
    `id`: The unique identifier for the feedback. This is a UUID.
    */
    id String,

    /*
    `project_id`: The project identifier for the ref. This is an internal
    identifier that matches the project identifier in the W&B API.
    It is stored for feedback to allow efficient permissions filtering.
    */
    project_id String,

    /*
    `weave_ref`: The ref the feedback is associated with.
    Note: the weave prefix is to avoid conflict with React's notion of ref.
    */
    weave_ref String,

    /*
    `wb_user_id`: The ID of the user account used to authenticate the feedback creation.
    This is the ID of the user in the W&B API.
    */
    wb_user_id String,

    /*
    `creator`: The name to display for who the feedback came from. Can default to the name of
    the user account used to authenticate the feedback creation, but can be an arbitrary string.
    This is useful for feedback that originated with end users who may not have a W&B account.
    */
    creator String NULL,

    /*
    `created_at`: The time that the row was inserted into the database.
    */
    created_at DateTime64(3) DEFAULT now64(3),

    /*
    `feedback_type`: The type of feedback that was given. The prefix "wandb." is reserved for our use.
    */
    feedback_type String,

    /*
    `payload_dump`: A dictionary of values that represent the feedback.
    The schema of this dictionary is determined by the feedback_type.
    */
    payload_dump String,

) ENGINE = ReplacingMergeTree()
ORDER BY (project_id, weave_ref, wb_user_id, id);
```

And there are 4 types of structured feedback (patten is split, but should be unified):

```python
# weave/trace_server/feedback.py
FEEDBACK_PAYLOAD_SCHEMAS: dict[str, type[BaseModel]] = {
    "wandb.reaction.1": tsi.FeedbackPayloadReactionReq,
    "wandb.note.1": tsi.FeedbackPayloadNoteReq,
}
```

```python
# weave/trace_server/interface/base_models/feedback_base_model_registry.py

# Implied type name: `ActionScore`

class ActionScore(BaseModel):
    configured_action_ref: str
    output: Any
```

```python
# weave/trace/feedback_types/score.py
SCORE_TYPE_NAME = "wandb.score.beta.1"

class ScoreTypePayload(TypedDict):
    name: str
    op_ref: str
    call_ref: str
    results: dict
```

The incoming `payload` is expected (and enforced) to conform to the schema for the given `feedback_type`. However, in the emoji case, some post procesing is applied:

```python
def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
    assert_non_null_wb_user_id(req)
    validate_feedback_create_req(req)

    feedback_type = req.feedback_type
    res_payload = req.payload

    for feedback_base_model in feedback_base_models:
        if base_model_name(feedback_base_model) == feedback_type:
            res_payload = base_model_dump(
                feedback_base_model.model_validate(res_payload)
            )
            break

    # Augment emoji with alias.
    if req.feedback_type == "wandb.reaction.1":
        em = req.payload["emoji"]
        if emoji.emoji_count(em) != 1:
            raise InvalidRequest(
                "Value of emoji key in payload must be exactly one emoji"
            )
        req.payload["alias"] = emoji.demojize(em)
        detoned = detone_emojis(em)
        req.payload["detoned"] = detoned
        req.payload["detoned_alias"] = emoji.demojize(detoned)
        res_payload = req.payload
```

Therefore, the on-disk shape is not technically typed or enforced at least for the emoji case

Finally, we should note that it is technically possible for the user to create their own feedback type name and payload that is completely arbitrary.


## Limitations / Complications

Until now, everything has been relatively adhoc in terms of consuming feedback in the UI and only support querying feedback itself. This presents a few complications:

1. We don't have a way to filter / sort calls based on feedback.
2. Dynamic Feedback types don't have a constent output shape, making their "type" mean something different than it does for emoji and note. (see section below)
3. Emoji's have a different shape on disk than their incoming shape constraints.

### Dynamic Feedback Types 

Let's consider the following new types of feedback:
1. (Emojis) `wandb.reaction.1`
    * Static Schema
    * Used in production & UI
    * Write-time enforced schema
2. (Notes) `wandb.note.1`
    * Static Schema
    * Used in production & UI
    * Write-time enforced schema
3. (Offline User-executed Scores) `wandb.score.beta.1`
    * Dynamic Schema
    * Not currently consumed - can be changed
    * Not enforced at write-time
4. (Online Weave-executed Scores) `ActionScore`
    * Dynamic Schema
    * No writers or consumers - can be changed
    * Write-time enforced schema
5. (Human-in-the-loop / Human Annotation Scores) `ConfiguredColumn`
    * Dynamic Schema
    * Not implemented in this branch (coming soon with Griffin's work)

Let's put to the side the naming format inconsistency for now and focus on what we mean by a "dynamic schema". Feeback types with a dynamic schema have some (or all) of their schema defined by user-specified configuration. For example:

* `wandb.score.beta.1` -> this is the result of running arbitrary user code, so the output schema is completely dynamic - from primitives to nested objects.
* `ActionScore` -> this is the result of running configured actions (which can be json-schema validated llm judgements).
* `ConfiguredColumn` -> this is the result of running a user-specified column (such as a rank, boolean, classification, etc).

In these cases, the user-specified configuration is identieed (NOT DEFINED ALWAYS) by a Weave object in the user's project. For example:

* All scorers generated by an Op with id `my_op:digest_1` would be expected to produce a consistent schema, but the schema itself is not stored
* All action scorers with the same action id `my_action:digest_1` are expected to produce the same schema (and in many cases is stored as json schema - nice!)
* All configured columns with the same column id `my_column:digest_1` are expected to produce the same schema, which is stored as more of a configuration object.

So now we have a logical mismatch between the "dynamic schema" and the "static schema" feedback types. While this all might seem pedantic, it's actually quite important for considering efficient and correct queries. This brings us to the next section.

### Additional Considerations

* Some scorers will need to have additionl context (for example ground truth labels) that need to be associated with the feedback.

## Querying Feedback

### Example Data
Let's consider that a call might have a number of feedbacks associated with it. For example (note, project-id, creator, and created_at are excluded for brevity):
<table>
  <tr>
    <th>id</th>
    <th>weave_ref</th>
    <th>wb_user_id</th>
    <th>feedback_type</th>
    <th>payload_dump</th>
  </tr>
  <tr>
    <td>fb_001</td>
    <td>call:abc</td>
    <td>wb_001</td>
    <td>wandb.reaction.1</td>
    <td><pre>
{"emoji": "👍"}</pre></td>
  </tr>
  <tr>
    <td>fb_002</td>
    <td>call:abc</td>
    <td>wb_001</td>
    <td>wandb.note.1</td>
    <td><pre>
{"note": "Great result!"}</pre></td>
  </tr>
  <tr>
    <td>fb_003</td>
    <td>call:abc</td>
    <td>wb_001</td>
    <td>wandb.score.beta.1</td>
    <td><pre>
{
    "name": "my_score",
    "op_ref": "my_op:digest_1", 
    "call_ref": "score_call:def",
    "results": {
        "is_correct": true
    }
}</pre></td>
  </tr>
  <tr>
    <td>fb_004</td>
    <td>call:abc</td>
    <td>wb_001</td>
    <td>ActionScore</td>
    <td><pre>
{
    "configured_action_ref": "my_action:digest_1",
    "value": PRIMTIVE OR DICT PAYLOAD
}</pre></td>
  </tr>
    <tr>
    <td>fb_002</td>
    <td>call:abc</td>
    <td>wb_001</td>
    <td>ConfiguredColumn</td>
    <td><pre>
{
    "configured_column_ref": "my_column:digest_1",
    "output": {
        "score": 0.98
    }
}</pre></td>
  </tr>
</table>

### Query considerations:
* Different queries have different requirements in terms of grouping and aggregating. For example:
   * Emojis: you want to group by emoji value, then count the unique user ids.
   * Notes: no grouping, just list all.
   * Scores/Actions: group by scorer name (optionally version), then apply a function (last, avg, etc).
   * ConfiguredColumns: group by column name, then apply a function (last, avg, etc). Optionally group by users.

### Example Queries

* "Given a Call, return all feedback"
* "Given a Call, return feedback columns"
* "Given a Call, return feedback for specific (type/version & group)(s)"
* "Given a Call query, include feedback for specific (type/version & group fn)(s)"
* "Given a Call query, sort feedback for specific (type/version & group fn)(s)"
* "Given a Call query, filter feedback for specific (type/version & group fn)(s)"

### Anticipated problems:
* The `type` column (as is) is insufficient for uniquely defining the column. (eg. not all `ConfiguredColumns should be grouped together.)
* The free-form schema of dynamic columns means that we will likely encounter key-space collisions in the nested objects - impliing that we need a mechanism to further narrow the space when querying.
* Since the feedback column is just a string dump of json, anytime we want to fetch feedback we need to parse the json. If critical keys lie in this json, then we will need to load the entire column into memory to perform operations, which will be too slow.

### Proposed Solutions

1. ("RefAsFields"): For dynamic columns, we store the additional grouping/metatadata as fields in the the payload. (This is the current design).
   * The main problem here is that getting the value of any speicfic feedback column requires loading the entire column into memory.
2. ("RefAsType"): For dynamic columns, use the specific object ref as the type name.
   * This will allow for indexed lookups for specific columns.
   * Question: can we effieciently prefix-match to group all versions?
   * Problem: assuming the query looks like `feedback.name:[version|*].path.to.key`, then our existing type names will be a problem.
   * Possible problem: it is not possible to distinguish between Actions, Scorers, and ConfiguredColumns.
   * Possible problem: if we want to put more metadata about the specific feedback, it nees to be placed as siblings in the payload, which excludes primitives from ever being used/stored. Also, effectively untyped and could cause key collisions. For example:
   ```json
   {
    "_scorer_context": {"label": "ground truth"},
    "is_correct": true
   }
   ```
3. ("RefAsKey"): For dynamic columns, we could store the "object/version" as the first two keys of the payload. For example:
   ```json
   {
    "my_action": {
        "digest_1": {
            "_scorer_context": {"label": "ground truth"},
            "value": {
                "grade": "A"
            }
        }
    }
   }
   ```
   * For this to be more efficient than #1, we would need to migrate to clickhouse's native json format (need to validate hypothesis here). This would allow the query syntax to be more natural (but does require an extra "value" key for these cases.): `feedback.my_action.digest_1.value.grade`. or `feedback.my_action.*.value.grade` to get the first value.
   * Also, getting all the feedback columns would then require a querying the json key space (need to investigate performance here).
   * One very nice property of this model is that you can group by call_ref, and do a dictionary merge on the results to get a compbined feedback object for each call.
4. ("RefAsColumns"): For dynamic columns, we could store the "object/version" as new columns in the table. This is very similar to #3, but directly encodes the object/version as columns - taking advantage of the direct indexing capabilities of clickhouse.

Consider the following table,
<table>
<tr>
    <th>Solution</th>
    <th>Dynamic?</th>
    <th>Type</th>
    <th>Name</th>
    <th>Version</th>
    <th>Context</th>
    <th>Payload</th>
</tr>
<tr>
    <td rowspan=3>RefAsFields</td>
    <td>Static</td>
    <td>`wandb.score.beta.1`</td>
    <td>N/A</td>
    <td>N/A</td>
    <td>N/A</td>
    <td><pre>
{
    "emoji": "👍",
}</pre></td>
</tr>
<tr>
    <td rowspan=2>Dynamic</td>
    <td rowspan=2>`ActionScore`</td>
    <td rowspan=2>N/A</td>
    <td rowspan=2>N/A</td>
    <td>N/A</td>
    <td><pre>
{
    "configured_action_ref": "my_action:digest_1",
    "_additional_context_fields: "",
    "value": PRIMTIVE OR DICT PAYLOAD
}</pre></td>
</tr>
<tr>
    <td><pre>{
    "configured_action_ref": "my_action:digest_1",
    "_additional_context_fields: ""
}</pre></td>
    <td><pre>
{"value": PRIMTIVE OR DICT PAYLOAD}
</pre></td>
</tr>
<tr>
    <td rowspan=3>RefAsType</td>
    <td>Static</td>
    <td>`wandb.score.beta.1`</td>
    <td>N/A</td>
    <td>N/A</td>
    <td>N/A</td>
    <td><pre>
{
    "emoji": "👍",
}</pre></td>
</tr>
<tr>
    <td rowspan=2>Dynamic</td>
    <td rowspan=2>`my_action:digest_1`</td>
    <td rowspan=2>N/A</td>
    <td rowspan=2>N/A</td>
    <td>N/A</td>
    <td><pre>
{
    "_additional_context_fields: "",
    "value": PRIMTIVE OR DICT PAYLOAD
}</pre></td>
</tr>
<tr>
    <td><pre>
{
    "_additional_context_fields: ""
}</pre></td>
    <td><pre>
{"value": PRIMTIVE OR DICT PAYLOAD}</pre></td>
</tr>
<tr>
    <td rowspan=3>RefAsKey</td>
    <td>Static</td>
    <td>`wandb.score.beta.1`</td>
    <td>N/A</td>
    <td>N/A</td>
    <td>N/A</td>
    <td><pre>
{
    "emoji": "👍",
}</pre></td>
</tr>
<tr>
    <td rowspan=2>Dynamic</td>
    <td rowspan=2>`ActionScore`</td>
    <td rowspan=2>N/A</td>
    <td rowspan=2>N/A</td>
    <td>N/A</td>
    <td><pre>
{
    "my_action": {
        "digest_1": {
            "configured_action_ref": "my_action:digest_1",
            "_additional_context_fields: "",
            "value": PRIMTIVE OR DICT PAYLOAD
        }
    }
}</pre></td>
</tr>
<tr>
    <td><pre>{
    "configured_action_ref": "my_action:digest_1",
    "_additional_context_fields": ""
}</pre></td>
    <td><pre>
{
    "my_action": {
        "digest_1": {
             "value": PRIMTIVE OR DICT PAYLOAD
        }
    }
}</pre></td>
</tr>
<tr>
    <td rowspan=3>RefAsColumns</td>
    <td>Static</td>
    <td>`wandb.score.beta.1`</td>
    <td>N/A</td>
    <td>N/A</td>
    <td>N/A</td>
    <td><pre>
{
    "emoji": "👍",
}</pre></td>
</tr>
<tr>
    <td rowspan=2>Dynamic</td>
    <td rowspan=2>`ActionScore`</td>
    <td rowspan=2>my_action</td>
    <td rowspan=2>digest_1</td>
    <td>N/A</td>
    <td><pre>
{
    "_additional_context_fields: "",
    "value": PRIMTIVE OR DICT PAYLOAD
}</pre></td>
</tr>
<tr>
    <td><pre>{
    "_additional_context_fields": ""
}</pre></td>
    <td><pre>
{"value": PRIMTIVE OR DICT PAYLOAD}</pre></td>
</tr>
</table>

## Initial Observations:
1. All feedback seems to have:
    * Type (defines the "Extra" schema and "Value" schema)
        * We can think of some `types` as having a generic type, and the `name + version` further narrows the value schema.
    * Name (object id)
    * Version (object digest) - implicitly augments the value schema
    * "Extra" Context (additional context)
    * Value (the output of the feedback scorer)
2. It is probably safe to assert that all payloads are dictionaries.
    * DynamicColumns that might produce primitives need to be stored in the value field.


```python
T = TypeVar("T", bound=Union[dict])
class ScorerFeedback(Generic[T]):
    type: str = "ScorerFeedback"
    name: str
    version: str
    extra: dict
    value: T
```

The main question is which of these fields need to be their own columns, and which go in the value field. If all non-value fields are columns, then the further question becomes do we put {"value": ...} in the value field, or just the raw value?

^^ This is the big question.

## Possible Lower cost solution:

1. Go with `RefAsFields`
2. Store the Pydantic mapping in `type`
3. Store additional fields as siblings to the value field.
4. Create a materialized view that feels like ``RefsAsColumns`.

This would:
1. Allow us to keep the current contract that: typename -> pydantic mapping defines the value schema.
2. We don't need to migrate / change the existing feedback ground truth table
3. We can query from a materialized view that is more optimized for querying.

Why not just go straight to `RefAsColumns`?
1. Requires a migration.
2. Does not depend on clickhouse's experimental JSON format to work.

## Alternative Option

1. Start with something more like `RefAsKeys`
2. This gets all the benefits of the above solution, with the added benefit that existing queries of `[name].version.key` will work.
   * would probably want to use underscores for metadata keys
3. Possible issues with name collissions.
- Feels more complex than the above solution, still requires a materialized view for performant lookup (or JSON column)

However, if we don't do this, we lose the contract that `feedback.X.Y.Z` matches the payload schema.


---
```python
# This would be the feedback table schema
class Feedback():
    type: str = "ScorerFeedback"
    payload_value: TypedDict({
        "_type_spec_name": str,     # _type_spec_name: my_scorer
        "_type_spec_version": str,  # _type_spec_version: digest_1
        "_context": dict,           # _context: {"label": "ground truth"}
        name: TypedDict({           # my_scorer: {"digest_1": {"grade": "A"}}
            version: VALUE_DICT,        
        }),
    })

# This would be the materialized view schema
class FeedbackView():
    type: str = "ScorerFeedback" # indexed
    spec_name: str # indexed
    spec_version: str # indexed
    context: dict
    payload_value: VALUE_DICT

# How about buildins?
class FeedbackView():
    type: str = "Builtin" # indexed
    spec_name: str # indexed # "note"
    spec_version: str # indexed # "1"
    context: dict
    payload_value: VALUE_DICT

class FeedbackView():
    type: str = "Custom" # indexed
    spec_name: str # indexed # ""
    spec_version: str # indexed # ""
    context: dict
    payload_value: VALUE_DICT
```

Query Time
 
unfortunately, somehow we have to make the distiion between specifying the feeback spec and the value. for example, do we do:

* `payload.name.version.key`?

Sigh, there are so many competing concerns here.

1. User-space, would be nice to have a "mongo-like" field selection for feedback:
   * `feedback.spec_name.spec_version.value.key`
   * or maybe:
   ```
   {
        $getFeedbackField: {
            $query: {
                $expr: {
                    $and: [
                        {$eq: ["$feedback_type", "ScorerFeedback"]},
                        {$eq: ["$spec_name", "my_scorer"]},
                        {$eq: ["$spec_version", "digest_1"]},
                    ]
                }
            },
            <!-- $userGroup: "take_last", -->
            $field: {
                $avg: {$getField: "$.payload_value.grade"}
            }
        }
   }
   ```


Ok, what if we merged things and just stored more info?

```python
# Here, we would store the value 3 times. However, this would allow for:
1. Querying using existing dot notation (feedback.payload.name.key), (feedback.payload.name:version.key)
2. We could easily
class Feedback():
    type: str = "ScorerFeedback"
    payload_value: TypedDict({
        "_type_spec_name": str,     # _type_spec_name: my_scorer
        "_type_spec_version": str,  # _type_spec_version: digest_1
        "_context": dict,           # _context: {"label": "ground truth"}
        "_value": VALUE_DICT,      # _value: {"grade": "A"}
        name: VALUE_DICT,          # my_scorer: {"grade": "A"}
        name: TypedDict({           # my_scorer: {"digest_1": {"grade": "A"}}
            version: VALUE_DICT,        
        }),
    })
```


OK, i am just flip flopping now. I think ultimately, a feedback "column" is keyed by the type, name, and version. I think the existing format is wrong. it should be

* HumanFeedback.ColumnName.ColumnVersion.value.key
* ScorerScore.ScorerName.ScorerVersion.value.key
* ActionResult.ActionName.ActionVersion.value.key
* Builtin.BuiltinName("Reaction" | "Note").BuiltinVersion("1").value.key
* Custom.CustomName.CustomVersion("").value.key

ok, now drop the category.

* ColumnName.ColumnVersion.value.key
* ScorerName.ScorerVersion.value.key
* ActionName.ActionVersion.value.key
* BuiltinName("Reaction" | "Note").BuiltinVersion("1").value.key # name collission possibility
* CustomTypeName.CustomVersion("").value.key # name collission possibility


----

Circular thinking:

1. We want feedback_type to map to a pydantic structure.
    * this implies that we likely need a materizlied view for peformance else we have to read big columns. JSON column are not available in clickhouse yet.
2. If that is the case, then feedback_type is a small list of valid types.
3. We also MUST store data in addition to the value field, meaning the payload has a few extra fields.
4. If we want to maintain the existing dot notation (meaning the payload values themselves correspond to the value structure), then we want the value to be nested at the top level. However, if we want to be able to group by name and version differently, then we might need to store multiple copies, which feels wrong.
5. Maybe we should extract name and version into their own fields. If we do this, then how do we handle theexisting types of note/emoji/custom? Custom types don't hae versions. Any dot-sperated notion is going to be flawed and have name collisions.
6. At query time, sometimes you are going to want to get all the individual feedback rows. Would we want to return that special materialized view, or the raw view?
    * what about the cases where you are aggregating?
7. Call query time is a bit different
8. Which if any of these options is easiest to migrate or change?

This makes me land back on:

```python
class ScorerFeedback():
    type: str = "ScorerFeedback"
    value: TypedDict({
        "_scorer_object_id": str,
        "_scorer_digest": str,
        # ... other metadata fields
        "result": dict
    })
```

We then have a materialized view that extracts the metadata fields into their own columns.

* If you are listing feedback for a ref, you get the raw data back, and you see some of the underlying metadata fields.
* We preserve the ability to migrate reliably
* Custom feedback types can have some sentinal ersion in the materizalsed view: "_".
* Notes and Emojies are hard... we might want to have their names be something more complicated like `weave_note` and `weave_reaction`. 
* We shsould use the `~0` and `~1` encoding for dots and tildes.

... Ok, now why not just directly store `{[name]: [version]: value}` in the value field?)
1. Inconsistent pydantic mapping.
    * could reduce forward risk by by data duplication using `_result` field.
2. would save us from the immediate need of a materialized view.
benefit: saves the nested selection. drawback: feels more complex.

This would be:
```python
class ScorerFeedback():
    type: str = "ScorerFeedback"
    value: TypedDict({
        "_metadata": TypedDict({
            "scorer_object_id": str,
            "scorer_digest": str,
            # ... other metadata fields
        }),
        scorer_object_id: TypedDict({
            scorer_digest: dict
        })
    })


```

----

# TODOs

Cleanups:

* [ ] Unify the naming format for feedback types
* [ ] Unify the feedback validation logic (Tim unintentionally made this less dry)
* [ ] Add scorer feedback type to this formal definition.
* [ ] wb_user_id should be nullable (for actions)
* [ ] Could migrate the types to explude dots(.) - to avoid conflict with json selectors.

--- What about query notions

* Calls Query
    * `feedback[ScorerFeedback].name.version.key`


{
    feedback: {
        "my_scorer": {
            "digest_1": {
                "grade": "A"
            }
        },
        "my_action": {
            "digest_1": {
                "value": "some_value"
            }
        },
        "my_column": {
            "digest_1": {
                "value": "some_value"
            }
        },
        "custom_field": 3,
        "note": "some note",
        "emoji": "👍"
    }
}

{
    feedback: {
        my_scorer.avg: 3.14
        my_action.avg: 3.14
        my_column.avg: 3.14
        custom_field.avg: 3.14
        emoji.value_counts: {
            "👍": 10,
            "👎": 5
        }
    }
}

{
    feedback_query: {
        my_scorer.avg: {"$avg": "$feedback.payload.my_scorer.*.grade", $query: {$eq: ["$feedback_type", "ScorerFeedback"]}},
        emoji.👍: {"$count": "$feedback.payload.emoji.👍"},
    }
}

{
    field_selector: "payload.my_scorer.*.grade",
    query_filter: {
        $eq: ["$feedback_type", "ScorerFeedback"],
        $eq: ["scorer_object_id", "digest_1"],
    },
    user_group: "take_last"
    aggregation: "avg"
}
