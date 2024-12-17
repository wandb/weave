---
sidebar_label: op
---
    

# weave.trace.op

Defines the Op protocol and related functions.

---


# API Overview





## Functions

- [`op.call`](#function-call): Executes the op and returns both the result and a Call representing the execution.
- [`op.calls`](#function-calls): Get an iterator over all calls to this op.


---


<a href="https://github.com/wandb/weave/blob/master/weave/trace/op.py#L347"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>function</kbd> `call`

```python
call(
    op: 'Op',
    *args: 'Any',
    __weave: 'WeaveKwargs | None' = None,
    __should_raise: 'bool' = False,
    **kwargs: 'Any'
) → tuple[Any, Call] | Coroutine[Any, Any, tuple[Any, Call]]
```

Executes the op and returns both the result and a Call representing the execution. 

This function will never raise.  Any errors are captured in the Call object. 

This method is automatically bound to any function decorated with `@weave.op`, allowing for usage like: 

```python
@weave.op
def add(a: int, b: int) -> int:
     return a + b

result, call = add.call(1, 2)
``` 

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/op.py#L526"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>function</kbd> `calls`

```python
calls(op: 'Op') → CallsIter
```

Get an iterator over all calls to this op. 

This method is automatically bound to any function decorated with `@weave.op`, allowing for usage like: 

```python
@weave.op
def add(a: int, b: int) -> int:
     return a + b

calls = add.calls()
for call in calls:
     print(call)
``` 
