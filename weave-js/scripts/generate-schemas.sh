#!/bin/bash

# Exit on error
set -e

SCHEMA_INPUT_PATH="../weave/trace_server/interface/builtin_object_classes/generated/generated_base_object_class_schemas.json"
SCHEMA_OUTPUT_PATH="./src/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/generatedBuiltinObjectClasses.zod.ts"

echo "Generating schemas..."

# Generate TypeScript-Zod types from schema
yarn quicktype -s schema "$SCHEMA_INPUT_PATH" -o "$SCHEMA_OUTPUT_PATH" --lang typescript-zod

# Transform the schema to extract the type map
sed -i.bak '
  # Find the generatedBuiltinObjectClassesZodSchema definition and capture its contents
  /export const generatedBuiltinObjectClassesZodSchema = z.object({/,/});/ {
    # Replace the opening line with typeMap declaration
    s/export const generatedBuiltinObjectClassesZodSchema = z.object({/export const builtinObjectClassRegistry = ({/
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
export const generatedBuiltinObjectClassesZodSchema = z.object(builtinObjectClassRegistry)
    }
  }
' "$SCHEMA_OUTPUT_PATH"

# Remove backup file
rm "${SCHEMA_OUTPUT_PATH}.bak"

# Format the generated file
yarn direct-prettier --write "$SCHEMA_OUTPUT_PATH"

echo "Schema generation completed successfully" 