---
sidebar_label: feedback
---
    

# weave.feedback

Classes for working with feedback on a project or ref level.

---


# API Overview



## Classes

- [`feedback.Feedbacks`](#class-feedbacks): A collection of Feedback objects with utilities.
- [`feedback.FeedbackQuery`](#class-feedbackquery): Lazy-loading object for fetching feedback from the server.
- [`feedback.RefFeedbackQuery`](#class-reffeedbackquery): Object for interacting with feedback associated with a particular ref.




---


## <kbd>class</kbd> `Feedbacks`
A collection of Feedback objects with utilities. 

### <kbd>method</kbd> `__init__`

```python
__init__(show_refs: bool, feedbacks: Optional[Iterable[Feedback]] = None) → None
```








---

### <kbd>method</kbd> `refs`

```python
refs() → Refs
```

Return the unique refs associated with these feedbacks. 


---

## <kbd>class</kbd> `FeedbackQuery`
Lazy-loading object for fetching feedback from the server. 

### <kbd>method</kbd> `__init__`

```python
__init__(
    entity: str,
    project: str,
    query: Query,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
    show_refs: bool = False
)
```








---

### <kbd>method</kbd> `execute`

```python
execute() → Feedbacks
```





---

### <kbd>method</kbd> `refresh`

```python
refresh() → Feedbacks
```





---

### <kbd>method</kbd> `refs`

```python
refs() → Refs
```






---

## <kbd>class</kbd> `RefFeedbackQuery`
Object for interacting with feedback associated with a particular ref. 

### <kbd>method</kbd> `__init__`

```python
__init__(ref: str) → None
```








---

### <kbd>method</kbd> `add`

```python
add(
    feedback_type: str,
    payload: Optional[dict[str, Any]] = None,
    creator: Optional[str] = None,
    **kwargs: dict[str, Any]
) → str
```

Add feedback to the ref. 

feedback_type: A string identifying the type of feedback. The "wandb." prefix is reserved. creator: The name to display for the originator of the feedback. 

---

### <kbd>method</kbd> `add_note`

```python
add_note(note: str, creator: Optional[str] = None) → str
```





---

### <kbd>method</kbd> `add_reaction`

```python
add_reaction(emoji: str, creator: Optional[str] = None) → str
```





---

### <kbd>method</kbd> `execute`

```python
execute() → Feedbacks
```





---

### <kbd>method</kbd> `purge`

```python
purge(feedback_id: str) → None
```





---

### <kbd>method</kbd> `refresh`

```python
refresh() → Feedbacks
```





---

### <kbd>method</kbd> `refs`

```python
refs() → Refs
```





