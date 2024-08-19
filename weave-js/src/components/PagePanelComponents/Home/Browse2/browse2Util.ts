/**
 * Flatten an object, but preserve any object that has a `_type` field.
 * This is critical for handling "Weave Types" - payloads that should be
 * treated as holistic objects, rather than flattened.
 */
export const flattenObjectPreservingWeaveTypes = (obj: {
  [key: string]: any;
}) => {
  return flattenObject(obj, '', {}, (key, value) => {
    return (
      typeof value !== 'object' ||
      value == null ||
      value._type !== 'CustomWeaveType'
    );
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
