# Contributing to Weave Python

When contributing to Weave Python, you will be creating Ops, Panels, and Types.

- `Ops` are essentially functions.
- `Panels` are displayable components.
- `Types` are the data definitions that tie everything together and define serialization rules. All saved objects must have belong to a Type.

## Hello World

Let's start by creating a basic `Hello World` Op.

```python
import weave

@weave.op
def hello_world():
    print("Hello World!")
```
