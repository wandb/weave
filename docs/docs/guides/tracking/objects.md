# Objects

Weave's serialization layer saves and versions Python objects.

## Publishing an object

```python
import weave
# Initialize tracking to the project 'intro-example'
weave.init('intro-example')
# Save a list, giving it the name 'cat-names'
weave.publish(['felix', 'jimbo', 'billie'], 'cat-names')
```

Saving an object with a name will create the first version of that object if it doesn't exist.

## Getting an object back

`weave.publish` returns a Ref. You can call `.get()` on any Ref to get the object back.

You can construct a ref and then fetch the object back.

```python
weave.init('intro-example')
cat_names = weave.ref('cat-names').get()
```

## Ref styles

A fully qualified weave object ref uri looks like this:

```
weave:///<entity>/<project>/object/<object_name>:<object_version>
```

- _entity_: wandb entity (username or team)
- _project_: wandb project
- _object_name_: object name
- _object_version_: either a version hash, a string like v0, v1..., or an alias like ":latest". All objects have the ":latest" alias.

Refs can be constructed with a few different styles

- `weave.ref(<name>)`: requires `weave.init(<project>)` to have been called. Refers to the ":latest" version
- `weave.ref(<name>:<version>)`: requires `weave.init(<project>)` to have been called.
- `weave.ref(<fully_qualified_ref_uri>)`: can be constructed without calling weave.init
