# Weave Serialization Layer Specification

## Problem Statement

The Weave serialization system allows custom Python objects to be stored in the trace server and reconstructed later. This is critical for persisting objects like PIL Images, Markdown content, audio/video files, and custom data structures across Python runtimes.

### Original Issues

1. **Inconsistent Implementations**: Different serializers used different patterns
   - `Image` serializer: File-based API (stores binary data in artifact files)
   - `Markdown` serializer: Metadata API (stored content as inline JSON)
   - No unified interface between the two approaches

2. **Buggy Inspection-Based Dispatch**: The original `serializer.py` used parameter counting to determine serializer types
   - Fragile: Relied on counting function parameters (1 param = inline, 3 params = file-based)
   - Error-prone: Easy to miscount or create ambiguous signatures
   - Hard to maintain: No explicit contract for serializers to implement

3. **Inflexible Design**: Couldn't support hybrid patterns
   - Some objects need BOTH files and metadata (e.g., Audio with format metadata + binary data)
   - Original design forced a choice between file-based OR metadata-based

4. **Suboptimal Storage**: Markdown stored content inline instead of as files
   - Large markdown content bloated JSON metadata
   - Should store as `.md` files in the artifact

## Solution Overview

### Core Design Principles

1. **Single Unified Interface**: `WeaveSerializer` base class supports all patterns
2. **Static Methods**: Both `save()` and `load()` are static (no instance state needed)
3. **Normalize at Registration**: Convert both APIs to callables once, use everywhere
4. **Inspection When Needed**: Use parameter counting only for legacy compatibility

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    WeaveSerializer (ABC)                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ @staticmethod                                        │   │
│  │ save(obj, artifact, name) -> metadata | None        │   │
│  │                                                       │   │
│  │ @staticmethod                                        │   │
│  │ load(artifact, name, metadata) -> obj                │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                         ▲
                         │ inherits
         ┌───────────────┼───────────────┐
         │               │               │
    ImageSerializer  MarkdownSerializer  AudioSerializer
    (files only)     (files + metadata)  (files + metadata)
```

## API Design

### 1. WeaveSerializer Base Class

```python
class WeaveSerializer(ABC):
    """Base class for all Weave serializers."""

    @staticmethod
    def save(obj: Any, artifact: MemTraceFilesArtifact, name: str) -> Any | None:
        """Save an object, optionally returning metadata.

        Returns:
            - None if files-only (e.g., Image)
            - dict/str/etc if metadata-only or hybrid (e.g., Markdown)
        """
        raise NotImplementedError

    @staticmethod
    def load(artifact: MemTraceFilesArtifact, name: str, metadata: Any | None) -> Any:
        """Load an object from files and/or metadata.

        This function gets serialized as an op for cross-runtime deserialization.
        """
        raise NotImplementedError
```

**Why Static Methods?**
- No instance state needed
- Load function gets serialized as an op and must be standalone
- Simpler mental model: serializer is just a namespace for two functions

### 2. Serializer Dataclass

```python
@dataclass
class Serializer:
    """Internal representation of a registered serializer."""
    target_class: type
    save: Callable  # Normalized save function
    load: Callable  # Normalized load function
    instance_check: Callable[[Any], bool] | None = None

    def id(self) -> str:
        """Return the unique ID for this serializer (module.ClassName)."""
        serializer_id = self.target_class.__module__ + "." + self.target_class.__name__
        # Special case for weave.Op
        if serializer_id.startswith("weave.") and serializer_id.endswith(".Op"):
            return "Op"
        return serializer_id
```

**Key Design Decision**: Store normalized callables, not WeaveSerializer classes or separate field variants.

- ✅ Simple: Just two functions, always populated
- ✅ Fast: No helper methods, no conditionals at usage sites
- ✅ Clear: `serializer.save()` and `serializer.load()` work everywhere
- ✅ ID method: Provides unique identifier for database storage

### 3. Registration Function

```python
def register_serializer(
    target_class: type,
    save: Callable | Type[WeaveSerializer],
    load: Callable | None = None,
    instance_check: Callable[[Any], bool] | None = None,
) -> None:
    """Register a serializer for a type.

    Accepts either:
    1. WeaveSerializer class (new API) - omit load parameter
    2. Save/load functions (legacy API) - provide both
    """
```

**Normalization Logic**:
```python
if isinstance(save, type) and issubclass(save, WeaveSerializer):
    # New API: extract static methods
    save_func = save.save
    load_func = save.load
else:
    # Legacy API: use provided functions
    save_func = save
    load_func = load
```

### 4. Lookup Functions

```python
def get_serializer_by_id(id: str) -> Serializer | None:
    """Find a serializer by its type ID (module.ClassName)."""
    for serializer in SERIALIZERS:
        if serializer.id() == id:
            return serializer
    return None

def get_serializer_for_obj(obj: Any) -> Serializer | None:
    """Find a serializer for an object instance."""
    for serializer in SERIALIZERS:
        if serializer.instance_check and serializer.instance_check(obj):
            return serializer
        elif isinstance(obj, serializer.target_class):
            return serializer
    return None
```

**Note**: `instance_check` is used for special cases where `isinstance()` checks fail (e.g., Protocol types in Python 3.12+).

## Implementation Patterns

### Pattern 1: Hybrid Files + Metadata (Markdown - New API)

Markdown demonstrates the new WeaveSerializer API with hybrid pattern:

```python
class MarkdownSerializer(WeaveSerializer):
    @staticmethod
    def save(obj: Markdown, artifact, name: str) -> dict | None:
        # Store content as file
        with artifact.new_file("content.md", binary=False) as f:
            f.write(obj.markup)

        # Return metadata
        metadata = {}
        if obj.code_theme:
            metadata["code_theme"] = obj.code_theme
        return metadata if metadata else None

    @staticmethod
    def load(artifact, name: str, metadata: Any) -> Markdown:
        # Load from both files and metadata
        with artifact.open("content.md", binary=False) as f:
            markup = f.read()

        kwargs = {}
        if metadata and isinstance(metadata, dict):
            if "code_theme" in metadata:
                kwargs["code_theme"] = metadata["code_theme"]

        return Markdown(markup=markup, **kwargs)

# Registration
register_serializer(Markdown, MarkdownSerializer)
```

### Pattern 2: Legacy File-Based Functions (Image - Current Implementation)

Most existing serializers still use the legacy function-based API:

```python
def save(obj: Image.Image, artifact, name: str) -> None:
    with artifact.new_file("image.png", binary=True) as f:
        obj.save(f, format="PNG")

def load(artifact, name: str) -> Image.Image:
    filename = next(iter(artifact.path_contents))
    return Image.open(artifact.path(filename))

# Registration
register_serializer(Image.Image, save, load)
```

### Pattern 3: Legacy Inline Functions (Also Supported)

```python
def save_datetime(obj: datetime) -> dict:
    return {"iso": obj.isoformat()}

def load_datetime(data: dict) -> datetime:
    return datetime.fromisoformat(data["iso"])

# Registration
register_serializer(datetime, save_datetime, load_datetime)
```

## Serialization Flow

### Dispatch Logic (Maximally Simple)

No helper functions needed - just count parameters:

```python
sig = inspect.signature(serializer.save)
param_count = len(sig.parameters)

if param_count == 1:
    # Legacy inline: (obj) -> metadata
    encoded["val"] = serializer.save(obj)
else:
    # File-based (legacy or new): (obj, artifact, name) -> metadata | None
    artifact = MemTraceFilesArtifact()
    metadata = serializer.save(obj, artifact, "obj")

    if artifact.path_contents:
        encoded["files"] = artifact.path_contents

    if metadata is not None:
        encoded["val"] = metadata
```

**Key Insight**:
- 1 param → legacy inline
- 3 params → file-based (legacy returns None, new API may return metadata)

### Encoding (save)

```
1. User saves object with weave.publish() or similar
2. encode_custom_obj(obj) is called
3. Find serializer: get_serializer_for_obj(obj)
4. Save load function as op (for cross-runtime deserialization)
5. Count parameters and dispatch (see above)
6. Store in database with type ID and load_op reference
```

### Decoding (load)

```
1. User calls client.get(ref)
2. Database returns encoded object with type ID
3. Find serializer: get_serializer_by_id(type_id)
4. Dispatch based on signature inspection:

   sig = inspect.signature(serializer.load)
   param_count = len(sig.parameters)

   if param_count == 3:                      # New API: (artifact, name, metadata)
       artifact = MemTraceFilesArtifact(files)
       return serializer.load(artifact, "obj", metadata)

   elif param_count == 2:                    # Legacy file: (artifact, name)
       artifact = MemTraceFilesArtifact(files)
       return serializer.load(artifact, "obj")

   elif param_count == 1:                    # Legacy inline: (val)
       return serializer.load(metadata)

5. If no serializer found locally, load from saved load_op (cross-runtime case)
```

## Migration Guide

### For New Serializers

Just implement `WeaveSerializer`:

```python
from weave.trace.serialization.base_serializer import WeaveSerializer
from weave.trace.serialization import serializer

class MySerializer(WeaveSerializer):
    @staticmethod
    def save(obj: MyType, artifact, name: str) -> dict | None:
        # Your save logic here
        pass

    @staticmethod
    def load(artifact, name: str, metadata: Any) -> MyType:
        # Your load logic here
        pass

serializer.register_serializer(MyType, MySerializer)
```

### For Existing Legacy Serializers

No changes needed! Legacy function-based serializers continue to work:

```python
# This still works exactly as before
serializer.register_serializer(MyType, save_fn, load_fn)
```

## Design Rationale

### Why Not Generic `WeaveSerializer[T]`?

We don't use `WeaveSerializer[Image.Image]` because:
1. Python's type system doesn't enforce it at runtime anyway
2. The static methods don't use `T` in their implementation
3. Simpler without generic complexity
4. Type hints in individual implementations are sufficient

### Why Normalize at Registration?

**Alternative**: Store `WeaveSerializer` class, extract methods at usage time

```python
# ❌ BAD: Check type every time we use it
if serializer.weave_serializer:
    save_func = serializer.weave_serializer.save
else:
    save_func = serializer.legacy_save

save_func(obj, art, name)
```

**Our Approach**: Extract methods once at registration

```python
# ✅ GOOD: Just use it
serializer.save(obj, art, name)
```

Benefits:
- Simpler usage: No helper methods, no conditionals
- Better performance: Normalization happens once, not on every call
- Cleaner code: 52 fewer lines, no helper methods
- Easier to reason about: Serializer always has `save` and `load`

### Why Single `register_serializer()` Function?

**Alternative**: Separate functions for each API

```python
register_weave_serializer(cls, serializer_class)
register_serializer_functions(cls, save, load)
```

**Our Approach**: One function that handles both

```python
register_serializer(cls, save, load=None)
```

Benefits:
- Less API surface to learn
- Type detection is simple: `isinstance(save, type) and issubclass(save, WeaveSerializer)`
- Backward compatible: Legacy code continues to work
- Clear documentation: One function with examples for both APIs

### Why Static Methods Instead of Instance Methods?

**Critical Requirement**: The load function gets serialized as an op and sent to the server. When deserializing in a different Python runtime, we need to be able to call this function standalone.

```python
# ❌ BAD: Instance method
class ImageSerializer(WeaveSerializer):
    def load(self, artifact, name, metadata):  # Needs 'self'
        return Image.open(artifact.path("image.png"))

# Problem: When deserializing, we'd need to create an instance first
serializer_instance = ImageSerializer()  # Where does this come from?
obj = serializer_instance.load(art, "obj", None)
```

```python
# ✅ GOOD: Static method
class ImageSerializer(WeaveSerializer):
    @staticmethod
    def load(artifact, name, metadata):  # No 'self' needed
        return Image.open(artifact.path("image.png"))

# Solution: Can call directly without instance
obj = ImageSerializer.load(art, "obj", None)
```

Static methods are standalone functions that can be serialized and called without needing an instance.

## Testing Strategy

### Unit Tests

1. **Registration Tests**
   - Register WeaveSerializer class
   - Register legacy functions
   - Register with instance_check
   - Error handling (missing load function)

2. **Serialization Tests**
   - Files-only pattern (Image)
   - Metadata-only pattern (legacy inline)
   - Hybrid pattern (Markdown)
   - Round-trip: save → load → verify equality

3. **Inspection Tests**
   - Correct dispatch for 1-param functions (inline)
   - Correct dispatch for 3-param functions (file/new API)
   - Signature detection with different annotations

4. **Cross-Runtime Tests**
   - Serialize with local serializer
   - Deserialize without local serializer (load from op)
   - Verify load_op is saved correctly

### Integration Tests

1. **Type Handler Tests**
   - Test all built-in type handlers (Image, Markdown, Audio, Video, etc.)
   - Verify backward compatibility with existing serialized objects

2. **Client Tests**
   - Save objects with `weave.publish()`
   - Retrieve objects with `client.get()`
   - Verify artifacts are stored correctly

## File Structure

```
weave/trace/serialization/
├── SPEC.md                    # This specification
├── base_serializer.py         # WeaveSerializer ABC
├── serializer.py              # Registration & Serializer dataclass
├── custom_objs.py             # Encoding/decoding logic
├── mem_artifact.py            # MemTraceFilesArtifact
└── serialize.py               # High-level serialization API

weave/type_handlers/
├── Image/image.py             # Example: files-only
├── Markdown/markdown.py       # Example: hybrid
├── Audio/audio.py             # Example: hybrid
└── [other handlers]/          # Legacy examples
```

## FAQ

**Q: Why not use `__init_subclass__` to auto-register serializers?**

A: Explicit registration is clearer and gives more control. Auto-registration can cause import-time side effects and makes it harder to understand when serializers are registered.

**Q: Can I use async save/load methods?**

A: Not currently. The serialization system is synchronous. Async support would require significant changes to the encoding/decoding pipeline.

**Q: What happens if I register multiple serializers for the same type?**

A: The last registered serializer wins. Serializers are stored in a list and searched in order, so later registrations override earlier ones.

**Q: Can I serialize objects that contain other serialized objects?**

A: Yes! The serialization system handles nested objects automatically. Each nested object will use its own registered serializer.

**Q: Why do we save the load function as an op?**

A: This enables cross-runtime deserialization. If you serialize an object in one Python environment and deserialize it in another (e.g., a different machine, container, or time), the load function op allows reconstruction even if the serializer isn't registered locally.

## Future Enhancements

1. **Async Support**: Allow async save/load for large files or network operations
2. **Streaming**: Support streaming large files instead of loading entirely in memory
3. **Compression**: Automatic compression for large artifacts
4. **Versioning**: Support multiple serializer versions for the same type
5. **Validation**: Schema validation for metadata using Pydantic or similar
6. **Caching**: Cache deserialized objects to avoid repeated loads

## References

- Implementation: `weave/trace/serialization/`
- Type Handlers: `weave/type_handlers/`
- Tests: `tests/trace/test_serializer.py`
- Original Discussion: See git history for commit messages with detailed rationale
