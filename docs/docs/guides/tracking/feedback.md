---
sidebar_position: 3
hide_table_of_contents: true
---

# Feedback

Because automatically evaluating LLM applications is difficult, many teams will allow end-users or a pilot group to provide feedback such as a thumbs up or down on generated content. If they have enough domain expertise, the development team may want to flag issues with traces themselves.

Weave's feedback feature allows users to attach feedback to calls in the Weave UI & via the API. Feedback can include emoji reactions, textual notes, and structured data.

## UI

Reactions and notes are displayed in a column in the calls grid. Hovering over these indicators provides more detail. Notes and reactions can be added by clicking the buttons.

(SCREENSHOT HERE)

Feedback can also be viewed and edited in header of the call details page.

(SCREENSHOT HERE)

The feedback on a call can be viewed on the "Feedback" tab of the call details page.

(SCREENSHOT HERE)

The "Use" tab on the call details page provides copy+paste examples of using the SDK to manipulate the feedback for that call.

(SCREENSHOT HERE)

## SDK

The Weave Python SDK allows you to programmatically add, remove, and query feedback on calls.

### Querying a project's feedback

```python
import weave
client = weave.init('intro-example')

# Get all feedback in a project
all_feedback = client.feedback()

# Fetch a specific feedback object by id.
# Note that the API still returns a collection, which is expected
# to contain zero or one item(s).
one_feedback = client.feedback("<feedback_uuid>")[0]

# Find all feedback objects with a specific reaction. You can specify offset and limit.
thumbs_up = client.feedback(reaction="👍", limit=10)

# After retrieval you can view the details of individual feedback objects.
for f in client.feedback():
    print(f.id)
    print(f.created_at)
    print(f.feedback_type)
    print(f.payload)
```

(TODO: Link to more sophisticated workflow examples)

### Adding feedback to a call

```python
import weave
client = weave.init('intro-example')

call = client.call("<call_uuid>")

# Adding an emoji reaction
call.feedback.add_reaction("👍")

# Adding a note
call.feedback.add_note("this is a note")

# Adding custom key/value pairs.
# The first argument is a user-defined "type" string.
# Feedback must be JSON serializable and less than 1kb when serialized.
call.feedback.add("correctness", { "value": 5 })
```

### Querying feedback on a call

```python
for f in call.feedback:
    print(f.id)
    print(f.feedback_type)
    print(f.payload)
```

### Deleting feedback from a call

```python
call.feedback.purge("<feedback_uuid>")
```
