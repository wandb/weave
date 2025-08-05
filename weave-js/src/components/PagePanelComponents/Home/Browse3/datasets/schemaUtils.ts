import {TraceCallSchema} from '../pages/wfReactInterface/traceServerClientTypes';

// Field prefix constants
export const FIELD_PREFIX = {
  INPUTS: 'inputs.',
  OUTPUT: 'output.',
  ANNOTATIONS: 'annotations.',
  SCORER: 'scorer.',
  NOTES: 'notes.',
  REACTIONS: 'reactions.',
};

// Field name constants (without dots)
export const FIELD_NAME = {
  NOTES: 'notes',
  REACTIONS: 'reactions',
};

// Feedback type constants
export const FEEDBACK_TYPE = {
  ANNOTATION_PREFIX: 'wandb.annotation.',
  RUNNABLE_PREFIX: 'wandb.runnable.',
  NOTE_PREFIX: 'wandb.note.',
  REACTION_PREFIX: 'wandb.reaction.',
};

// Special object property constants
export const WEAVE_EXPANDED_REF_PROPS = {
  REF: '__ref__',
  VAL: '__val__',
};

// Common field name constants
export const FIELD_NAMES = {
  TRACE: 'trace',
  FEEDBACK_TYPE: 'feedback_type',
  PAYLOAD: 'payload',
  VALUE: 'value',
  OUTPUT: 'output',
  SUMMARY: 'summary',
  WEAVE: 'weave',
  FEEDBACK: 'feedback',
  ID: 'id',
  IS_NEW: 'isNew',
  SERVER_VALUE: 'serverValue',
  SELF: 'self',
  MODEL: 'model',
  OTEL_SPAN: 'otel_span',
};

// Weave metadata namespace
export const WEAVE_NAMESPACE = '___weave';

export interface SchemaField {
  name: string;
  type: string;
  displayName?: string;
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

// Type for feedback items to resolve TypeScript errors
interface BaseFeedbackItem {
  feedback_type: string;
  created_at?: string;
  [key: string]: any;
}

interface AnnotationFeedback extends BaseFeedbackItem {
  payload: {
    value?: any;
    [key: string]: any;
  };
}

interface NoteFeedback extends BaseFeedbackItem {
  payload: {
    note?: string;
    [key: string]: any;
  };
}

interface ReactionFeedback extends BaseFeedbackItem {
  payload: {
    emoji?: string;
    [key: string]: any;
  };
}

interface ScorerFeedback extends BaseFeedbackItem {
  payload: {
    output?: Record<string, any>;
    [key: string]: any;
  };
}

type FeedbackItem =
  | AnnotationFeedback
  | NoteFeedback
  | ReactionFeedback
  | ScorerFeedback;

// Type for weave metadata
interface WeaveMetadata {
  id: string;
  isNew: boolean;
  serverValue?: any;
  [key: string]: any;
}

// Type for a row with weave metadata
interface WeaveRow {
  [WEAVE_NAMESPACE]: WeaveMetadata;
  [key: string]: any;
}

/**
 * Creates a schema representation of call data (source) by only extracting
 * top-level fields under inputs and output, without deep flattening.
 */
export const createSourceSchema = (calls: CallData[]): SchemaField[] => {
  const allFields: SchemaField[] = [
    {
      name: FIELD_NAMES.TRACE,
      type: 'string',
    },
  ];

  if (!calls || !Array.isArray(calls)) {
    return allFields;
  }

  // Add input and output fields
  calls.forEach(call => {
    // Skip if call or call.val is undefined
    if (!call || !call.val) {
      return;
    }

    // Extract input fields
    if (call.val.inputs) {
      Object.entries(call.val.inputs).forEach(([key, value]) => {
        allFields.push({
          name: `${FIELD_PREFIX.INPUTS}${key}`,
          type: inferType(value),
        });
      });
    }

    // Extract output fields
    const output = unwrapRefValue(call.val.output);
    if (output !== undefined) {
      if (
        output !== null &&
        typeof output === 'object' &&
        !Array.isArray(output) &&
        output._type === undefined
      ) {
        Object.entries(output).forEach(([key, value]) => {
          allFields.push({
            name: `${FIELD_PREFIX.OUTPUT}${key}`,
            type: inferType(value),
          });
        });
      } else {
        allFields.push({name: FIELD_NAMES.OUTPUT, type: inferType(output)});
      }
    }

    // Extract OTEL span field from attributes.otel_span
    const attributes = call.val.attributes || {};
    const otelSpan = attributes.otel_span;

    if (otelSpan && typeof otelSpan === 'object') {
      // Add a single field for the entire OTEL span object
      allFields.push({
        name: FIELD_NAMES.OTEL_SPAN,
        type: 'object',
        displayName: 'otel span',
      });
    }

    // Extract feedback fields (annotations, notes, reactions, and runnables) from summary.weave.feedback
    const summary = call.val.summary || {};
    const weave = summary.weave || {};
    const feedback = weave.feedback;

    if (feedback) {
      if (Array.isArray(feedback)) {
        // Process each feedback item
        feedback.forEach(item => {
          const feedbackItem = item as FeedbackItem;
          if (
            typeof feedbackItem === 'object' &&
            feedbackItem !== null &&
            feedbackItem.feedback_type
          ) {
            const fieldName = getFieldNameFromFeedbackType(
              feedbackItem.feedback_type
            );

            if (fieldName) {
              // Add field to schema for all supported feedback types
              allFields.push({
                name: fieldName,
                type: inferType(feedbackItem.payload?.value),
              });
            }
          }
        });
      } else if (typeof feedback === 'object' && feedback !== null) {
        // Process object-form feedback
        Object.entries(feedback).forEach(([feedbackType, feedbackItem]) => {
          const fieldName = getFieldNameFromFeedbackType(feedbackType);

          if (
            fieldName &&
            typeof feedbackItem === 'object' &&
            feedbackItem !== null
          ) {
            const typedFeedbackItem = feedbackItem as FeedbackItem;

            // Add field to schema for all supported feedback types
            allFields.push({
              name: fieldName,
              type: inferType(typedFeedbackItem.payload?.value),
            });
          }
        });
      }
    }
  });

  return allFields
    .filter(
      field =>
        !field.name.startsWith(`${FIELD_PREFIX.INPUTS}${FIELD_NAMES.SELF}`) &&
        !field.name.startsWith(`${FIELD_PREFIX.INPUTS}${FIELD_NAMES.MODEL}`)
    )
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
  if (
    value[WEAVE_EXPANDED_REF_PROPS.REF] &&
    value[WEAVE_EXPANDED_REF_PROPS.VAL]
  ) {
    return unwrapRefValue(value[WEAVE_EXPANDED_REF_PROPS.VAL]);
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

    if (path === FIELD_NAMES.TRACE) {
      return `weave:///${obj.project_id}/call/${obj.digest}`;
    }

    // Special handling for OTEL span field
    if (path === FIELD_NAMES.OTEL_SPAN) {
      const attributes = obj.attributes || {};
      return unwrapRefValue(attributes.otel_span);
    }

    // Special handling for feedback fields (annotations, notes, reactions, and runnables)
    if (isFeedbackField(path)) {
      const summary = obj.summary || {};
      const weave = summary.weave || {};
      return getFeedbackValue(weave.feedback, path);
    }

    // Regular path resolution for non-feedback fields
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

      // If it's an object and not an array or weave object, recurse and merge results
      if (
        typeof value === 'object' &&
        value !== null &&
        !Array.isArray(value) &&
        value?._type === undefined
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
      const summary = call.val.summary || {};
      const attributes = call.val.attributes || {};

      let sourceValue: any;
      if (mapping.sourceField === FIELD_NAMES.OUTPUT) {
        // Case where output is a primitive value or array
        sourceValue = unwrapRefValue(output);
      } else {
        sourceValue = resolveValue(
          {
            inputs,
            output,
            summary,
            attributes,
            project_id: call.val.project_id,
            digest: call.digest,
          },
          mapping.sourceField
        );
      }
      if (sourceValue !== undefined) {
        if (
          typeof sourceValue === 'object' &&
          sourceValue !== null &&
          !Array.isArray(sourceValue) &&
          sourceValue._type === undefined
        ) {
          Object.entries(flattenObject(sourceValue)).forEach(([key, value]) => {
            rowData[`${mapping.targetField}.${key}`] = value;
          });
        } else {
          rowData[mapping.targetField] = sourceValue;
        }
      }
    });

    return {
      [WEAVE_NAMESPACE]: {
        id: call.digest,
        isNew: true,
      },
      ...rowData,
    } as WeaveRow;
  });
};

/**
 * Creates a map of processed rows with schema-based filtering.
 *
 * @param mappedRows - The rows mapped from calls
 * @param datasetObject - The dataset object containing schema information
 * @returns A Map of row IDs to processed row data
 */
export function createProcessedRowsMap(
  mappedRows: WeaveRow[],
  datasetObject: any
): Map<string, any> {
  return new Map(
    mappedRows
      .filter(row => row && row[WEAVE_NAMESPACE] && row[WEAVE_NAMESPACE].id)
      .map(row => {
        // If datasetObject has a schema, filter row properties to match schema fields
        if (datasetObject?.schema && Array.isArray(datasetObject.schema)) {
          const schemaFields = new Set(
            datasetObject.schema.map((f: {name: string}) => {
              // Remove inputs. or output. prefix if present
              const name = f.name;
              if (name.startsWith(FIELD_PREFIX.INPUTS)) {
                return name.slice(FIELD_PREFIX.INPUTS.length);
              }
              if (name.startsWith(FIELD_PREFIX.OUTPUT)) {
                return name.slice(FIELD_PREFIX.OUTPUT.length);
              }
              return name;
            })
          );

          const {[WEAVE_NAMESPACE]: weaveData, ...rest} = row;
          // Only include fields that are in the schema
          const filteredData = Object.fromEntries(
            Object.entries(rest).filter(([key]) =>
              Array.from(schemaFields).some(
                schemaField =>
                  key === schemaField || key.startsWith(`${schemaField}.`)
              )
            )
          );

          return [
            row[WEAVE_NAMESPACE].id,
            {
              ...filteredData,
              [WEAVE_NAMESPACE]: {...weaveData, serverValue: filteredData},
            },
          ];
        }

        // Default case - keep all fields
        return [
          row[WEAVE_NAMESPACE].id,
          {
            ...row,
            [WEAVE_NAMESPACE]: {...row[WEAVE_NAMESPACE], serverValue: row},
          },
        ];
      })
  );
}

/**
 * Removes prefixes from a field name for comparison purposes
 * @param fieldName Field name that might have prefixes
 * @returns Field name without prefixes
 */
const removeFieldPrefixes = (fieldName: string): string => {
  if (fieldName.startsWith(FIELD_PREFIX.INPUTS)) {
    return fieldName.replace(FIELD_PREFIX.INPUTS, '');
  } else if (fieldName.startsWith(FIELD_PREFIX.OUTPUT)) {
    return fieldName.replace(FIELD_PREFIX.OUTPUT, '');
  } else if (fieldName.startsWith(FIELD_PREFIX.ANNOTATIONS)) {
    return fieldName.replace(FIELD_PREFIX.ANNOTATIONS, '');
  } else if (fieldName.startsWith(FIELD_PREFIX.SCORER)) {
    return fieldName.replace(FIELD_PREFIX.SCORER, '');
  } else if (fieldName.startsWith(FIELD_PREFIX.NOTES)) {
    return fieldName.replace(FIELD_PREFIX.NOTES, '');
  } else if (fieldName.startsWith(FIELD_PREFIX.REACTIONS)) {
    return fieldName.replace(FIELD_PREFIX.REACTIONS, '');
  }
  return fieldName;
};

/**
 * Suggests field mappings between source and target schemas.
 *
 * This function attempts to match fields between schemas using various strategies:
 * 1. Preserves existing mappings if the fields still exist
 * 2. Matches fields with identical names after removing prefixes
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

    // Try to find a matching source field by exact name after removing prefixes
    const targetNameNoPrefixes = removeFieldPrefixes(targetField.name);
    const exactMatch = sourceSchema.find(sourceField => {
      const sourceNameNoPrefixes = removeFieldPrefixes(sourceField.name);
      return sourceNameNoPrefixes === targetNameNoPrefixes;
    });

    if (exactMatch) {
      newMappings.push({
        targetField: targetField.name,
        sourceField: exactMatch.name,
      });
      return;
    }

    // Try to find a matching source field by name containing the target field name
    const containsMatch = sourceSchema.find(sourceField => {
      const sourceNameNoPrefixes = removeFieldPrefixes(sourceField.name);
      return sourceNameNoPrefixes
        .toLowerCase()
        .includes(targetNameNoPrefixes.toLowerCase());
    });

    if (containsMatch) {
      newMappings.push({
        targetField: targetField.name,
        sourceField: containsMatch.name,
      });
      return;
    }

    // Try to find a matching source field where the target field name contains the source field name
    const reverseContainsMatch = sourceSchema.find(sourceField => {
      const sourceNameNoPrefixes = removeFieldPrefixes(sourceField.name);
      return targetNameNoPrefixes
        .toLowerCase()
        .includes(sourceNameNoPrefixes.toLowerCase());
    });

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

/**
 * Extracts the field name from a feedback_type string.
 * For annotations: "wandb.annotation.Quality" -> "annotations.Quality"
 * For runnables: "wandb.runnable.toxicity" -> "scorer.toxicity" (currently disabled)
 * For notes: "wandb.note.1" -> "notes" (removes numeric ID)
 * For reactions: "wandb.reaction.1" -> "reactions" (removes numeric ID)
 */
export const getFieldNameFromFeedbackType = (
  feedbackType: string
): string | null => {
  if (feedbackType.startsWith(FEEDBACK_TYPE.ANNOTATION_PREFIX)) {
    const annotationType = feedbackType.substring(
      FEEDBACK_TYPE.ANNOTATION_PREFIX.length
    );
    return `${FIELD_PREFIX.ANNOTATIONS}${annotationType}`;
  }

  if (feedbackType.startsWith(FEEDBACK_TYPE.RUNNABLE_PREFIX)) {
    // Currently returning null to disable runnable fields
    // const scorerName = feedbackType.substring(FEEDBACK_TYPE.RUNNABLE_PREFIX.length);
    // return `${FIELD_PREFIX.SCORER}${scorerName}`;
    return null;
  }

  if (feedbackType.startsWith(FEEDBACK_TYPE.NOTE_PREFIX)) {
    // For notes, we don't include the ID number in the field name
    // We just return "notes" as the field name
    return FIELD_NAME.NOTES;
  }

  if (feedbackType.startsWith(FEEDBACK_TYPE.REACTION_PREFIX)) {
    // For reactions, we don't include the ID number in the field name
    // We just return "reactions" as the field name
    return FIELD_NAME.REACTIONS;
  }

  return null;
};

/**
 * Determines if a field name might represent a feedback field (annotation or runnable).
 * Uses prefixed format: "annotations.*" for annotations, "scorer.*" for runnable scorers.
 * Also handles "notes" and "reactions" as exact field names.
 */
export const isFeedbackField = (fieldName: string): boolean => {
  // Check for annotation fields
  if (fieldName.startsWith(FIELD_PREFIX.ANNOTATIONS)) {
    return true;
  }

  // Check for scorer fields (currently disabled)
  if (fieldName.startsWith(FIELD_PREFIX.SCORER)) {
    return true;
  }

  // Check for note fields (exact match for "notes")
  if (fieldName === FIELD_NAME.NOTES) {
    return true;
  }

  // Check for reaction fields (exact match for "reactions")
  if (fieldName === FIELD_NAME.REACTIONS) {
    return true;
  }

  return false;
};

/**
 * Extract the most appropriate display value from a feedback payload.
 * This helper extracts a simple string/primitive value from various payload formats.
 */
const extractSimpleValue = (payload: any): any => {
  if (!payload) {
    return undefined;
  }

  // Try various possible locations for the content in order of preference
  if (payload.note) {
    return payload.note;
  } else if (payload.emoji) {
    return payload.emoji;
  } else if (payload.value !== undefined && typeof payload.value !== 'object') {
    return payload.value;
  } else if (
    typeof payload === 'string' ||
    typeof payload === 'number' ||
    typeof payload === 'boolean'
  ) {
    return payload;
  }
  throw new Error(
    `No simple value found in feedback payload: ${JSON.stringify(payload)}`
  );
};

/**
 * Extracts a feedback value from feedback data for a given field name.
 * Works with both array and object formats of feedback data.
 *
 * Handles different feedback types differently:
 * - Annotations: Returns the most recent annotation of each type
 * - Notes: Returns a list of all notes
 * - Reactions: Returns a list of all reactions
 */
export const getFeedbackValue = (feedback: any, fieldName: string): any => {
  if (!feedback) {
    return undefined;
  }

  // Parse prefixed field name
  let prefix: string | null = null;
  let actualName: string | null = null;

  if (fieldName.startsWith(FIELD_PREFIX.ANNOTATIONS)) {
    prefix = 'annotations';
    actualName = fieldName.substring(FIELD_PREFIX.ANNOTATIONS.length);
  } else if (fieldName.startsWith(FIELD_PREFIX.SCORER)) {
    prefix = 'scorer';
    actualName = fieldName.substring(FIELD_PREFIX.SCORER.length);
  } else if (fieldName === FIELD_NAME.NOTES) {
    prefix = 'notes';
    actualName = '';
  } else if (fieldName === FIELD_NAME.REACTIONS) {
    prefix = 'reactions';
    actualName = '';
  }

  if (!prefix) {
    return undefined;
  }

  // Convert feedback to array format if it's not already
  const feedbackArray = Array.isArray(feedback)
    ? feedback
    : Object.entries(feedback).map(([key, value]) => {
        const item = value as FeedbackItem;
        item.feedback_type = key;
        return item;
      });

  // Handle annotations - return most recent annotation for the specified type
  if (prefix === 'annotations') {
    const matchingAnnotations = feedbackArray
      .filter(
        item =>
          item &&
          typeof item === 'object' &&
          item.feedback_type ===
            `${FEEDBACK_TYPE.ANNOTATION_PREFIX}${actualName}`
      )
      .sort((a, b) => {
        // Sort by created_at date, most recent first
        const dateA = new Date(a.created_at || 0);
        const dateB = new Date(b.created_at || 0);
        return dateB.getTime() - dateA.getTime();
      });

    if (matchingAnnotations.length > 0) {
      const mostRecentAnnotation = matchingAnnotations[0];
      return extractSimpleValue(mostRecentAnnotation.payload);
    }
    return undefined;
  }

  // Handle notes - collect all notes into a list
  if (prefix === 'notes') {
    const notes = feedbackArray
      .filter(
        item =>
          item &&
          typeof item === 'object' &&
          item.feedback_type.startsWith(FEEDBACK_TYPE.NOTE_PREFIX)
      )
      .sort((a, b) => {
        // Sort by created_at date, most recent first
        const dateA = new Date(a.created_at || 0);
        const dateB = new Date(b.created_at || 0);
        return dateB.getTime() - dateA.getTime();
      })
      .map(note => extractSimpleValue(note.payload));

    if (notes.length > 0) {
      return notes;
    }
    return undefined;
  }

  // Handle reactions - collect all reactions into a list
  if (prefix === 'reactions') {
    const reactions = feedbackArray
      .filter(
        item =>
          item &&
          typeof item === 'object' &&
          item.feedback_type.startsWith(FEEDBACK_TYPE.REACTION_PREFIX)
      )
      .sort((a, b) => {
        // Sort by created_at date, most recent first
        const dateA = new Date(a.created_at || 0);
        const dateB = new Date(b.created_at || 0);
        return dateB.getTime() - dateA.getTime();
      })
      .map(reaction => extractSimpleValue(reaction.payload));

    if (reactions.length > 0) {
      return reactions;
    }
    return undefined;
  }

  // For scorer fields (handle separately from other types)
  if (prefix === 'scorer') {
    const matchingScorers = feedbackArray
      .filter(
        item =>
          item &&
          typeof item === 'object' &&
          item.feedback_type === `${FEEDBACK_TYPE.RUNNABLE_PREFIX}${actualName}`
      )
      .sort((a, b) => {
        // Sort by created_at date, most recent first
        const dateA = new Date(a.created_at || 0);
        const dateB = new Date(b.created_at || 0);
        return dateB.getTime() - dateA.getTime();
      });

    if (matchingScorers.length > 0) {
      const mostRecentScorer = matchingScorers[0];
      if (
        mostRecentScorer.payload?.output &&
        typeof mostRecentScorer.payload.output === 'object'
      ) {
        return mostRecentScorer.payload.output;
      }
      return extractSimpleValue(mostRecentScorer.payload);
    }
    return undefined;
  }

  return undefined;
};

/**
   * Generates preview data for fields across all calls
  /**
   * Generates preview data for fields across all calls
   *
   * @param sourceSchema - Schema fields to generate previews for
   * @param selectedCalls - Call data to extract values from
   * @returns A Map where keys are field names and values are arrays of records with field values
   */
export const generateFieldPreviews = (
  sourceSchema: SchemaField[],
  selectedCalls: CallData[]
): Map<string, Array<Record<string, any>>> => {
  const previews = new Map<string, Array<Record<string, any>>>();

  sourceSchema.forEach(field => {
    const fieldData = selectedCalls.map(call => {
      let value: any;

      // Handle standard input/output fields first
      if (field.name === FIELD_NAMES.OUTPUT) {
        value = unwrapRefValue(call.val.output);
      } else if (field.name === FIELD_NAMES.TRACE) {
        value = `weave:///${call.val.project_id}/call/${call.digest}`;
      } else if (field.name.startsWith(FIELD_PREFIX.INPUTS)) {
        const path = field.name.slice(FIELD_PREFIX.INPUTS.length).split('.');
        value = getNestedValue(call.val.inputs, path);
      } else if (field.name.startsWith(FIELD_PREFIX.OUTPUT)) {
        if (typeof call.val.output === 'object' && call.val.output !== null) {
          const path = field.name.slice(FIELD_PREFIX.OUTPUT.length).split('.');
          value = getNestedValue(call.val.output, path);
        } else {
          value = unwrapRefValue(call.val.output);
        }
      }
      // Special handling for feedback fields (annotations, notes, reactions, and runnables)
      else if (isFeedbackField(field.name)) {
        const summary = call.val.summary || {};
        const weave = summary.weave || {};
        value = getFeedbackValue(weave.feedback, field.name);
      }
      // Special handling for OTEL span field
      else if (field.name === FIELD_NAMES.OTEL_SPAN) {
        const attributes = call.val.attributes || {};
        value = unwrapRefValue(attributes.otel_span);
      } else {
        // General path resolution for any other fields
        const path = field.name.split('.');
        value = getNestedValue(call.val, path);
      }
      return {[field.name]: value};
    });
    previews.set(field.name, fieldData);
  });
  return previews;
};
