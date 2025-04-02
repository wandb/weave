import {TraceCallSchema} from '../pages/wfReactInterface/traceServerClientTypes';

export interface SchemaField {
  name: string;
  type: string;
}

export const inferType = (value: any): string => {
  if (value === null) {
    return 'null';
  }
  if (Array.isArray(value)) {
    return 'array';
  }
  if (value instanceof Date) {
    return 'date';
  }
  if (value !== null && typeof value === 'object') {
    return 'object';
  }
  return typeof value;
};

export const flattenObject = (obj: any, prefix = ''): SchemaField[] => {
  let fields: SchemaField[] = [];

  // Return empty array for null or undefined inputs
  if (obj == null) {
    return fields;
  }

  // Special handling for __ref__ and __val__ pattern
  if (typeof obj === 'object' && '__ref__' in obj && '__val__' in obj) {
    return flattenObject(obj.__val__, prefix);
  }

  for (const [key, value] of Object.entries(obj)) {
    const newKey = prefix ? `${prefix}.${key}` : key;

    if (
      value !== null &&
      typeof value === 'object' &&
      !Array.isArray(value) &&
      !(value instanceof Date)
    ) {
      fields = [...fields, ...flattenObject(value, newKey)];
    } else {
      fields.push({
        name: newKey,
        type: inferType(value),
      });
    }
  }

  return fields;
};

export const inferSchema = (data: any): SchemaField[] => {
  const schemaMap = new Map<string, Set<string>>();

  const addToSchema = (obj: any) => {
    const flatFields = flattenObject(obj);
    flatFields.forEach(field => {
      if (!schemaMap.has(field.name)) {
        schemaMap.set(field.name, new Set());
      }
      schemaMap.get(field.name)?.add(field.type);
    });
  };

  if (Array.isArray(data)) {
    data.forEach(item => addToSchema(item));
  } else {
    addToSchema(data);
  }

  return Array.from(schemaMap.entries()).map(([name, types]) => ({
    name,
    type: Array.from(types).join(' | '),
  }));
};

export interface CallData {
  digest: string;
  val: TraceCallSchema;
}

export interface FieldMapping {
  sourceField: string;
  targetField: string;
}

/**
 * Get a nested value from an object using a path array
 * @param obj The object to extract value from
 * @param path Array of property names to traverse
 * @returns The value at the specified path or undefined if path doesn't exist
 */
export const getNestedValue = (obj: any, path: string[]): any => {
  let current = obj;
  for (const part of path) {
    if (current == null) {
      return undefined;
    }
    if (typeof current === 'object' && '__val__' in current) {
      current = current.__val__;
    }
    if (typeof current !== 'object') {
      return current;
    }
    current = current[part];
  }
  return current;
};

export const extractSourceSchema = (calls: CallData[]): SchemaField[] => {
  const allFields: SchemaField[] = [];

  if (!calls || !Array.isArray(calls)) {
    return allFields;
  }

  calls.forEach(call => {
    // Skip if call or call.val is undefined
    if (!call || !call.val) {
      return;
    }

    if (call.val.inputs) {
      allFields.push(...flattenObject(call.val.inputs, 'inputs'));
    }

    const output = call.val.output;
    if (output !== undefined) {
      if (typeof output === 'string') {
        allFields.push({name: 'output', type: 'string'});
      } else {
        allFields.push(...flattenObject(output, 'output'));
      }
    }
  });

  return allFields
    .filter(field => field.name !== 'inputs.self')
    .reduce((acc, field) => {
      if (!acc.some(f => f.name === field.name)) {
        acc.push(field);
      }
      return acc;
    }, [] as SchemaField[]);
};

/**
 * Suggests field mappings between a source schema and target schema, with support for nested paths
 * and existing mappings.
 *
 * The function follows this priority order for suggesting mappings:
 * 1. Keeps all valid existing mappings
 * 2. Exact matches between source and target field names
 * 3. Matches based on the last segment of nested paths (e.g. "inputs.examples.question" matches "question")
 * 4. Falls back to mapping remaining fields to "output" if available
 *
 * For nested path matching:
 * - Source field "inputs.examples.question" will match target field "question"
 * - Only the first source field ending in a given name is mapped (e.g. if both
 *   "inputs.question" and "inputs.examples.question" exist, first one is used)
 *
 * @param sourceSchema - Array of fields available in the source data
 * @param targetSchema - Array of fields required by the target schema
 * @param existingMappings - Array of existing field mappings to preserve if still valid
 * @returns Array of suggested field mappings, including preserved valid existing mappings
 */
export const suggestMappings = (
  sourceSchema: SchemaField[],
  targetSchema: SchemaField[],
  existingMappings: FieldMapping[]
): FieldMapping[] => {
  const sourceNames = new Set(sourceSchema.map(s => s.name));
  const targetNames = new Set(targetSchema.map(t => t.name));
  const sourcePathMap = new Map<string, string>();
  sourceSchema.forEach(source => {
    const parts = source.name.split('.');
    const lastPart = parts[parts.length - 1];
    if (!sourcePathMap.has(lastPart)) {
      sourcePathMap.set(lastPart, source.name);
    }
  });
  const suggested: FieldMapping[] = existingMappings.filter(
    m => targetNames.has(m.targetField) && sourceNames.has(m.sourceField)
  );
  const mappedTargets = new Set(suggested.map(m => m.targetField));
  const remainingTargets = targetSchema.filter(
    target => !mappedTargets.has(target.name)
  );
  remainingTargets.forEach(target => {
    if (sourceNames.has(target.name)) {
      suggested.push({sourceField: target.name, targetField: target.name});
      mappedTargets.add(target.name);
    }
  });
  remainingTargets.forEach(target => {
    if (!mappedTargets.has(target.name)) {
      const sourcePath = sourcePathMap.get(target.name);
      if (sourcePath) {
        suggested.push({sourceField: sourcePath, targetField: target.name});
        mappedTargets.add(target.name);
      }
    }
  });
  if (sourceNames.has('output')) {
    remainingTargets.forEach(target => {
      if (!mappedTargets.has(target.name)) {
        suggested.push({sourceField: 'output', targetField: target.name});
      }
    });
  }
  return suggested;
};

/**
 * Maps an array of call data to dataset rows formatted for MUI DataGrid consumption.
 *
 * @param selectedCalls - Array of call data containing inputs and outputs
 * @param fieldMappings - Array of mappings that define how call data fields map to dataset columns
 * @returns An array of rows compatible with MUI DataGrid, each containing mapped fields and Weave metadata
 *
 * Each returned row will:
 * - Be formatted for use in MUI DataGrid components
 * - Include a ___weave namespace containing metadata used by Weave's custom hooks and callbacks:
 *   - id: The digest of the call
 *   - isNew: Flag indicating this is a newly created row
 * - Include mapped values from the call's inputs/outputs based on fieldMappings
 * - Only include fields where the source value is defined
 */
export const mapCallsToDatasetRows = (
  selectedCalls: CallData[],
  fieldMappings: FieldMapping[]
) => {
  const resolveValue = (obj: any, path: string): any => {
    const parts = path.split('.');
    let current = obj;

    for (const part of parts) {
      if (current == null) {
        return undefined;
      }

      // Handle __ref__/__val__ pattern during value resolution
      if (
        typeof current === 'object' &&
        '__ref__' in current &&
        '__val__' in current
      ) {
        current = current.__val__;
      }

      current = current[part];
    }
    return current;
  };

  return selectedCalls.map(call => {
    const row: Record<string, any> = {};

    fieldMappings.forEach(mapping => {
      const inputs = call.val.inputs || {};
      const output = call.val.output;

      let sourceValue: any;
      if (mapping.sourceField === 'output' && typeof output === 'string') {
        sourceValue = output;
      } else {
        sourceValue = resolveValue({inputs, output}, mapping.sourceField);
      }

      if (sourceValue !== undefined) {
        row[mapping.targetField] = sourceValue;
      }
    });

    return {
      ___weave: {
        id: call.digest,
        isNew: true,
      },
      ...row,
    };
  });
};

/**
 * Filters row data for new datasets based on target fields.
 *
 * @param mappedRows - The rows mapped from calls
 * @param targetFields - Set of target field names to include
 * @returns Filtered rows containing only the specified target fields
 */
export function filterRowsForNewDataset(
  mappedRows: Array<{
    ___weave: {id: string; isNew: boolean};
    [key: string]: any;
  }>,
  targetFields: Set<string>
): Array<{___weave: {id: string; isNew: boolean}; [key: string]: any}> {
  return mappedRows
    .map(row => {
      try {
        if (!row || typeof row !== 'object' || !row.___weave) {
          return undefined;
        }

        const {___weave, ...rest} = row;
        const filteredData = Object.fromEntries(
          Object.entries(rest).filter(([key]) => targetFields.has(key))
        );
        return {
          ___weave,
          ...filteredData,
        };
      } catch (rowError) {
        console.error('Error processing row:', rowError);
        return undefined;
      }
    })
    .filter(row => row !== undefined) as Array<{
    ___weave: {id: string; isNew: boolean};
    [key: string]: any;
  }>;
}

/**
 * Creates a map of processed rows with schema-based filtering.
 *
 * @param mappedRows - The rows mapped from calls
 * @param datasetObject - The dataset object containing schema information
 * @returns A Map of row IDs to processed row data
 */
export function createProcessedRowsMap(
  mappedRows: Array<{
    ___weave: {id: string; isNew: boolean};
    [key: string]: any;
  }>,
  datasetObject: any
): Map<string, any> {
  return new Map(
    mappedRows
      .filter(row => row && row.___weave && row.___weave.id)
      .map(row => {
        // If datasetObject has a schema, filter row properties to match schema fields
        if (datasetObject?.schema && Array.isArray(datasetObject.schema)) {
          const schemaFields = new Set(
            datasetObject.schema.map((f: {name: string}) => f.name)
          );
          const {___weave, ...rest} = row;

          // Only include fields that are in the schema
          const filteredData = Object.fromEntries(
            Object.entries(rest).filter(([key]) => schemaFields.has(key))
          );

          return [
            row.___weave.id,
            {
              ...filteredData,
              ___weave: {...row.___weave, serverValue: filteredData},
            },
          ];
        }

        // Default case - keep all fields
        return [
          row.___weave.id,
          {...row, ___weave: {...row.___weave, serverValue: row}},
        ];
      })
  );
}

/**
 * Suggests field mappings between source and target schemas.
 *
 * This function attempts to match fields between schemas using various strategies:
 * 1. Preserves existing mappings if the fields still exist
 * 2. Matches fields with identical names
 * 3. Matches fields where one name contains the other
 *
 * @param sourceSchema - Array of fields in the source schema
 * @param targetSchema - Array of fields in the target schema
 * @param existingMappings - Optional array of existing mappings to preserve
 * @returns Array of suggested field mappings
 */
export const suggestFieldMappings = (
  sourceSchema: any[],
  targetSchema: any[],
  existingMappings: FieldMapping[] = []
): FieldMapping[] => {
  if (!sourceSchema.length || !targetSchema.length) {
    return existingMappings;
  }

  // Create mapping table of existing mappings for quick lookup
  const existingMappingsMap = new Map<string, string>();
  existingMappings.forEach(mapping => {
    existingMappingsMap.set(mapping.targetField, mapping.sourceField);
  });

  // Create a new array of suggested mappings
  const newMappings: FieldMapping[] = [];

  // Attempt to match fields by name
  targetSchema.forEach(targetField => {
    // If there's already a mapping for this target field, keep it
    if (existingMappingsMap.has(targetField.name)) {
      newMappings.push({
        targetField: targetField.name,
        sourceField: existingMappingsMap.get(targetField.name)!,
      });
      return;
    }

    // Try to find a matching source field by exact name
    const exactMatch = sourceSchema.find(
      sourceField => sourceField.name === targetField.name
    );
    if (exactMatch) {
      newMappings.push({
        targetField: targetField.name,
        sourceField: exactMatch.name,
      });
      return;
    }

    // Try to find a matching source field by name containing the target field name
    const containsMatch = sourceSchema.find(sourceField =>
      sourceField.name.toLowerCase().includes(targetField.name.toLowerCase())
    );
    if (containsMatch) {
      newMappings.push({
        targetField: targetField.name,
        sourceField: containsMatch.name,
      });
      return;
    }

    // Try to find a matching source field where the target field name contains the source field name
    const reverseContainsMatch = sourceSchema.find(sourceField =>
      targetField.name.toLowerCase().includes(sourceField.name.toLowerCase())
    );
    if (reverseContainsMatch) {
      newMappings.push({
        targetField: targetField.name,
        sourceField: reverseContainsMatch.name,
      });
      return;
    }

    // No matches found, leave this target field unmapped
  });

  return newMappings;
};
