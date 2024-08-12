export const flattenObject = (
  obj: {[key: string]: any},
  parentKey: string = '',
  result: {[key: string]: any} = {},
  shouldFlatten: (key: string, value: any) => boolean = () => true
) => {
  if (typeof obj !== 'object' || obj === null) {
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
    } else if (typeof obj[key] === 'object' && shouldFlatten(key, obj[key])) {
      flattenObject(obj[key], newKey, result, shouldFlatten);
    } else {
      result[newKey] = obj[key];
    }
  });
  return result;
};

export const flattenObjectTypeAware = (
  obj: {[key: string]: any},
  parentKey: string = '',
  result: {[key: string]: any} = {}
) => {
  return flattenObject(obj, parentKey, result, (key, value) => {
    return typeof value !== 'object' || value == null || value['_type'] == null;
  });
};

export const unflattenObject = (obj: {[key: string]: any}) => {
  const result: {[key: string]: any} = {};
  for (const key in obj) {
    if (!obj.hasOwnProperty(key)) {
      continue;
    }
    const keys = key.split('.');
    let current = result;
    for (let i = 0; i < keys.length; i++) {
      const k = keys[i];
      if (i === keys.length - 1) {
        current[k] = obj[key];
      } else {
        current[k] = current[k] || {};
      }
      current = current[k];
    }
  }
  return result;
};
