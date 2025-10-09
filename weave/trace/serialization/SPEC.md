# Weave Serialization Layer

## Problem

Markdown serializer stored content inline as JSON, causing bloat for large markdown. Needed hybrid pattern: files + metadata.

## Solution

New optional `WeaveSerializer` base class for types needing files + metadata. Legacy function-based serializers unchanged.

## New API (Optional)

```python
from weave.trace.serialization.base_serializer import WeaveSerializer

class MarkdownSerializer(WeaveSerializer):
    @staticmethod
    def save(obj: Markdown, artifact, name: str) -> dict | None:
        # Save content as file
        with artifact.new_file("content.md", binary=False) as f:
            f.write(obj.markup)

        # Return metadata
        return {"code_theme": obj.code_theme} if obj.code_theme else None

    @staticmethod
    def load(artifact, name: str, metadata: dict | None) -> Markdown:
        with artifact.open("content.md", binary=False) as f:
            markup = f.read()

        code_theme = metadata.get("code_theme") if metadata else None
        return Markdown(markup, code_theme=code_theme)

# Register
serializer.register_serializer(Markdown, MarkdownSerializer)
```

## Legacy API (Still Works)

```python
# File-based (Image, Audio, Video, etc.)
def save(obj: Image.Image, artifact, name: str) -> None:
    with artifact.new_file("image.png", binary=True) as f:
        obj.save(f, format="PNG")

def load(artifact, name: str) -> Image.Image:
    return Image.open(artifact.path("image.png"))

serializer.register_serializer(Image.Image, save, load)

# Inline (DateTime, etc.)
def save_dt(obj: datetime) -> dict:
    return {"iso": obj.isoformat()}

def load_dt(data: dict) -> datetime:
    return datetime.fromisoformat(data["iso"])

serializer.register_serializer(datetime, save_dt, load_dt)
```

## Dispatch Logic

Count parameters:
- 1 param → legacy inline
- 3 params → file-based (legacy or new)

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

## Migration Status

- **Markdown**: Migrated to new API (stores `.md` file + metadata)
- **Everything else**: Legacy API (unchanged)

## Key Points

1. **Additive**: New API available, old API untouched
2. **Simple**: Just count parameters, no helper functions
3. **Static methods**: Load serialized as op for cross-runtime deserialization
4. **Single registration**: `register_serializer()` handles both APIs
