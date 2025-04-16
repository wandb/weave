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

/**
 * Re-nests flattened data with dot notation paths into a nested object structure.
 * @param flatData Object with flattened dot notation paths
 * @returns Hierarchically nested object
 */
export const denestData = (
  flatData: Record<string, any>
): Record<string, any> => {
  const nestedObject: Record<string, any> = {};
  Object.entries(flatData).forEach(([key, value]) => {
    const parts = key.split('.');
    let current = nestedObject;

    // Build the nested structure
    for (let i = 0; i < parts.length - 1; i++) {
      const part = parts[i];
      if (!current[part]) {
        current[part] = {};
      }
      current = current[part];
    }

    // Set the value at the final part
    const lastPart = parts[parts.length - 1];
    current[lastPart] = value;
  });

  return nestedObject;
};

/**
 * Extracts only the top-level fields from an object without deep flattening.
 * Used primarily for source/call schema where we only want the top-level structure.
 */
export const extractTopLevelFields = (obj: any, prefix = ''): SchemaField[] => {
  const fields: SchemaField[] = [];

  // Return empty array for null or undefined inputs
  if (obj == null) {
    return fields;
  }

  if (Array.isArray(obj)) {
    fields.push({
      name: prefix,
      type: 'array',
    });
    return fields;
  }

  // Special handling for __ref__ and __val__ pattern
  if (typeof obj === 'object' && '__ref__' in obj && '__val__' in obj) {
    if (typeof obj.__val__ === 'object' && !Array.isArray(obj.__val__)) {
      // For object values, extract its top-level fields
      return extractTopLevelFields(obj.__val__, prefix);
    } else {
      // For primitive or array values, return as is
      return [{name: prefix, type: inferType(obj.__val__)}];
    }
  }

  for (const [key, value] of Object.entries(obj)) {
    const newKey = prefix ? `${prefix}.${key}` : key;
    fields.push({
      name: newKey,
      type: inferType(value),
    });
  }

  return fields;
};

/**
 * Creates a schema representation of a dataset object by identifying top-level fields
 * and marking nested paths as objects without expanding them.
 */
export const createTargetSchema = (data: any): SchemaField[] => {
  const schemaMap = new Map<string, Set<string>>();

  const processField = (key: string, value: any) => {
    // Split the key to get just the top-level part
    const parts = key.split('.');
    const topLevelKey = parts[0];

    // Determine the type
    let type: string;
    if (parts.length > 1) {
      // If the key has dots, it's a nested object path
      type = 'object';
    } else {
      // Otherwise use the actual type of the value
      type = inferType(value);
    }

    // Add to schema map
    if (!schemaMap.has(topLevelKey)) {
      schemaMap.set(topLevelKey, new Set());
    }
    schemaMap.get(topLevelKey)?.add(type);
  };

  // Process each item in the dataset
  if (Array.isArray(data)) {
    data.forEach(item => {
      if (item && typeof item === 'object') {
        Object.entries(item).forEach(([key, value]) => {
          processField(key, value);
        });
      }
    });
  } else if (data && typeof data === 'object') {
    Object.entries(data).forEach(([key, value]) => {
      processField(key, value);
    });
  }

  // Convert schema map to schema fields
  return Array.from(schemaMap.entries()).map(([name, types]) => ({
    name,
    type: Array.from(types).join(' | '),
  }));
};

// Alternative implementation of createTargetSchema that accepts pre-denested data
export const createTargetSchemaFromDenested = (data: any[]): SchemaField[] => {
  const schemaMap = new Map<string, Set<string>>();

  // Process each denested data item
  data.forEach(item => {
    // Only process top-level keys
    if (item && typeof item === 'object') {
      Object.entries(item).forEach(([key, value]) => {
        if (!schemaMap.has(key)) {
          schemaMap.set(key, new Set());
        }
        schemaMap.get(key)?.add(inferType(value));
      });
    }
  });

  // Convert schema map to schema fields
  return Array.from(schemaMap.entries()).map(([name, types]) => ({
    name,
    type: Array.from(types).join(' | '),
  }));
};

/**
 * Creates a schema representation of call data (source) by only extracting
 * top-level fields under inputs and output, without deep flattening.
 */
export const createSourceSchema = (calls: CallData[]): SchemaField[] => {
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
      Object.entries(call.val.inputs).forEach(([key, value]) => {
        allFields.push({
          name: `inputs.${key}`,
          type: inferType(value),
        });
      });
    }

    const output = call.val.output;
    if (output !== undefined) {
      if (
        output !== null &&
        typeof output === 'object' &&
        !Array.isArray(output)
      ) {
        Object.entries(output).forEach(([key, value]) => {
          allFields.push({
            name: `output.${key}`,
            type: inferType(value),
          });
        });
      } else {
        allFields.push({name: 'output', type: inferType(output)});
      }
    }
  });

  return allFields
    .filter(field => !field.name.startsWith('inputs.self'))
    .reduce((acc, field) => {
      if (!acc.some(f => f.name === field.name)) {
        acc.push(field);
      }
      return acc;
    }, [] as SchemaField[]);
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
 * Recursively unwraps reference objects with __ref__ and __val__ properties
 * @param value The value to unwrap
 * @returns The unwrapped value
 */
export const unwrapRefValue = (value: any): any => {
  if (!value || typeof value !== 'object') {
    return value;
  }

  // If this is an expanded reference object, return just the __val__ part (recursively unwrapped)
  if (value.__ref__ && value.__val__) {
    return unwrapRefValue(value.__val__);
  }

  // Handle arrays
  if (Array.isArray(value)) {
    return value.map(item => unwrapRefValue(item));
  }

  // Handle objects
  const result: {[key: string]: any} = {};
  for (const key in value) {
    if (Object.prototype.hasOwnProperty.call(value, key)) {
      result[key] = unwrapRefValue(value[key]);
    }
  }
  return result;
};

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
    // Recursively unwrap references at each level
    current = unwrapRefValue(current);
    if (typeof current !== 'object') {
      return current;
    }
    current = current[part];
  }
  // Unwrap the final result as well
  return unwrapRefValue(current);
};

export const extractSourceSchema = (calls: CallData[]): SchemaField[] => {
  return createSourceSchema(calls);
};

/**
 * Maps an array of call data to dataset rows formatted for MUI DataGrid consumption.
 * This function flattens nested dictionaries in the output, creating separate entries
 * with path-based keys for each primitive value or list.
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
 * - Dictionary values will be flattened with path-based keys (e.g., "parent.child.value")
 * - Only primitive values and lists will be included as entries
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

      // Handle __ref__/__val__ pattern during value resolution using unwrapRefValue
      current = unwrapRefValue(current);

      if (typeof current !== 'object' || current === null) {
        return current;
      }

      current = current[part];
    }

    // Unwrap final value as well
    return unwrapRefValue(current);
  };

  // Helper function to flatten nested objects
  const flattenObject = (obj: any, prefix = ''): Record<string, any> => {
    const result: Record<string, any> = {};

    // Return immediately if value is null or undefined
    if (obj === null || obj === undefined) {
      return result;
    }

    // Unwrap any ref/val pattern
    obj = unwrapRefValue(obj);

    // If it's a primitive or array, just return it with the prefix
    if (typeof obj !== 'object' || Array.isArray(obj)) {
      return prefix ? {[prefix]: obj} : obj;
    }

    // Process each key in the object
    Object.keys(obj).forEach(key => {
      const value = obj[key];
      const newPrefix = prefix ? `${prefix}.${key}` : key;

      // If it's an object and not an array, recurse and merge results
      if (
        typeof value === 'object' &&
        value !== null &&
        !Array.isArray(value)
      ) {
        Object.assign(result, flattenObject(value, newPrefix));
      } else {
        // For primitives and arrays, add directly with the constructed key
        result[newPrefix] = value;
      }
    });

    return result;
  };

  return selectedCalls.map(call => {
    const rowData: Record<string, any> = {};

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
        if (
          typeof sourceValue === 'object' &&
          sourceValue !== null &&
          !Array.isArray(sourceValue)
        ) {
          // Flatten nested objects into path-based keys
          const flattenedValues = flattenObject(sourceValue);
          Object.keys(flattenedValues).forEach(key => {
            const fullKey = `${mapping.targetField}.${key}`;
            rowData[fullKey] = flattenedValues[key];
          });
        } else {
          // For primitive values and arrays, add directly
          rowData[mapping.targetField] = sourceValue;
        }
      }
    });

    return {
      ___weave: {
        id: call.digest,
        isNew: true,
      },
      ...rowData,
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
