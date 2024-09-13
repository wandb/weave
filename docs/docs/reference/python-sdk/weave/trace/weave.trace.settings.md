---
sidebar_label: settings
---
    

# weave.trace.settings

Settings for Weave.

TODO: Fill this in with examples on how to use the settings.


---


# API Overview



## Classes

- [`settings.UserSettings`](#class-usersettings): User configuration for Weave.

## Functions

- [`settings.parse_and_apply_settings`](#function-parse_and_apply_settings)
- [`settings.should_disable_weave`](#function-should_disable_weave)
- [`settings.should_print_call_link`](#function-should_print_call_link)


---


<a href="https://github.com/wandb/weave/blob/master/weave/trace/settings.py#L19"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `UserSettings`
User configuration for Weave. 

All configs can be overrided with environment variables.  The precedence is environment variables > `weave.trace.settings.UserSettings`. 


**Pydantic Fields:**

- `disabled`: `<class 'bool'>`
- `print_call_link`: `<class 'bool'>`
---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/settings.py#L44"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>method</kbd> `apply`

```python
apply() → None
```






---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/settings.py#L63"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>function</kbd> `parse_and_apply_settings`

```python
parse_and_apply_settings(
    settings: Optional[UserSettings, dict[str, Any]] = None
) → None
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/settings.py#L55"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>function</kbd> `should_disable_weave`

```python
should_disable_weave() → bool
```





---

<a href="https://github.com/wandb/weave/blob/master/weave/trace/settings.py#L59"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

### <kbd>function</kbd> `should_print_call_link`

```python
should_print_call_link() → bool
```




