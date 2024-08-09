---
sidebar_label: util
---
    

# weave.trace.util



---


# API Overview



## Classes

- [`util.ContextAwareThreadPoolExecutor`](#class-contextawarethreadpoolexecutor): A ThreadPoolExecutor that runs functions with the context of the caller.
- [`util.ContextAwareThread`](#class-contextawarethread): A Thread that runs functions with the context of the caller.




---


<a href="https://github.com/wandb/weave/blob/master/weave/trace/util.py#L8"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ContextAwareThreadPoolExecutor`
A ThreadPoolExecutor that runs functions with the context of the caller. 

This is a drop-in replacement for concurrent.futures.ThreadPoolExecutor that ensures weave calls behave as expected inside the executor.  Weave requires certain contextvars to be set (see call_context.py), but new threads do not automatically copy context from the parent, which can cause the call context to be lost -- not good!  This class automates contextvar copying so using this executor "just works" as the user probably expects. 

You can achieve the same effect without this class by instead writing: 

```python
with concurrent.futures.ThreadPoolExecutor() as executor:
     contexts = [copy_context() for _ in range(len(vals))]

     def _wrapped_fn(*args):
         return contexts.pop().run(fn, *args)

     executor.map(_wrapped_fn, vals)
``` 

<a href="https://github.com/wandb/weave/blob/master/weave/trace/util.py#L31"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `__init__`

```python
__init__(*args: Any, **kwargs: Any) → None
```








---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/util.py#L44"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `map`

```python
map(
    fn: Callable,
    *iterables: Iterable[Iterable],
    timeout: Optional[float] = None,
    chunksize: int = 1
) → Iterator
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/util.py#L37"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `submit`

```python
submit(fn: Callable, *args: Any, **kwargs: Any) → Any
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/util.py#L65"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ContextAwareThread`
A Thread that runs functions with the context of the caller. 

This is a drop-in replacement for threading.Thread that ensures calls behave as expected inside the thread.  Weave requires certain contextvars to be set (see call_context.py), but new threads do not automatically copy context from the parent, which can cause the call context to be lost -- not good!  This class automates contextvar copying so using this thread "just works" as the user probaly expects. 

You can achieve the same effect without this class by instead writing: 

```python
def run_with_context(func, *args, **kwargs):
     context = copy_context()
     def wrapper():
         context.run(func, *args, **kwargs)
     return wrapper

thread = threading.Thread(target=run_with_context(your_func, *args, **kwargs))
thread.start()
``` 

<a href="https://github.com/wandb/weave/blob/master/weave/trace/util.py#L89"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `__init__`

```python
__init__(*args: Any, **kwargs: Any) → None
```






---

#### <kbd>property</kbd> daemon

A boolean value indicating whether this thread is a daemon thread. 

This must be set before start() is called, otherwise RuntimeError is raised. Its initial value is inherited from the creating thread; the main thread is not a daemon thread and therefore all threads created in the main thread default to daemon = False. 

The entire Python program exits when only daemon threads are left. 

---

#### <kbd>property</kbd> ident

Thread identifier of this thread or None if it has not been started. 

This is a nonzero integer. See the get_ident() function. Thread identifiers may be recycled when a thread exits and another thread is created. The identifier is available even after the thread has exited. 

---

#### <kbd>property</kbd> name

A string used for identification purposes only. 

It has no semantics. Multiple threads may be given the same name. The initial name is set by the constructor. 

---

#### <kbd>property</kbd> native_id

Native integral thread ID of this thread, or None if it has not been started. 

This is a non-negative integer. See the get_native_id() function. This represents the Thread ID as reported by the kernel. 



---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/util.py#L93"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `run`

```python
run() → None
```





