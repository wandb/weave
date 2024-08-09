

# API Overview

## Modules

- No modules

## Classes

- [`feedback.Feedbacks`](./weave.feedback.md#class-feedbacks): A collection of Feedback objects with utilities.
- [`feedback.FeedbackQuery`](./weave.feedback.md#class-feedbackquery): Lazy-loading object for fetching feedback from the server.
- [`feedback.RefFeedbackQuery`](./weave.feedback.md#class-reffeedbackquery): Object for interacting with feedback associated with a particular ref.

## Functions

- No functions

---
Classes for working with feedback on a project or ref level.
---

## <kbd>class</kbd> `Feedbacks`
A collection of Feedback objects with utilities. 

### <kbd>method</kbd> `Feedbacks.__init__`

```python
__init__(
    show_refs: bool,
    feedbacks: Optional[Iterable[weave.trace_server.trace_server_interface.Feedback]] = None
) → None
```








---

### <kbd>method</kbd> `Feedbacks.refs`

```python
refs() → Refs
```

Return the unique refs associated with these feedbacks. 


---

## <kbd>class</kbd> `FeedbackQuery`
Lazy-loading object for fetching feedback from the server. 

### <kbd>method</kbd> `FeedbackQuery.__init__`

```python
__init__(
    entity: str,
    project: str,
    query: weave.trace_server.interface.query.Query,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
    show_refs: bool = False
)
```








---

### <kbd>method</kbd> `FeedbackQuery.execute`

```python
execute() → Feedbacks
```





---

### <kbd>method</kbd> `FeedbackQuery.refresh`

```python
refresh() → Feedbacks
```





---

### <kbd>method</kbd> `FeedbackQuery.refs`

```python
refs() → Refs
```






---

## <kbd>class</kbd> `RefFeedbackQuery`
Object for interacting with feedback associated with a particular ref. 

### <kbd>method</kbd> `RefFeedbackQuery.__init__`

```python
__init__(ref: str) → None
```








---

### <kbd>method</kbd> `RefFeedbackQuery.add`

```python
add(
    feedback_type: str,
    payload: Optional[dict[str, Any]] = None,
    creator: Optional[str] = None,
    **kwargs: dict[str, typing.Any]
) → str
```

Add feedback to the ref. 

feedback_type: A string identifying the type of feedback. The "wandb." prefix is reserved. creator: The name to display for the originator of the feedback. 

---

### <kbd>method</kbd> `RefFeedbackQuery.add_note`

```python
add_note(note: str, creator: Optional[str] = None) → str
```





---

### <kbd>method</kbd> `RefFeedbackQuery.add_reaction`

```python
add_reaction(emoji: str, creator: Optional[str] = None) → str
```





---

### <kbd>method</kbd> `RefFeedbackQuery.execute`

```python
execute() → Feedbacks
```





---

### <kbd>method</kbd> `RefFeedbackQuery.purge`

```python
purge(feedback_id: str) → None
```





---

### <kbd>method</kbd> `RefFeedbackQuery.refresh`

```python
refresh() → Feedbacks
```





---

### <kbd>method</kbd> `RefFeedbackQuery.refs`

```python
refs() → Refs
```





