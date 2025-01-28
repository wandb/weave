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
  val: any;
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
