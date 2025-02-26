# Serialization Patterns Audit in Weave

## Overview

This doc covers the serialization patterns in Weave, including how objects are serialized, stored, and retrieved.

## Core Serialization Components

### 1. Basic Serialization (`serialize.py`)

The core serialization functionality is implemented in `weave/trace/serialize.py`, which provides:

- **to_json()**: Converts Python objects to JSON-serializable formats
- **from_json()**: Converts JSON data back to Python objects
- **dictify()**: Creates dictionary representations of objects
- **stringify()**: Provides string representations for objects that can't be serialized

The serialization process handles:

- Primitive types (int, float, str, bool, None)
- Collections (list, tuple, dict)
- Namedtuples
- ObjectRecords and References (ObjectRef, TableRef)
- Custom objects via the custom_objs module

### 2. Custom Object Serialization (`custom_objs.py`)

For objects that can't be directly serialized to JSON, Weave provides a custom object serialization system:

- **encode_custom_obj()**: Encodes custom objects using registered serializers
- **decode_custom_obj()**: Decodes custom objects using the appropriate serializer
- Uses a file-based approach to store serialized data

The system maintains a list of `KNOWN_TYPES` that are recognized and can be deserialized without requiring the original serializer to be registered in the current runtime.

### 3. Pluggable Serializers (`serializer.py`)

Weave allows registering custom serializers for specific types:

- **register_serializer()**: Registers save/load functions for a specific type
- **get_serializer_by_id()**: Retrieves a serializer by its ID
- **get_serializer_for_obj()**: Finds the appropriate serializer for an object

Example serializers include:

- Image serializer (for PIL.Image.Image)
- Audio serializer (for wave.Wave_read)
- Op serializer (for weave.Op)

### 4. Dictifiable Protocol (`serialization/dictifiable.py`)

A protocol for objects that can be converted to dictionaries:

- **Dictifiable**: Protocol defining the to_dict() method
- **try_to_dict()**: Attempts to convert an object to a dictionary using the protocol

### 5. Serialization Reversibility

An important consideration in the serialization system is whether the serialization process is reversible (i.e., whether the original object can be reconstructed from its serialized form). The reversibility of different serialization methods varies:

- **Custom Serializers**: Fully reversible. Objects serialized using registered custom serializers can be fully reconstructed with their original type and data.
- **to_json/from_json**: Partially reversible. Basic types, collections, and objects with registered serializers can be reconstructed. Complex objects without serializers may lose type information.
- **dictify**: Partially reversible. While dictify preserves more structure than stringify, it loses method information and may not capture all the necessary state to reconstruct the original object. The resulting dictionary contains class information but not the logic to reconstruct instances.
- **stringify**: Not reversible. The stringify method produces a string representation that is meant for display purposes only. It cannot be used to reconstruct the original object as it discards all type information and internal structure.
- **Dictifiable Protocol**: Potentially reversible, but depends on the implementation. If the to_dict method is designed to capture all necessary state and there's a corresponding from_dict method, objects can be reconstructed.

When designing systems that need to store and retrieve objects, it's crucial to use the appropriate serialization method based on whether the objects need to be reconstructed later.

## Adding Custom Types

Users who want to add their own custom types to Weave can do so by registering custom serializers. This section provides a guide for users who are not Weave developers but want to ensure their custom types can be properly serialized and deserialized.

### 1. Creating Serialization Functions

To add support for a custom type, you need to define two functions:

1. **Save Function**: Responsible for serializing the object to files
2. **Load Function**: Responsible for deserializing the object from files

Example:

```python
from weave.trace import serializer
from weave.trace.custom_objs import MemTraceFilesArtifact

class MyCustomType:
    def __init__(self, value):
        self.value = value

def save_my_type(obj: MyCustomType, artifact: MemTraceFilesArtifact, name: str) -> None:
    # Save the object's data to a file in the artifact
    with artifact.new_file(f"{name}.txt") as f:
        f.write(str(obj.value))

def load_my_type(artifact: MemTraceFilesArtifact, name: str) -> MyCustomType:
    # Load the object's data from the file in the artifact
    with artifact.open(f"{name}.txt") as f:
        value = f.read()
    return MyCustomType(value)
```

### 2. Registering the Serializer

Once you have defined the save and load functions, you need to register them with Weave:

```python
from weave.trace import serializer

# Register the serializer for your custom type
serializer.register_serializer(MyCustomType, save_my_type, load_my_type)
```

### 3. Using Custom Types with Weave

After registering the serializer, you can use your custom type with Weave operations:

```python
import weave

# Create an instance of your custom type
my_obj = MyCustomType("Hello, Weave!")

# Save the object to Weave
client = weave.init()
ref = client.save(my_obj, "my-custom-object")

# Retrieve the object from Weave
retrieved_obj = client.get(ref)
print(retrieved_obj.value)  # Output: Hello, Weave!
```

### 4. Handling Large Data

For custom types that contain large data, you should be careful about how you serialize them. Weave provides mechanisms to handle large files efficiently:

```python
def save_large_data(obj, artifact, name):
    with artifact.new_file(name) as f:
        # Write data in chunks to avoid memory issues
        for chunk in obj.get_data_chunks():
            f.write(chunk)

def load_large_data(artifact, name):
    # Load data efficiently
    return LargeDataType(artifact.path(name))
```

### 5. Cross-Runtime Compatibility

When a custom object is saved, Weave also saves the load function as an operation. This allows the object to be deserialized in a Python runtime that does not have the serializer registered, as long as the necessary dependencies are available.

## Gaps and Limitations

Based on the analysis, the following gaps in the current serialization and object management system have been identified:

1. **Collection Support**: There's no explicit support for organizing objects into collections or groups. Objects are currently identified by their IDs and can be filtered by base classes, but there's no way to group related objects together.

2. **Pagination**: While the ObjQueryReq supports limit and offset parameters, there's no high-level pagination API in the client for efficiently browsing large sets of objects.

3. **List Objects API**: There's no dedicated API for listing objects with collection support and pagination. The current `_objects()` method is internal and doesn't provide a user-friendly interface for browsing objects.

4. **Metadata Querying**: While objects can be filtered by their base classes and IDs, there's limited support for querying objects based on their metadata or attributes.

5. **Collection Management**: There's no API for creating, updating, or deleting collections of objects.

6. **Serialization Error Handling**: The current system silently returns None when no serializer is found for an object, which can lead to data loss without clear error messages.

7. **Type Registration Discovery**: There's no easy way for users to discover what types are already registered or to list available serializers.

8. **Serialization Reversibility**: Not all serialization methods are reversible. The system lacks clear documentation about which methods preserve enough information to reconstruct objects and which are for display purposes only.

## Recommendations

To address these gaps, the following implementations are recommended:

1. **Collection Support**:

   - Add a collection field to objects or create a separate collection mapping system
   - Implement APIs for creating and managing collections

2. **Enhanced Pagination**:

   - Create a PaginatedObjectIterator similar to the existing PaginatedIterator for calls
   - Support both offset-based and cursor-based pagination

3. **List Objects API**:

   - Implement a public `list_objects()` method in WeaveClient
   - Support filtering by collections, object types, and metadata
   - Include pagination support

4. **Collection Management API**:

   - Add methods for creating, updating, and deleting collections
   - Support moving objects between collections

5. **Metadata Querying**:

   - Enhance the ObjectVersionFilter to support querying by object metadata
   - Add support for complex queries using the existing Query system

6. **Improved Serialization Error Handling**:

   - Provide clear warnings or errors when objects cannot be serialized
   - Add logging for serialization failures

7. **Serializer Registry API**:

   - Add methods to list registered serializers
   - Provide documentation on available serializers

8. **Serialization Reversibility Documentation**:
   - Clearly document which serialization methods are reversible and which are not
   - Provide guidelines for choosing the appropriate serialization method based on use case

## Implementation Approach

The implementation should follow these steps:

1. Extend the server interface to support collections and enhanced object querying
2. Update the database schema to store collection information
3. Implement the client-side APIs for collection management and object listing
4. Add pagination support to the object listing API
5. Create comprehensive tests for the new functionality
6. Improve error handling and documentation for serialization
7. Add clear documentation about serialization reversibility

This approach will provide a more user-friendly and powerful way to manage and browse objects in the Weave system.
