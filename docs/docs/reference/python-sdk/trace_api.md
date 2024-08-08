

# API Overview

## Modules

- No modules

## Classes

- No classes

## Functions

- [`trace_api.init`](./weave.trace_api.md#function-init): Initialize weave tracking, logging to a wandb project.
- [`trace_api.publish`](./weave.trace_api.md#function-publish): Save and version a python object.
- [`trace_api.ref`](./weave.trace_api.md#function-ref): Construct a Ref to a Weave object.
- [`call_context.get_current_call`](./weave.call_context.md#function-get_current_call): Get the Call object for the currently executing Op, within that Op.
- [`trace_api.finish`](./weave.trace_api.md#function-finish): Stops logging to weave.

---
The top-level functions for Weave Trace API.
---

### <kbd>function</kbd> `init`

```python
init(
    project_name: str,
    settings: Optional[weave.trace.settings.UserSettings, dict[str, Any]] = None
) → WeaveClient
```

Initialize weave tracking, logging to a wandb project. 

Logging is initialized globally, so you do not need to keep a reference to the return value of init. 

Following init, calls of weave.op() decorated functions will be logged to the specified project. 



**Args:**
 
 - <b>`project_name`</b>:  The name of the Weights & Biases project to log to. 



**Returns:**
 A Weave client. 

---

### <kbd>function</kbd> `publish`

```python
publish(obj: Any, name: Optional[str] = None) → ObjectRef
```

Save and version a python object. 

If an object with name already exists, and the content hash of obj does not match the latest version of that object, a new version will be created. 

TODO: Need to document how name works with this change. 



**Args:**
 
 - <b>`obj`</b>:  The object to save and version. 
 - <b>`name`</b>:  The name to save the object under. 



**Returns:**
 A weave Ref to the saved object. 

---

### <kbd>function</kbd> `ref`

```python
ref(location: str) → ObjectRef
```

Construct a Ref to a Weave object. 

TODO: what happens if obj does not exist 



**Args:**
 
 - <b>`location`</b>:  A fully-qualified weave ref URI, or if weave.init() has been called, "name:version" or just "name" ("latest" will be used for version in this case). 





**Returns:**
 A weave Ref to the object. 

---

### <kbd>function</kbd> `get_current_call`

```python
get_current_call() → Optional[ForwardRef('Call')]
```

Get the Call object for the currently executing Op, within that Op. 

This allows you to access attributes of the Call such as its id or feedback while it is running. 

```python
@weave.op
def hello(name: str) -> None:
     print(f"Hello {name}!")
     current_call = weave.get_current_call()
     print(current_call.id)
``` 

It is also possible to access a Call after the Op has returned. 

If you have the Call's id, perhaps from the UI, you can use the `call` method on the `WeaveClient` returned from `weave.init` to retrieve the Call object. 

```python
client = weave.init("<project>")
mycall = client.call("<call_id>")
``` 

Alternately, after defining your Op you can use its `call` method. For example: 

```python
@weave.op
def hello(name: str) -> None:
     print(f"Hello {name}!")

mycall = hello.call("world")
print(mycall.id)
``` 



**Returns:**
  The Call object for the currently executing Op, or  None if tracking has not been initialized or this method is  invoked outside an Op. 

---

### <kbd>function</kbd> `finish`

```python
finish() → None
```

Stops logging to weave. 

Following finish, calls of weave.op() decorated functions will no longer be logged. You will need to run weave.init() again to resume logging. 
