#!/bin/bash

# Exit on error
set -e

SCHEMA_PATH="../weave/trace_server/interface/builtin_object_classes/generated/generated_builtin_object_class_schemas.json"
OUTPUT_PATH="./src/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/generatedBuiltinObjectClasses.zod.ts"

echo "Generating schemas..."

# First resolve circular references in the schema
python3 ../weave/scripts/resolve_schema_circular_refs.py "$SCHEMA_PATH"

# Generate TypeScript-Zod types from schema
yarn quicktype -s schema "$SCHEMA_PATH" -o "$OUTPUT_PATH" --lang typescript-zod

# Transform the schema to extract the type map
sed -i.bak '
  # Find the GeneratedBuiltinObjectClassesZodSchema definition and capture its contents
  /export const GeneratedBuiltinObjectClassesZodSchema = z.object({/,/});/ {
    # Replace the opening line with typeMap declaration
    s/export const GeneratedBuiltinObjectClassesZodSchema = z.object({/export const builtinObjectClassRegistry = ({/
    # Store the pattern
    h
    # If this is the last line (with closing brace), append the schema definition
    /});/ {
      p
      s/.*//
      x
      s/.*//
      i\
\
export const GeneratedBuiltinObjectClassesZodSchema = z.object(builtinObjectClassRegistry)
    }
  }
' "$OUTPUT_PATH"

# Remove backup file
rm "${OUTPUT_PATH}.bak"

# Format the generated file
yarn direct-prettier --write "$OUTPUT_PATH"

echo "Schema generation completed successfully" 