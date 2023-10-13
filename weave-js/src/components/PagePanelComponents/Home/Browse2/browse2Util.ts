export const flattenObject = (
  obj: {[key: string]: any},
  parentKey: string = '',
  result: {[key: string]: any} = {}
) => {
  for (const key in obj) {
    const newKey = parentKey ? `${parentKey}.${key}` : key;
    if (Array.isArray(obj[key])) {
      result[newKey] = obj[key];
    } else if (typeof obj[key] === 'object') {
      flattenObject(obj[key], newKey, result);
    } else {
      result[newKey] = obj[key];
    }
  }
  return result;
};
export const unflattenObject = (obj: {[key: string]: any}) => {
  const result: {[key: string]: any} = {};
  for (const key in obj) {
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
