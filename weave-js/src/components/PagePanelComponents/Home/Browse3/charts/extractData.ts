import {parseRefMaybe} from '@wandb/weave/react';

import {CallSchema} from '../pages/wfReactInterface/wfDataModelHooksInterface';

export type ChartAxisField = {
  key: string;
  label: string;
  type: 'number' | 'string' | 'date' | 'boolean';
  units?: string;
  render?: (value: any) => string;
};

// Types for schema extraction from inputs/outputs
export type FieldType =
  | 'string'
  | 'number'
  | 'boolean'
  | 'object'
  | 'array'
  | 'null'
  | 'undefined';

export type FieldSchema = {
  key: string;
  types: Set<FieldType>;
  label: string;
  source: 'input' | 'output';
  fullPath: string; // For nested objects, e.g., "input.message", "output.response.text"
};

export type InputOutputSchema = {
  inputFields: Map<string, FieldSchema>;
  outputFields: Map<string, FieldSchema>;
};

export const chartAxisFields: ChartAxisField[] = [
  {
    key: 'started_at',
    label: 'Start Time',
    type: 'date',
    render: v => new Date(v).toLocaleString(),
  },
  {
    key: 'ended_at',
    label: 'End Time',
    type: 'date',
    render: v => (v ? new Date(v).toLocaleString() : ''),
  },
  {
    key: 'latency',
    label: 'Latency',
    type: 'number',
    units: 'ms',
    render: v => `${v} ms`,
  },
  {
    key: 'exception',
    label: 'Exception',
    type: 'string',
  },
  {
    key: 'op_name',
    label: 'Operation Name',
    type: 'string',
  },
  {
    key: 'display_name',
    label: 'Display Name',
    type: 'string',
  },
  {
    key: 'cost',
    label: 'Cost',
    type: 'number',
    units: 'USD',
  },
  {
    key: 'prompt_tokens',
    label: 'Prompt Tokens',
    type: 'number',
  },
  {
    key: 'completion_tokens',
    label: 'Completion Tokens',
    type: 'number',
  },
  {
    key: 'prompt_cost',
    label: 'Prompt Cost',
    type: 'number',
    units: 'USD',
  },
  {
    key: 'completion_cost',
    label: 'Completion Cost',
    type: 'number',
    units: 'USD',
  },
];

export const xAxisFields: ChartAxisField[] = chartAxisFields.filter(
  f => f.key === 'started_at'
);
export const yAxisFields: ChartAxisField[] = chartAxisFields.filter(
  f =>
    f.key !== 'started_at' &&
    f.key !== 'display_name' &&
    f.key !== 'op_name' &&
    f.key !== 'exception'
);

// For scatter plots, allow all fields for both x and y axes
export const scatterXAxisFields: ChartAxisField[] = chartAxisFields;
export const scatterYAxisFields: ChartAxisField[] = chartAxisFields;

export type ExtractedCallData = {
  callId: string;
  traceId: string;
  started_at: string;
  ended_at?: string;
  latency?: number;
  exception?: string;
  op_name?: string;
  display_name?: string;
  cost?: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  prompt_cost?: number;
  completion_cost?: number;
  // Raw inputs and outputs for accessing input/output field values
  inputs?: {[key: string]: any};
  output?: {[key: string]: any};
};

export function getValueType(value: any): FieldType {
  if (value === null) return 'null';
  if (value === undefined) return 'undefined';
  if (Array.isArray(value)) return 'array';

  const type = typeof value;
  switch (type) {
    case 'string':
      return 'string';
    case 'number':
      return 'number';
    case 'boolean':
      return 'boolean';
    case 'object':
      return 'object';
    default:
      return 'string'; // fallback for unknown types
  }
}

export function extractKeysFromObject(
  obj: any,
  source: 'input' | 'output',
  fieldsMap: Map<string, FieldSchema>
): void {
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) {
    return;
  }

  Object.keys(obj).forEach(key => {
    if (key.startsWith('_')) return; // Skip any keys that start with underscore

    const value = obj[key];
    const valueType = getValueType(value);

    // Only include string, number, and boolean fields at the top level
    if (
      valueType !== 'string' &&
      valueType !== 'number' &&
      valueType !== 'boolean'
    ) {
      return;
    }

    const fullPath = key; // Only top-level, no prefix needed
    const fieldKey = `${source}.${fullPath}`;

    if (fieldsMap.has(fieldKey)) {
      // Add to existing type set
      fieldsMap.get(fieldKey)!.types.add(valueType);
    } else {
      // Create new field schema
      fieldsMap.set(fieldKey, {
        key: fieldKey,
        types: new Set([valueType]),
        label: `${source === 'input' ? 'Input' : 'Output'}: ${fullPath}`,
        source,
        fullPath,
      });
    }
  });
}

export function extractInputOutputSchema(
  calls: CallSchema[]
): InputOutputSchema {
  const inputFields = new Map<string, FieldSchema>();
  const outputFields = new Map<string, FieldSchema>();

  calls.forEach(call => {
    const trace = call.traceCall;

    // Extract from inputs
    if (trace?.inputs) {
      extractKeysFromObject(trace.inputs, 'input', inputFields);
    }

    // Extract from output
    if (trace?.output) {
      extractKeysFromObject(trace.output, 'output', outputFields);
    }
  });

  return {
    inputFields,
    outputFields,
  };
}

export function convertSchemaToAxisFields(
  schema: InputOutputSchema
): ChartAxisField[] {
  const axisFields: ChartAxisField[] = [];

  // Convert input fields
  schema.inputFields.forEach(fieldSchema => {
    const types = Array.from(fieldSchema.types);

    // Since we only extract string, number, and boolean fields, determine the primary type
    let chartType: ChartAxisField['type'] = 'string'; // default

    if (types.includes('number')) {
      chartType = 'number';
    } else if (types.includes('boolean')) {
      chartType = 'boolean';
    } else if (types.includes('string')) {
      chartType = 'string';
    }

    axisFields.push({
      key: fieldSchema.key,
      label: fieldSchema.label,
      type: chartType,
      render: value => value?.toString() || '',
    });
  });

  // Convert output fields
  schema.outputFields.forEach(fieldSchema => {
    const types = Array.from(fieldSchema.types);

    let chartType: ChartAxisField['type'] = 'string'; // default

    if (types.includes('number')) {
      chartType = 'number';
    } else if (types.includes('boolean')) {
      chartType = 'boolean';
    } else if (types.includes('string')) {
      chartType = 'string';
    }

    axisFields.push({
      key: fieldSchema.key,
      label: fieldSchema.label,
      type: chartType,
      render: value => value?.toString() || '',
    });
  });

  return axisFields;
}

export function getInputOutputFieldValue(
  extractedData: ExtractedCallData,
  fieldKey: string
): any {
  // fieldKey format: "input.fieldName" or "output.fieldName" or "input.nested.field"
  const [source, ...pathParts] = fieldKey.split('.');
  const path = pathParts.join('.');

  let targetObject;
  if (source === 'input') {
    targetObject = extractedData.inputs;
  } else if (source === 'output') {
    targetObject = extractedData.output;
  } else {
    return undefined;
  }

  if (!targetObject) {
    return undefined;
  }

  // Navigate through nested path
  if (path.includes('.')) {
    const pathSegments = path.split('.');
    let current = targetObject;
    for (const segment of pathSegments) {
      if (current && typeof current === 'object' && segment in current) {
        current = current[segment];
      } else {
        return undefined;
      }
    }
    return current;
  } else {
    // Simple path
    return targetObject[path];
  }
}

export function extractCallData(calls: CallSchema[]): ExtractedCallData[] {
  return calls.map(call => {
    const trace = call.traceCall;
    const started_at = trace?.started_at || '';
    const ended_at = trace?.ended_at;
    const latency = call.rawSpan.summary.latency_s;
    const costs = trace?.summary?.weave?.costs;

    let cost: number = 0.0;
    let prompt_tokens: number = 0;
    let completion_tokens: number = 0;
    let prompt_cost: number = 0.0;
    let completion_cost: number = 0.0;

    if (costs) {
      Object.entries(costs).forEach(([_, value]) => {
        prompt_tokens += value?.prompt_tokens || 0;
        completion_tokens += value?.completion_tokens || 0;
        prompt_cost += value?.prompt_tokens_total_cost || 0.0;
        completion_cost += value?.completion_tokens_total_cost || 0.0;
        cost += prompt_cost + completion_cost;
      });
    }

    return {
      callId: call.callId,
      traceId: call.traceId,
      started_at,
      ended_at,
      latency,
      exception: trace?.exception,
      op_name: trace?.op_name,
      display_name: trace?.display_name,
      cost,
      prompt_tokens,
      completion_tokens,
      prompt_cost,
      completion_cost,
      inputs: call.rawSpan.inputs,
      output: call.rawSpan.output as {[key: string]: any} | undefined,
    };
  });
}

export function getOpNameDisplay(opName?: string): string {
  if (!opName) return '';
  const parsed = parseRefMaybe(opName);
  if (
    parsed &&
    typeof parsed === 'object' &&
    'artifactName' in parsed &&
    parsed.artifactName
  ) {
    return parsed.artifactName;
  }
  // fallback: just show the string
  return opName;
}

export function extractInputOutputSchemaFromExtractedData(
  extractedCalls: ExtractedCallData[]
): InputOutputSchema {
  const inputFields = new Map<string, FieldSchema>();
  const outputFields = new Map<string, FieldSchema>();

  extractedCalls.forEach(call => {
    // Extract from inputs
    if (call.inputs) {
      extractKeysFromObject(call.inputs, 'input', inputFields);
    }

    // Extract from output
    if (call.output) {
      extractKeysFromObject(call.output, 'output', outputFields);
    }
  });

  return {
    inputFields,
    outputFields,
  };
}

// Enhanced axis field functions that include input/output fields
export function getXAxisFields(
  extractedCalls?: ExtractedCallData[]
): ChartAxisField[] {
  const baseFields = [...xAxisFields];

  if (extractedCalls && extractedCalls.length > 0) {
    const schema = extractInputOutputSchemaFromExtractedData(extractedCalls);
    const inputOutputFields = convertSchemaToAxisFields(schema);

    // Only include numerical fields for x-axis (non-scatter plots typically use time-based x-axis)
    const numericalInputOutputFields = inputOutputFields.filter(
      field => field.type === 'number'
    );

    baseFields.push(...numericalInputOutputFields);
  }

  return baseFields;
}

export function getYAxisFields(
  extractedCalls?: ExtractedCallData[]
): ChartAxisField[] {
  const baseFields = [...yAxisFields];

  if (extractedCalls && extractedCalls.length > 0) {
    const schema = extractInputOutputSchemaFromExtractedData(extractedCalls);
    const inputOutputFields = convertSchemaToAxisFields(schema);

    // Include numerical fields for y-axis
    const numericalInputOutputFields = inputOutputFields.filter(
      field => field.type === 'number'
    );

    baseFields.push(...numericalInputOutputFields);
  }

  return baseFields;
}

export function getScatterXAxisFields(
  extractedCalls?: ExtractedCallData[]
): ChartAxisField[] {
  const baseFields = [...scatterXAxisFields];

  if (extractedCalls && extractedCalls.length > 0) {
    const schema = extractInputOutputSchemaFromExtractedData(extractedCalls);
    const inputOutputFields = convertSchemaToAxisFields(schema);

    // Include numerical fields for scatter plot x-axis
    const numericalInputOutputFields = inputOutputFields.filter(
      field => field.type === 'number'
    );

    baseFields.push(...numericalInputOutputFields);
  }

  return baseFields;
}

export function getScatterYAxisFields(
  extractedCalls?: ExtractedCallData[]
): ChartAxisField[] {
  const baseFields = [...scatterYAxisFields];

  if (extractedCalls && extractedCalls.length > 0) {
    const schema = extractInputOutputSchemaFromExtractedData(extractedCalls);
    const inputOutputFields = convertSchemaToAxisFields(schema);

    // Include numerical fields for scatter plot y-axis
    const numericalInputOutputFields = inputOutputFields.filter(
      field => field.type === 'number'
    );

    baseFields.push(...numericalInputOutputFields);
  }

  return baseFields;
}
