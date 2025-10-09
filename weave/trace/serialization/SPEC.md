# Weave Serialization

## Problem

Markdown stored content inline as JSON, bloating payloads for large markdown.

## Solution

Added 3rd parameter to `load(artifact, name, metadata)` for hybrid pattern. Markdown now stores `.md` file + returns metadata dict.

## Markdown Example

```python
def save(obj: Markdown, artifact, name: str) -> dict | None:
    with artifact.new_file("content.md", binary=False) as f:
        f.write(obj.markup)
    return {"code_theme": obj.code_theme} if obj.code_theme else None

def load(artifact, name: str, metadata) -> Markdown:
    with artifact.open("content.md", binary=False) as f:
        markup = f.read()
    code_theme = metadata.get("code_theme") if metadata else None
    return Markdown(markup, code_theme=code_theme)

serializer.register_serializer(Markdown, save, load)
```

## Dispatch Logic

Count parameters:
- 1 param → inline
- 3 params → file-based (with or without metadata return)

```python
sig = inspect.signature(serializer.save)
if len(sig.parameters) == 1:
    encoded["val"] = serializer.save(obj)
else:
    artifact = MemTraceFilesArtifact()
    metadata = serializer.save(obj, artifact, "obj")
    if artifact.path_contents:
        encoded["files"] = artifact.path_contents
    if metadata is not None:
        encoded["val"] = metadata
```

Legacy loads check param count (2 vs 3) to know whether to pass metadata.
