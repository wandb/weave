import {get} from 'lodash';
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

export const suggestMappings = (
  sourceSchema: SchemaField[],
  targetSchema: SchemaField[],
  existingMappings: FieldMapping[]
): FieldMapping[] => {
  const sourceNames = new Set(sourceSchema.map(s => s.name));
  const targetNames = new Set(targetSchema.map(t => t.name));

  // Filter existing valid mappings
  const filtered = existingMappings.filter(m => targetNames.has(m.targetField));

  if (filtered.length > 0) {
    return filtered;
  }

  const suggested: FieldMapping[] = [];
  const remainingTargets = [...targetSchema];

  // Exact matches
  targetSchema.forEach(target => {
    if (sourceNames.has(target.name)) {
      suggested.push({sourceField: target.name, targetField: target.name});
      remainingTargets.splice(remainingTargets.indexOf(target), 1);
    }
  });

  // Inputs.* matches
  remainingTargets.forEach(target => {
    const inputField = `inputs.${target.name}`;
    if (sourceNames.has(inputField)) {
      suggested.push({sourceField: inputField, targetField: target.name});
      remainingTargets.splice(remainingTargets.indexOf(target), 1);
    }
  });

  // Output fallback
  if (sourceNames.has('output') && remainingTargets.length > 0) {
    remainingTargets.forEach(target => {
      suggested.push({sourceField: 'output', targetField: target.name});
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
  return selectedCalls.map(call => {
    const row: Record<string, any> = {};

    fieldMappings.forEach(mapping => {
      const inputs = call.val.inputs || {};
      const output = call.val.output;

      let sourceValue: any;
      if (mapping.sourceField === 'output' && typeof output === 'string') {
        sourceValue = output;
      } else {
        sourceValue = get({inputs, output}, mapping.sourceField);
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
