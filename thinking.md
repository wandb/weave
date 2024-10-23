Object Creation:

1. Have a registry of "base_class_name" -> "BaseModel" 
2. Maybe we should require that they are all something like "Object" with name and description?
3. When you fetch, they deserialize to perfect type (no refs, all resolved)
4. Saving: recursively saves nested objects:
    1. Model Validate on the raw payload
    2. 