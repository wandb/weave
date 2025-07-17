/*
  extractData.ts

  This file contains functions used for extracting data from the calls
  into the ExtractedCallData type.

  The functions are used in the useChartData hook, which is used to process the data for the charts.
 */
import {isWeaveObjectRef, parseRefMaybe} from '@wandb/weave/react';

import {Feedback} from '../pages/wfReactInterface/traceServerClientTypes';
import {CallSchema} from '../pages/wfReactInterface/wfDataModelHooksInterface';
import {
  ChartAxisField,
  DynamicFields,
  ExtractedCallData,
  FieldSchema,
  FieldType,
  ProcessedFeedback,
} from './types';

export const chartAxisFields: ChartAxisField[] = [
  {
    key: 'started_at',
    label: 'started at',
    type: 'date',
    render: v => new Date(v as string).toLocaleString(),
  },
  {
    key: 'ended_at',
    label: 'ended at',
    type: 'date',
    render: v => (v ? new Date(v as string).toLocaleString() : ''),
  },
  {
    key: 'latency',
    label: 'latency',
    type: 'number',
    units: 'ms',
    render: v => `${v} ms`,
  },
  {
    key: 'exception',
    label: 'exception',
    type: 'number',
    render: v => (v === 1 ? 'Error' : 'Success'),
  },
  {
    key: 'op_name',
    label: 'op name',
    type: 'string',
  },
  {
    key: 'display_name',
    label: 'display name',
    type: 'string',
  },
  // Cost fields - only USD costs are aggregated to prevent mixing currencies
  {
    key: 'cost',
    label: 'cost',
    type: 'number',
    units: 'USD',
  },
  {
    key: 'prompt_tokens',
    label: 'prompt tokens',
    type: 'number',
  },
  {
    key: 'completion_tokens',
    label: 'completion tokens',
    type: 'number',
  },
  {
    key: 'prompt_cost',
    label: 'prompt cost',
    type: 'number',
    units: 'USD',
  },
  {
    key: 'completion_cost',
    label: 'completion cost',
    type: 'number',
    units: 'USD',
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

export function getValueType(value: unknown): FieldType {
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
  obj: unknown,
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

    const value = (obj as Record<string, unknown>)[key];
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

export function convertSchemaToAxisFields(
  schema: DynamicFields
): ChartAxisField[] {
  const axisFields: ChartAxisField[] = [];

  // Helper function to create axis field with proper render function
  const createAxisField = (fieldSchema: FieldSchema): ChartAxisField => {
    const types = Array.from(fieldSchema.types);
    let chartType: ChartAxisField['type'] = 'string'; // default

    if (types.includes('number')) {
      chartType = 'number';
    } else if (types.includes('boolean')) {
      chartType = 'boolean';
    } else if (types.includes('string')) {
      chartType = 'string';
    }

    // Custom render function based on type
    let renderFunc = (value: unknown) => (value as object)?.toString() || '';

    if (chartType === 'boolean') {
      renderFunc = (value: unknown) => {
        if (value === true) return 'true';
        if (value === false) return 'false';
        if (value === 1) return 'true';
        if (value === 0) return 'false';
        return (value as object)?.toString() || '';
      };
    }

    return {
      key: fieldSchema.key,
      label: fieldSchema.label,
      type: chartType,
      render: renderFunc,
    };
  };

  // Convert input fields
  schema.inputFields.forEach(fieldSchema => {
    axisFields.push(createAxisField(fieldSchema));
  });

  // Convert output fields
  schema.outputFields.forEach(fieldSchema => {
    axisFields.push(createAxisField(fieldSchema));
  });

  // Convert annotation fields
  schema.annotationFields.forEach(fieldSchema => {
    axisFields.push(createAxisField(fieldSchema));
  });

  // Convert score fields
  schema.scoreFields.forEach(fieldSchema => {
    axisFields.push(createAxisField(fieldSchema));
  });

  // Convert reaction fields
  schema.reactionFields.forEach(fieldSchema => {
    const axisField = createAxisField(fieldSchema);

    // Special handling for aggregated reactions (notes, reactions)
    if (
      fieldSchema.key === 'reactions.notes' ||
      fieldSchema.key === 'reactions.reactions'
    ) {
      axisField.render = (value: unknown) => {
        if (Array.isArray(value)) {
          return value.join(', ');
        }
        return (value as object)?.toString() || '';
      };
    }

    axisFields.push(axisField);
  });

  return axisFields;
}

export function getInputOutputFieldValue(
  extractedData: ExtractedCallData,
  fieldKey: string
): unknown {
  // Handle feedback fields
  if (
    fieldKey.startsWith('annotations.') ||
    fieldKey.startsWith('scores.') ||
    fieldKey.startsWith('reactions.')
  ) {
    return getFeedbackFieldValue(extractedData, fieldKey);
  }

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
      current = current[segment] as unknown as Record<string, unknown>;
    } else {
      return undefined;
    }
  }
  return current;
}

/**
 * Retrieves the value for a feedback field from extracted call data.
 *
 * Now works with the structured feedback format and new field prefixes.
 *
 * @param extractedData - The extracted call data containing structured feedback information
 * @param fieldKey - The field key (e.g., "annotations.Quality", "scores.toxicity", "reactions.notes")
 * @returns The feedback value, or undefined if not found
 *
 * @example
 * const callData = { feedback: { annotations: { Quality: 8.5 } } };
 * const value = getFeedbackFieldValue(callData, "annotations.Quality"); // returns 8.5
 *
 * const notesData = { feedback: { notes: ["Good", "Bad"] } };
 * const notes = getFeedbackFieldValue(notesData, "reactions.notes"); // returns ["Good", "Bad"]
 */
export function getFeedbackFieldValue(
  extractedData: ExtractedCallData,
  fieldKey: string
): unknown {
  if (!extractedData.feedback) {
    return undefined;
  }

  const feedback = extractedData.feedback;

  // Handle annotation fields: "annotations.Quality"
  if (fieldKey.startsWith('annotations.')) {
    const annotationType = fieldKey.substring('annotations.'.length);
    return feedback.annotations[annotationType];
  }

  // Handle score fields: "scores.toxicity"
  if (fieldKey.startsWith('scores.')) {
    const scorerName = fieldKey.substring('scores.'.length);
    return feedback.scorers[scorerName];
  }

  // Handle reaction fields: "reactions.notes" or "reactions.reactions"
  if (fieldKey.startsWith('reactions.')) {
    const reactionType = fieldKey.substring('reactions.'.length);

    if (reactionType === 'notes') {
      return feedback.notes.length > 0 ? feedback.notes : undefined;
    }

    if (reactionType === 'reactions') {
      return feedback.reactions.length > 0 ? feedback.reactions : undefined;
    }
  }

  return undefined;
}

/**
 * Recursively flattens a nested object, extracting numeric and boolean values with their full paths.
 *
 * @param obj - The object to flatten
 * @param prefix - The path prefix to prepend to keys
 * @param maxDepth - Maximum recursion depth to prevent infinite loops
 * @returns Flat object with dot-separated path keys and numeric/boolean values
 *
 * @example
 * flattenScorerObject({ quality: { accuracy: 0.85, metadata: { confidence: 0.78 } }, toxicity: false })
 * // Returns: { "quality.accuracy": 0.85, "quality.metadata.confidence": 0.78, "toxicity": false }
 */
function flattenScorerObject(
  obj: unknown,
  prefix: string = '',
  maxDepth: number = 5
): {[key: string]: number | boolean} {
  const result: {[key: string]: number | boolean} = {};

  if (maxDepth <= 0 || obj === null || obj === undefined) {
    return result;
  }

  if (typeof obj !== 'object') {
    // If it's a primitive value and numeric/boolean, include it
    if (typeof obj === 'number' || typeof obj === 'boolean') {
      result[prefix] = obj;
    }
    return result;
  }

  // Handle arrays by treating them as objects with numeric indices
  if (Array.isArray(obj)) {
    obj.forEach((item, index) => {
      const newPrefix = prefix ? `${prefix}.${index}` : String(index);
      Object.assign(result, flattenScorerObject(item, newPrefix, maxDepth - 1));
    });
  } else {
    // Handle regular objects
    Object.entries(obj).forEach(([key, value]) => {
      const newPrefix = prefix ? `${prefix}.${key}` : key;

      if (typeof value === 'number' || typeof value === 'boolean') {
        result[newPrefix] = value;
      } else if (typeof value === 'object' && value !== null) {
        Object.assign(
          result,
          flattenScorerObject(value, newPrefix, maxDepth - 1)
        );
      }
    });
  }

  return result;
}

/**
 * Processes raw feedback data into a structured, easy-to-use format.
 *
 * Transforms the complex API feedback dictionary into organized categories:
 * - annotations: direct annotation values by type
 * - scorers: scorer results by name (flattened for nested objects)
 * - notes: array of all note strings
 * - reactions: array of all reaction emojis
 *
 * @param rawFeedback - Raw feedback dictionary from the API
 * @returns Structured feedback data, or undefined if no feedback
 *
 * @example
 * const raw = {
 *   "wandb.annotation.Quality": { payload: { value: 8.5 } },
 *   "wandb.runnable.toxicity": { payload: { output: { quality: { accuracy: 0.85, confidence: 0.78 }, toxic: false } } },
 *   "wandb.note.1": { payload: { note: "Good result" } }
 * };
 * const processed = processFeedback(raw);
 * // Returns: {
 * //   annotations: { Quality: 8.5 },
 * //   scorers: { "toxicity.quality.accuracy": 0.85, "toxicity.quality.confidence": 0.78, "toxicity.toxic": false },
 * //   notes: ["Good result"],
 * //   reactions: []
 * // }
 */
export function processFeedback(rawFeedback?: {
  [key: string]: Feedback;
}): ProcessedFeedback | undefined {
  if (!rawFeedback || typeof rawFeedback !== 'object') {
    return undefined;
  }

  const processed: ProcessedFeedback = {
    annotations: {},
    scorers: {},
    notes: [],
    reactions: [],
  };

  let hasAnyFeedback = false;

  Object.entries(rawFeedback).forEach(([feedbackType, feedbackItem]) => {
    if (!feedbackItem || typeof feedbackItem !== 'object') {
      return;
    }

    const payload = feedbackItem.payload;
    if (!payload || typeof payload !== 'object') {
      return;
    }

    // Handle annotations: "wandb.annotation.Quality" -> annotations.Quality
    if (feedbackType.startsWith('wandb.annotation.')) {
      const annotationType = feedbackType.substring('wandb.annotation.'.length);
      const value = payload.value;

      if (value !== undefined && value !== null) {
        processed.annotations[annotationType] = value;
        hasAnyFeedback = true;
      }
    }
    // Handle scorers: "wandb.runnable.toxicity" -> scorers with flattened nested paths
    else if (feedbackType.startsWith('wandb.runnable.')) {
      const scorerName = feedbackType.substring('wandb.runnable.'.length);

      // Try to extract value from payload.output first, then payload.value
      let sourceObject: any = undefined;
      if (payload.output && typeof payload.output === 'object') {
        sourceObject = payload.output;
      } else if (payload.value !== undefined) {
        sourceObject = payload.value;
      }

      if (sourceObject !== undefined && sourceObject !== null) {
        // Flatten the scorer object to expose all numeric/boolean values with their paths
        const flattenedValues = flattenScorerObject(sourceObject, scorerName);

        // Add all flattened values to scorers
        Object.entries(flattenedValues).forEach(([path, value]) => {
          processed.scorers[path] = value;
          hasAnyFeedback = true;
        });
      }
    }
    // Handle notes: "wandb.note.1" -> notes array
    else if (feedbackType.startsWith('wandb.note.')) {
      const note = payload.note;
      if (note && typeof note === 'string') {
        processed.notes.push(note);
        hasAnyFeedback = true;
      }
    }
    // Handle reactions: "wandb.reaction.1" -> reactions array
    else if (feedbackType.startsWith('wandb.reaction.')) {
      const emoji = payload.emoji;
      if (emoji && typeof emoji === 'string') {
        processed.reactions.push(emoji);
        hasAnyFeedback = true;
      }
    }
  });
  return hasAnyFeedback ? processed : undefined;
}

export function extractCallData(calls: CallSchema[]): ExtractedCallData[] {
  return calls.map(call => {
    const trace = call.traceCall;
    const started_at = trace?.started_at || '';
    const ended_at = trace?.ended_at;
    const latency = call.rawSpan.summary.latency_s;
    const costs = trace?.summary?.weave?.costs;
    const rawFeedback = trace?.summary?.weave?.feedback;

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
        // Round to avoid floating point precision issues
        prompt_cost = Math.round(totalPromptCost * 1000000) / 1000000;
        completion_cost = Math.round(totalCompletionCost * 1000000) / 1000000;

        // Only set total cost if we have costs in USD or unspecified currency
        // If we encounter mixed currencies, we've logged warnings above
        if (
          encounteredCurrencies.size <= 1 &&
          (encounteredCurrencies.size === 0 || encounteredCurrencies.has('USD'))
        ) {
          cost =
            Math.round((totalPromptCost + totalCompletionCost) * 1000000) /
            1000000;
        } else if (encounteredCurrencies.size > 1) {
          console.warn(
            `Mixed currency units detected in costs: ${Array.from(
              encounteredCurrencies
            ).join(', ')}. Total cost calculation may be inaccurate.`
          );
          // Still calculate total but with warning
          cost =
            Math.round((totalPromptCost + totalCompletionCost) * 1000000) /
            1000000;
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
      output: call.rawSpan.output as {[key: string]: unknown} | undefined,
      feedback: processFeedback(rawFeedback),
    };
  });
}

export function getOpNameDisplay(opName?: string): string {
  if (!opName) return '';
  const parsed = parseRefMaybe(opName);
  if (parsed && typeof parsed === 'object') {
    if (isWeaveObjectRef(parsed)) {
      if (parsed.weaveKind === 'op') {
        if (parsed.artifactName) {
          return parsed.artifactName;
        }
      }
    }
  }
  return opName;
}

export function extractDynamicFields(
  extractedCalls: ExtractedCallData[]
): DynamicFields {
  const inputFields = new Map<string, FieldSchema>();
  const outputFields = new Map<string, FieldSchema>();
  const annotationFields = new Map<string, FieldSchema>();
  const scoreFields = new Map<string, FieldSchema>();
  const reactionFields = new Map<string, FieldSchema>();

  extractedCalls.forEach(call => {
    // Extract from inputs
    if (call.inputs) {
      extractKeysFromObject(call.inputs, 'input', inputFields);
    }

    // Extract from output
    if (call.output) {
      extractKeysFromObject(call.output, 'output', outputFields);
    }

    // Extract from structured feedback
    if (call.feedback) {
      // Extract annotation fields
      Object.entries(call.feedback.annotations).forEach(
        ([annotationType, value]) => {
          const fieldKey = `annotations.${annotationType}`;
          const valueType = getValueType(value);

          if (annotationFields.has(fieldKey)) {
            annotationFields.get(fieldKey)!.types.add(valueType);
          } else {
            annotationFields.set(fieldKey, {
              key: fieldKey,
              types: new Set([valueType]),
              label: annotationType,
              source: 'annotations',
              fullPath: fieldKey,
            });
          }
        }
      );

      // Extract scorer fields
      Object.entries(call.feedback.scorers).forEach(([scorerName, value]) => {
        const fieldKey = `scores.${scorerName}`;
        const valueType = getValueType(value);

        if (scoreFields.has(fieldKey)) {
          scoreFields.get(fieldKey)!.types.add(valueType);
        } else {
          scoreFields.set(fieldKey, {
            key: fieldKey,
            types: new Set([valueType]),
            label: scorerName,
            source: 'scores',
            fullPath: fieldKey,
          });
        }
      });

      // Add notes field if there are any notes
      if (call.feedback.notes.length > 0) {
        const fieldKey = 'reactions.notes';
        if (reactionFields.has(fieldKey)) {
          reactionFields.get(fieldKey)!.types.add('string');
        } else {
          reactionFields.set(fieldKey, {
            key: fieldKey,
            types: new Set(['string']),
            label: 'Notes',
            source: 'reactions',
            fullPath: fieldKey,
          });
        }
      }

      // Add reactions field if there are any reactions
      if (call.feedback.reactions.length > 0) {
        const fieldKey = 'reactions.reactions';
        if (reactionFields.has(fieldKey)) {
          reactionFields.get(fieldKey)!.types.add('string');
        } else {
          reactionFields.set(fieldKey, {
            key: fieldKey,
            types: new Set(['string']),
            label: 'Reactions',
            source: 'reactions',
            fullPath: fieldKey,
          });
        }
      }
    }
  });

  return {
    inputFields,
    outputFields,
    annotationFields,
    scoreFields,
    reactionFields,
  };
}

// Enhanced axis field functions that include input/output fields
export function getXAxisFields(
  extractedCalls?: ExtractedCallData[]
): ChartAxisField[] {
  const baseFields = [...xAxisFields];

  if (extractedCalls && extractedCalls.length > 0) {
    const schema = extractDynamicFields(extractedCalls);
    const inputOutputFields = convertSchemaToAxisFields(schema);

    // Include numerical and boolean fields for x-axis (non-scatter plots typically use time-based x-axis)
    const numericalAndBooleanFields = inputOutputFields.filter(
      field => field.type === 'number' || field.type === 'boolean'
    );

    baseFields.push(...numericalAndBooleanFields);
  }

  return baseFields;
}

export function getYAxisFields(
  extractedCalls?: ExtractedCallData[]
): ChartAxisField[] {
  const baseFields = [...yAxisFields];

  if (extractedCalls && extractedCalls.length > 0) {
    const schema = extractDynamicFields(extractedCalls);
    const inputOutputFields = convertSchemaToAxisFields(schema);

    // Include numerical and boolean fields for y-axis
    const numericalAndBooleanFields = inputOutputFields.filter(
      field => field.type === 'number' || field.type === 'boolean'
    );

    baseFields.push(...numericalAndBooleanFields);
  }

  return baseFields;
}

export function getScatterXAxisFields(
  extractedCalls?: ExtractedCallData[]
): ChartAxisField[] {
  const baseFields = [...scatterXAxisFields];

  if (extractedCalls && extractedCalls.length > 0) {
    const schema = extractDynamicFields(extractedCalls);
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
    const schema = extractDynamicFields(extractedCalls);
    const inputOutputFields = convertSchemaToAxisFields(schema);

    // Include numerical and boolean fields for scatter plot y-axis
    const numericalAndBooleanFields = inputOutputFields.filter(
      field => field.type === 'number' || field.type === 'boolean'
    );

    baseFields.push(...numericalAndBooleanFields);
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
    const schema = extractDynamicFields(extractedCalls);
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
  sampleValues: unknown[];
  totalValues: number;
} {
  const values: unknown[] = [];
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
  const baseFields = chartAxisFields.filter(
    field => field.type === 'string' || field.type === 'boolean'
  );

  if (!extractedCalls || extractedCalls.length === 0) {
    return baseFields;
  }

  const schema = extractDynamicFields(extractedCalls);
  const inputOutputFields = convertSchemaToAxisFields(schema);

  // Filter input/output fields to only include categorical string and boolean fields
  const categoricalInputOutputFields = inputOutputFields.filter(field => {
    // Include boolean fields as they are inherently categorical
    if (field.type === 'boolean') {
      // Skip feedback fields here, we'll handle them separately
      if (
        field.key.startsWith('annotations.') ||
        field.key.startsWith('scores.') ||
        field.key.startsWith('reactions.')
      ) {
        return false;
      }
      return true;
    }

    // Only consider string fields for grouping
    if (field.type === 'string') {
      // Skip feedback fields here, we'll handle them separately
      if (
        field.key.startsWith('annotations.') ||
        field.key.startsWith('scores.') ||
        field.key.startsWith('reactions.')
      ) {
        return false;
      }

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

  // Add categorical feedback fields (annotations, scores, reactions) - include both string and boolean
  const categoricalFeedbackFields = inputOutputFields.filter(field => {
    if (
      (field.key.startsWith('annotations.') ||
        field.key.startsWith('scores.') ||
        field.key.startsWith('reactions.')) &&
      (field.type === 'string' || field.type === 'boolean')
    ) {
      // For feedback fields, we'll be more lenient with categoricality
      // since they're typically controlled values
      return true;
    }
    return false;
  });

  return [
    ...baseFields,
    ...categoricalInputOutputFields,
    ...categoricalFeedbackFields,
  ];
}
