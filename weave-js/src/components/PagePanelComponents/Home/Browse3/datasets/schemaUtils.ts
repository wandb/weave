import {v4 as uuidv4} from 'uuid';

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

  // Special handling for __ref__ and __val__ pattern
  if (
    obj != null &&
    typeof obj === 'object' &&
    '__ref__' in obj &&
    '__val__' in obj
  ) {
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

export const extractSourceSchema = (calls: CallData[]): SchemaField[] => {
  const allFields: SchemaField[] = [];

  calls.forEach(call => {
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

  return allFields.reduce((acc, field) => {
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
 *   - id: A unique identifier prefixed with "new-"
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
        id: `new-${uuidv4()}`,
        isNew: true,
      },
      ...row,
    };
  });
};
