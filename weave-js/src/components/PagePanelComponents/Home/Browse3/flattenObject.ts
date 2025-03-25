/**
 * Flatten an object, but preserve any object that has a `_type` field.
 * This is critical for handling "Weave Types" - payloads that should be
 * treated as holistic objects, rather than flattened.
 */
export const flattenObjectPreservingWeaveTypes = (obj: {
  [key: string]: any;
}) => {
  return flattenObject(obj, '', {}, (key, value) => {
    // If the object is a Weave type, keep it intact
    if (
      typeof value === 'object' &&
      value != null &&
      value._type === 'CustomWeaveType'
    ) {
      return false;
    }

    // If this is a feedback object (has wandb.reaction.* or wandb.note.* keys), keep it intact
    if (typeof value === 'object' && value != null) {
      // Check if this object has feedback keys (wandb.reaction.* or wandb.note.*)
      const hasFeedbackKeys = Object.keys(value).some(k =>
        k.match(/^wandb\.(reaction|note)\.\d+$/)
      );

      if (hasFeedbackKeys) {
        return false; // Don't flatten this object
      }
    }

    return true;
  });
};

const flattenObject = (
  obj: {[key: string]: any},
  parentKey: string = '',
  result: {[key: string]: any} = {},
  shouldFlatten: (key: string, value: any) => boolean = () => true
) => {
  if (
    typeof obj !== 'object' ||
    obj === null ||
    !shouldFlatten(parentKey, obj)
  ) {
    return obj;
  }
  const keys = Object.keys(obj);
  keys.forEach(key => {
    if (!obj.hasOwnProperty(key)) {
      return;
    }
    const newKey = parentKey ? `${parentKey}.${key}` : key;
    if (Array.isArray(obj[key])) {
      result[newKey] = obj[key];
    } else if (
      typeof obj[key] === 'object' &&
      shouldFlatten(newKey, obj[key])
    ) {
      flattenObject(obj[key], newKey, result, shouldFlatten);
    } else {
      result[newKey] = obj[key];
    }
  });
  return result;
};
