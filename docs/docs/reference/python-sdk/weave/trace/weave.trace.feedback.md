---
sidebar_label: feedback
---
    

# weave.trace.feedback

Classes for working with feedback on a project or ref level.

---


# API Overview



## Classes

- [`feedback.Feedbacks`](#class-feedbacks): A collection of Feedback objects with utilities.
- [`feedback.FeedbackQuery`](#class-feedbackquery): Lazy-loading object for fetching feedback from the server.
- [`feedback.RefFeedbackQuery`](#class-reffeedbackquery): Object for interacting with feedback associated with a particular ref.




---


<a href="https://github.com/wandb/weave/blob/master/weave/trace/feedback.py#L21"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `Feedbacks`
A collection of Feedback objects with utilities. 

<a href="https://github.com/wandb/weave/blob/master/weave/trace/feedback.py#L26"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    show_refs: 'bool',
    feedbacks: 'Iterable[Feedback] | None' = None
) → None
```








---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/feedback.py#L32"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `refs`

```python
refs() → Refs
```

Return the unique refs associated with these feedbacks. 


---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/feedback.py#L84"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `FeedbackQuery`
Lazy-loading object for fetching feedback from the server. 

<a href="https://github.com/wandb/weave/blob/master/weave/trace/feedback.py#L97"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    entity: 'str',
    project: 'str',
    query: 'Query',
    offset: 'int | None' = None,
    limit: 'int | None' = None,
    show_refs: 'bool' = False
)
```








---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/feedback.py#L145"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `execute`

```python
execute() → Feedbacks
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/feedback.py#L126"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `refresh`

```python
refresh() → Feedbacks
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/feedback.py#L151"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `refs`

```python
refs() → Refs
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/feedback.py#L168"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `RefFeedbackQuery`
Object for interacting with feedback associated with a particular ref. 

<a href="https://github.com/wandb/weave/blob/master/weave/trace/feedback.py#L173"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `__init__`

```python
__init__(ref: 'str') → None
```








---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/feedback.py#L204"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `add`

```python
add(
    feedback_type: 'str',
    payload: 'dict[str, Any] | None' = None,
    creator: 'str | None' = None,
    **kwargs: 'dict[str, Any]'
) → str
```

Add feedback to the ref. 

feedback_type: A string identifying the type of feedback. The "wandb." prefix is reserved. creator: The name to display for the originator of the feedback. 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/feedback.py#L232"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `add_note`

```python
add_note(note: 'str', creator: 'str | None' = None) → str
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/feedback.py#L223"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `add_reaction`

```python
add_reaction(emoji: 'str', creator: 'str | None' = None) → str
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/feedback.py#L145"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `execute`

```python
execute() → Feedbacks
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/feedback.py#L241"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `purge`

```python
purge(feedback_id: 'str') → None
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/feedback.py#L126"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `refresh`

```python
refresh() → Feedbacks
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/feedback.py#L151"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `refs`

```python
refs() → Refs
```





