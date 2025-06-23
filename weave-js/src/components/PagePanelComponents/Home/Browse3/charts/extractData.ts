/**
 * This file contains functions used for extracting data from the calls
 * into the ExtractedCallData type.
 */
import {isWeaveObjectRef, parseRefMaybe} from '@wandb/weave/react';

import {CallSchema} from '../pages/wfReactInterface/wfDataModelHooksInterface';
import {
  ChartAxisField,
  ExtractedCallData,
  FieldSchema,
  FieldType,
  InputOutputSchema,
} from './types';

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
    type: 'number',
    render: v => (v === 1 ? 'Error' : 'Success'),
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
  // Cost fields - only USD costs are aggregated to prevent mixing currencies
  {
    key: 'cost',
    label: 'Cost (USD)',
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
    label: 'Prompt Cost (USD)',
    type: 'number',
    units: 'USD',
  },
  {
    key: 'completion_cost',
    label: 'Completion Cost (USD)',
    type: 'number',
    units: 'USD',
  },
  {
    key: 'prediction_index',
    label: 'Prediction Index',
    type: 'number',
    render: v => `${v}`,
  },
];

export const xAxisFields: ChartAxisField[] = chartAxisFields.filter(
  f => f.key === 'started_at'
);
export const yAxisFields: ChartAxisField[] = chartAxisFields.filter(
  f => f.key !== 'started_at' && f.key !== 'display_name' && f.key !== 'op_name'
);

// For scatter plots, allow all fields for both x and y axes
export const scatterXAxisFields: ChartAxisField[] = chartAxisFields;
export const scatterYAxisFields: ChartAxisField[] = chartAxisFields;

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
  fieldsMap: Map<string, FieldSchema>,
  pathPrefix: string = '',
  maxDepth: number = 5
): void {
  if (!obj || typeof obj !== 'object' || Array.isArray(obj) || maxDepth <= 0) {
    return;
  }

  Object.keys(obj).forEach(key => {
    if (key.startsWith('_')) return; // Skip any keys that start with underscore

    const value = obj[key];
    const valueType = getValueType(value);
    const currentPath = pathPrefix ? `${pathPrefix}.${key}` : key;

    // If it's a primitive type (string, number, boolean), add it to the fields
    if (
      valueType === 'string' ||
      valueType === 'number' ||
      valueType === 'boolean'
    ) {
      const fieldKey = `${source}.${currentPath}`;

      if (fieldsMap.has(fieldKey)) {
        // Add to existing type set
        fieldsMap.get(fieldKey)!.types.add(valueType);
      } else {
        // Create new field schema
        fieldsMap.set(fieldKey, {
          key: fieldKey,
          types: new Set([valueType]),
          label: `${source === 'input' ? 'Input' : 'Output'}: ${currentPath}`,
          source,
          fullPath: currentPath,
        });
      }
    }
    // If it's an object (not null or array), recursively traverse it
    else if (valueType === 'object' && value !== null) {
      extractKeysFromObject(
        value,
        source,
        fieldsMap,
        currentPath,
        maxDepth - 1
      );
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
  const pathSegments = path.split('.');
  let current = targetObject;
  for (const segment of pathSegments) {
    if (
      current &&
      typeof current === 'object' &&
      !Array.isArray(current) &&
      segment in current
    ) {
      current = current[segment];
    } else {
      return undefined;
    }
  }
  return current;
}

export function extractCallData(calls: CallSchema[]): ExtractedCallData[] {
  return calls.map(call => {
    const trace = call.traceCall;
    const started_at = trace?.started_at || '';
    const ended_at = trace?.ended_at;
    const latency = call.rawSpan.summary.latency_s;
    const costs = trace?.summary?.weave?.costs;

    let cost: number | undefined = undefined;
    let prompt_tokens: number | undefined = undefined;
    let completion_tokens: number | undefined = undefined;
    let prompt_cost: number | undefined = undefined;
    let completion_cost: number | undefined = undefined;

    if (costs && Object.keys(costs).length > 0) {
      const encounteredCurrencies = new Set<string>();
      let totalPromptTokens = 0;
      let totalCompletionTokens = 0;
      let totalPromptCost = 0.0;
      let totalCompletionCost = 0.0;
      let hasCostData = false;
      let hasTokenData = false;

      Object.entries(costs).forEach(([_, value]) => {
        const promptTokenCount = value?.prompt_tokens || 0;
        const completionTokenCount = value?.completion_tokens || 0;

        if (promptTokenCount > 0 || completionTokenCount > 0) {
          hasTokenData = true;
        }

        totalPromptTokens += promptTokenCount;
        totalCompletionTokens += completionTokenCount;

        // Track currency units for cost aggregation
        const promptCostUnit = value?.prompt_token_cost_unit;
        const completionCostUnit = value?.completion_token_cost_unit;

        if (promptCostUnit) {
          encounteredCurrencies.add(promptCostUnit);
        }
        if (completionCostUnit) {
          encounteredCurrencies.add(completionCostUnit);
        }

        // Only aggregate costs if they're in USD or if no currency is specified (assume USD)
        // This prevents mixing different currencies which would be meaningless
        const promptCostToAdd = value?.prompt_tokens_total_cost || 0.0;
        const completionCostToAdd = value?.completion_tokens_total_cost || 0.0;

        if (promptCostToAdd > 0 || completionCostToAdd > 0) {
          hasCostData = true;
        }

        if (!promptCostUnit || promptCostUnit === 'USD') {
          totalPromptCost += promptCostToAdd;
        } else {
          console.warn(
            `Skipping prompt cost in non-USD currency: ${promptCostUnit}`
          );
        }

        if (!completionCostUnit || completionCostUnit === 'USD') {
          totalCompletionCost += completionCostToAdd;
        } else {
          console.warn(
            `Skipping completion cost in non-USD currency: ${completionCostUnit}`
          );
        }
      });

      // Only set values if we actually found data
      if (hasTokenData) {
        prompt_tokens = totalPromptTokens;
        completion_tokens = totalCompletionTokens;
      }

      if (hasCostData) {
        prompt_cost = totalPromptCost;
        completion_cost = totalCompletionCost;

        // Only set total cost if we have costs in USD or unspecified currency
        // If we encounter mixed currencies, we've logged warnings above
        if (
          encounteredCurrencies.size <= 1 &&
          (encounteredCurrencies.size === 0 || encounteredCurrencies.has('USD'))
        ) {
          cost = totalPromptCost + totalCompletionCost;
        } else if (encounteredCurrencies.size > 1) {
          console.warn(
            `Mixed currency units detected in costs: ${Array.from(
              encounteredCurrencies
            ).join(', ')}. Total cost calculation may be inaccurate.`
          );
          // Still calculate total but with warning
          cost = totalPromptCost + totalCompletionCost;
        }
      }
    }

    return {
      callId: call.callId,
      traceId: call.traceId,
      started_at,
      ended_at,
      latency,
      exception: trace?.exception ? 1 : 0,
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

  // Try to parse as a reference
  const parsed = parseRefMaybe(opName);
  if (parsed && typeof parsed === 'object') {
    // Handle weave object references specifically
    if (isWeaveObjectRef(parsed)) {
      // For different weave kinds, return appropriate display names
      switch (parsed.weaveKind) {
        case 'object':
        case 'op':
          // For objects and ops, use the artifact name if available
          if (parsed.artifactName) {
            return parsed.artifactName;
          }
          break;
        case 'table':
          // For tables, show a more descriptive name since artifactName might be empty
          if (parsed.artifactName) {
            return parsed.artifactName;
          }
          // For tables without names, show table + version/digest
          return `table:${parsed.artifactVersion.slice(0, 8)}`;
        case 'call':
          // For calls, use the artifact name (call ID) in a more readable format
          if (parsed.artifactName) {
            // Show a shortened version of the call ID
            return `call:${parsed.artifactName.slice(0, 8)}`;
          }
          break;
      }

      // Fallback: if no specific handling, use artifact name or show a generic label
      if (parsed.artifactName) {
        return parsed.artifactName;
      }

      // Last resort: show the kind and a short identifier
      return `${parsed.weaveKind}:${
        parsed.artifactVersion?.slice(0, 8) || 'unknown'
      }`;
    }

    // Handle other types of references (wandb-artifact, local-artifact)
    if ('artifactName' in parsed && parsed.artifactName) {
      return parsed.artifactName;
    }
  }

  // If it's not a parseable reference, check if it looks like a weave URL and extract a name
  if (opName.startsWith('weave:///')) {
    // Extract the last meaningful part from the URL path as a fallback
    const urlParts = opName.split('/');
    // Find the last non-empty part that isn't a hash or query
    for (let i = urlParts.length - 1; i >= 0; i--) {
      const part = urlParts[i];
      if (part && !part.includes('#') && !part.includes('?')) {
        // If it contains a colon (like "name:version"), extract the name part
        if (part.includes(':')) {
          const namePart = part.split(':')[0];
          if (namePart) {
            return namePart;
          }
        }
        return part;
      }
    }
  }

  // Fallback: return the original string (for non-URL op names)
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

    // Include all types for scatter plot x-axis (numerical, string, boolean)
    baseFields.push(...inputOutputFields);
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

// Function to get all fields that can be used for grouping/coloring (legacy - use getCategoricalGroupingFields for better filtering)
export function getGroupingFields(
  extractedCalls?: ExtractedCallData[]
): ChartAxisField[] {
  const baseFields = chartAxisFields.filter(
    field => field.type === 'string' || field.type === 'boolean'
  );

  if (extractedCalls && extractedCalls.length > 0) {
    const schema = extractInputOutputSchemaFromExtractedData(extractedCalls);
    const inputOutputFields = convertSchemaToAxisFields(schema);

    // Include string and boolean fields for grouping/coloring
    const categoricalInputOutputFields = inputOutputFields.filter(
      field => field.type === 'string' || field.type === 'boolean'
    );

    baseFields.push(...categoricalInputOutputFields);
  }

  return baseFields;
}

/**
 * Analyzes field values to determine if they are truly categorical.
 *
 * @param extractedCalls - The extracted call data
 * @param fieldKey - The field key to analyze (e.g., "input.model", "output.response")
 * @param maxStringLength - Maximum allowed string length for categorical strings (default: 64)
 * @param maxUniqueValues - Maximum number of unique values to consider categorical (default: 50)
 * @returns Object containing categoricality analysis results
 *
 * @example
 * analyzeFieldCategoricality(calls, "input.model") // returns { isCategorical: true, uniqueCount: 3, ... }
 * analyzeFieldCategoricality(calls, "output.full_response") // returns { isCategorical: false, ... }
 */
export function analyzeFieldCategoricality(
  extractedCalls: ExtractedCallData[],
  fieldKey: string,
  maxStringLength: number = 64,
  maxUniqueValues: number = 50
): {
  isCategorical: boolean;
  uniqueCount: number;
  hasLongStrings: boolean;
  sampleValues: any[];
  totalValues: number;
} {
  const values: any[] = [];
  const uniqueValues = new Set<string>();
  let hasLongStrings = false;

  // Extract all values for this field
  for (const call of extractedCalls) {
    const value = getInputOutputFieldValue(call, fieldKey);
    if (value !== undefined && value !== null) {
      values.push(value);
      const stringValue = String(value);

      // Check if any string values are too long
      if (stringValue.length > maxStringLength) {
        hasLongStrings = true;
      }

      // Track unique values (convert to string for comparison)
      uniqueValues.add(stringValue);
    }
  }

  const uniqueCount = uniqueValues.size;
  const totalValues = values.length;

  // Determine if the field is categorical
  const isCategorical =
    totalValues > 0 && // Has data
    !hasLongStrings && // No overly long strings
    uniqueCount <= maxUniqueValues && // Not too many unique values
    uniqueCount > 1 && // Has some variety (more than 1 unique value)
    uniqueCount < totalValues * 0.8; // Not mostly unique values (80% threshold)

  return {
    isCategorical,
    uniqueCount,
    hasLongStrings,
    sampleValues: Array.from(uniqueValues).slice(0, 5), // First 5 unique values as samples
    totalValues,
  };
}

/**
 * Filters input/output fields to only include categorical string fields.
 *
 * @param extractedCalls - The extracted call data
 * @param maxStringLength - Maximum allowed string length for categorical strings (default: 64)
 * @param maxUniqueValues - Maximum number of unique values to consider categorical (default: 50)
 * @returns Array of categorical string chart axis fields
 *
 * @example
 * getCategoricalGroupingFields(calls) // returns only categorical string fields
 */
export function getCategoricalGroupingFields(
  extractedCalls?: ExtractedCallData[],
  maxStringLength: number = 64,
  maxUniqueValues: number = 50
): ChartAxisField[] {
  const baseFields = chartAxisFields.filter(field => field.type === 'string');

  if (!extractedCalls || extractedCalls.length === 0) {
    return baseFields;
  }

  const schema = extractInputOutputSchemaFromExtractedData(extractedCalls);
  const inputOutputFields = convertSchemaToAxisFields(schema);

  // Filter input/output fields to only include categorical string fields
  const categoricalInputOutputFields = inputOutputFields.filter(field => {
    // Only consider string fields
    if (field.type === 'string') {
      const analysis = analyzeFieldCategoricality(
        extractedCalls,
        field.key,
        maxStringLength,
        maxUniqueValues
      );
      return analysis.isCategorical;
    }

    return false;
  });

  return [...baseFields, ...categoricalInputOutputFields];
}
