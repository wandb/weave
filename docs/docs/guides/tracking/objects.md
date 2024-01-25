---
sidebar_position: 0
hide_table_of_contents: true
---

# Objects

Weave's serialization layer saves and versions Python objects, backed by [W&B Artifacts](https://docs.wandb.ai/guides/artifacts).

## Publishing an object

```python
# Initialize tracking to the project 'cat-project'
weave.init('cat-project')
# Save a list, giving it the name 'cat-names'
weave.publish(['felix', 'jimbo', 'billie'], 'cat-names')
```

Saving an object with a name will create the first version of that object if it doesn't exist.

## Getting an object back

`weave.publish` returns a Ref. You can call `.get()` on any Ref to get the object back.

You can construct a ref and then fetch the object back.
```python
weave.init('cat-project')
cat_names = weave.ref('cat-names').get()
```

## Ref styles

A fully qualified weave object ref uri looks like this:

```
wandb-artifact://<entity>/<project>/<object_name>:<object_version>/obj
```

- *entity*: wandb entity (username or team)
- *project*: wandb project
- *object_name*: object name
- *object_version*: either a version hash, a string like v0, v1..., or an alias like ":latest". All objects have the ":latest" alias.


Refs can be constructed with a few different styles

- `weave.ref(<name>)`: requires `weave.init(<project>)` to have been called. Refers to the ":latest" version
- `weave.ref(<name>:<version>)`: requires `weave.init(<project>)` to have been called.
- `weave.ref(<fully_qualified_ref_uri>)`: can be constructed without calling weave.init


## TODO

- iterating through other versions of an object
- navigating to consuming and producing calls via the API
- declaring how to serializes other types of objects
- @weave.type()
