import {TraceCallSchema} from '../pages/wfReactInterface/traceServerClientTypes';

// Field prefix constants
export const FIELD_PREFIX = {
  INPUTS: 'inputs.',
  OUTPUT: 'output.',
  ANNOTATIONS: 'annotations.',
  SCORER: 'scorer.',
};

// Feedback type constants
export const FEEDBACK_TYPE = {
  ANNOTATION_PREFIX: 'wandb.annotation.',
  RUNNABLE_PREFIX: 'wandb.runnable.',
};

// Special object property constants
export const WEAVE_EXPANDED_REF_PROPS = {
  REF: '__ref__',
  VAL: '__val__',
};

// Common field name constants
export const FIELD_NAMES = {
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
};

// Weave metadata namespace
export const WEAVE_NAMESPACE = '___weave';

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
  if (
    typeof obj === 'object' &&
    WEAVE_EXPANDED_REF_PROPS.REF in obj &&
    WEAVE_EXPANDED_REF_PROPS.VAL in obj
  ) {
    if (
      typeof obj[WEAVE_EXPANDED_REF_PROPS.VAL] === 'object' &&
      !Array.isArray(obj[WEAVE_EXPANDED_REF_PROPS.VAL])
    ) {
      // For object values, extract its top-level fields
      return extractTopLevelFields(obj[WEAVE_EXPANDED_REF_PROPS.VAL], prefix);
    } else {
      // For primitive or array values, return as is
      return [
        {name: prefix, type: inferType(obj[WEAVE_EXPANDED_REF_PROPS.VAL])},
      ];
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

// Type for feedback items to resolve TypeScript errors
interface FeedbackItem {
  feedback_type: string;
  payload?: {
    output?: Record<string, any>;
    value?: any;
  };
  [key: string]: any;
}

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
  const allFields: SchemaField[] = [];

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
        !Array.isArray(output)
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

    // Extract feedback fields (annotations and runnables) from summary.weave.feedback
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
              // We've already filtered out runnables in getFieldNameFromFeedbackType
              // Add field to schema (only for annotations now)
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
            // We've already filtered out runnables in getFieldNameFromFeedbackType
            const typedFeedbackItem = feedbackItem as FeedbackItem;

            // Add field to schema (only for annotations now)
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
        !field.name.startsWith(`${FIELD_PREFIX.INPUTS}${FIELD_NAMES.SELF}`)
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

    // Handle the standard "output" field directly
    if (path === FIELD_NAMES.OUTPUT) {
      return unwrapRefValue(obj.output);
    }

    // Special handling for feedback fields (annotations and runnables)
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
      const summary = call.val.summary || {};

      let sourceValue: any;
      if (
        mapping.sourceField === FIELD_NAMES.OUTPUT &&
        typeof output === 'string'
      ) {
        sourceValue = output;
      } else {
        sourceValue = resolveValue(
          {inputs, output, summary},
          mapping.sourceField
        );
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
      [WEAVE_NAMESPACE]: {
        id: call.digest,
        isNew: true,
      },
      ...rowData,
    } as WeaveRow;
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
  mappedRows: WeaveRow[],
  targetFields: Set<string>
): WeaveRow[] {
  return mappedRows
    .map(row => {
      try {
        if (!row || typeof row !== 'object' || !row[WEAVE_NAMESPACE]) {
          return undefined;
        }

        const {[WEAVE_NAMESPACE]: weaveData, ...rest} = row;
        const filteredData = Object.fromEntries(
          Object.entries(rest).filter(([key]) => targetFields.has(key))
        );
        return {
          [WEAVE_NAMESPACE]: weaveData,
          ...filteredData,
        } as WeaveRow;
      } catch (rowError) {
        console.error('Error processing row:', rowError);
        return undefined;
      }
    })
    .filter((row): row is WeaveRow => row !== undefined);
}

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
            datasetObject.schema.map((f: {name: string}) => f.name)
          );
          const {[WEAVE_NAMESPACE]: weaveData, ...rest} = row;

          // Only include fields that are in the schema
          const filteredData = Object.fromEntries(
            Object.entries(rest).filter(([key]) => schemaFields.has(key))
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

  return null;
};

/**
 * Determines if a field name might represent a feedback field (annotation or runnable).
 * Uses prefixed format: "annotations.*" for annotations, "scorer.*" for runnable scorers.
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

  return false;
};

/**
 * Extracts a feedback value from feedback data for a given field name.
 * Works with both array and object formats of feedback data.
 * Handles prefixed field names: "annotations.*" for annotations, "scorer.*" for runnable scorers.
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
  }

  if (!prefix || !actualName) {
    return undefined;
  }

  // For annotation fields
  if (prefix === 'annotations') {
    // Handle array format
    if (Array.isArray(feedback)) {
      const annotationItem = feedback.find(item => {
        const feedbackItem = item as FeedbackItem;
        return (
          feedbackItem &&
          typeof feedbackItem === 'object' &&
          feedbackItem.feedback_type ===
            `${FEEDBACK_TYPE.ANNOTATION_PREFIX}${actualName}`
        );
      });

      if (annotationItem) {
        const typedItem = annotationItem as FeedbackItem;
        return typedItem.payload?.value;
      }
      return undefined;
    }

    // Handle object format (post-processed)
    if (typeof feedback === 'object' && feedback !== null) {
      const annotationKey = `${FEEDBACK_TYPE.ANNOTATION_PREFIX}${actualName}`;
      if (feedback[annotationKey]) {
        const typedItem = feedback[annotationKey] as FeedbackItem;
        return typedItem.payload?.value;
      }
    }
  }

  // For scorer fields (not currently used since we're returning null for scorers)
  if (prefix === 'scorer') {
    // Handle array format
    if (Array.isArray(feedback)) {
      const scorerItem = feedback.find(item => {
        const feedbackItem = item as FeedbackItem;
        return (
          feedbackItem &&
          typeof feedbackItem === 'object' &&
          feedbackItem.feedback_type ===
            `${FEEDBACK_TYPE.RUNNABLE_PREFIX}${actualName}`
        );
      });

      if (scorerItem) {
        const typedItem = scorerItem as FeedbackItem;
        if (
          typedItem.payload?.output &&
          typeof typedItem.payload.output === 'object'
        ) {
          return typedItem.payload.output;
        }
        return typedItem.payload?.value;
      }
      return undefined;
    }

    // Handle object format (post-processed)
    if (typeof feedback === 'object' && feedback !== null) {
      const scorerKey = `${FEEDBACK_TYPE.RUNNABLE_PREFIX}${actualName}`;
      if (feedback[scorerKey]) {
        const typedItem = feedback[scorerKey] as FeedbackItem;
        if (
          typedItem.payload?.output &&
          typeof typedItem.payload.output === 'object'
        ) {
          return typedItem.payload.output;
        }
        return typedItem.payload?.value;
      }
    }
  }

  return undefined;
};

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
      // Special handling for feedback fields (annotations and runnables)
      else if (isFeedbackField(field.name)) {
        const summary = call.val.summary || {};
        const weave = summary.weave || {};
        value = getFeedbackValue(weave.feedback, field.name);
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
