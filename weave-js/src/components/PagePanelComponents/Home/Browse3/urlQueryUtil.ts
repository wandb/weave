/**
 * Utility methods for updating URL query parameters.
 *
 * TODO: Optional parameter to control replace vs. push?
 */
import {History} from 'history';

export function queryGetString(
  history: History,
  key: string,
  defaultValue?: string
): string | null {
  const {search} = history.location;
  const params = new URLSearchParams(search);
  return params.get(key) ?? defaultValue ?? null;
}

export function querySetString(history: History, key: string, value: string) {
  const {search} = history.location;
  const params = new URLSearchParams(search);
  params.set(key, value);
  history.replace({
    search: params.toString(),
  });
}

export const queryToggleString = (
  history: History,
  key: string,
  value: string
) => {
  const currentValue = queryGetString(history, key);
  const {search} = history.location;
  const params = new URLSearchParams(search);
  if (currentValue === value) {
    params.delete(key);
  } else {
    params.set(key, value);
  }
  history.replace({
    search: params.toString(),
  });
};

export function queryGetBoolean(
  history: History,
  key: string,
  defaultValue: boolean
): boolean {
  const {search} = history.location;
  const params = new URLSearchParams(search);
  const currentValue = params.get(key);
  if (currentValue === null) {
    return defaultValue;
  }
  return currentValue === '1';
}

export const querySetBoolean = (
  history: History,
  key: string,
  value: boolean
) => {
  const {search} = history.location;
  const params = new URLSearchParams(search);
  params.set(key, value ? '1' : '0');
  history.replace({
    search: params.toString(),
  });
};

export const queryToggleBoolean = (
  history: History,
  key: string,
  defaultValue: boolean
) => {
  const currentValue = queryGetBoolean(history, key, defaultValue);
  const {search} = history.location;
  const params = new URLSearchParams(search);
  if (currentValue) {
    params.set(key, '0');
  } else {
    params.set(key, '1');
  }
  history.replace({
    search: params.toString(),
  });
};

export const querySetArray = (history: History, key: string, value: any[]) => {
  const {search} = history.location;
  const params = new URLSearchParams(search);
  searchParamsSetArray(params, key, value);
  history.replace({
    search: params.toString(),
  });
};

export const searchParamsSetArray = (
  params: URLSearchParams,
  key: string,
  value: any[]
) => {
  params.delete(key);
  value.forEach(item => {
    params.append(key, String(item));
  });
};

export const queryGetDict = (history: History): Record<string, any> => {
  const {search} = history.location;
  const searchParams = new URLSearchParams(search);
  const params: Record<string, any> = {};
  searchParams.forEach((value, key) => {
    if (params[key]) {
      // If the key already exists, convert the existing value to an array (if it isn't already)
      // and push the new value into the array
      if (Array.isArray(params[key])) {
        params[key].push(value);
      } else {
        params[key] = [params[key], value];
      }
    } else {
      // If the key doesn't exist, add it to the dictionary
      params[key] = value;
    }
  });
  return params;
};

export const getParamArray = (
  d: Record<string, any>,
  key: string,
  defaultValue: any[] = []
): any[] => {
  if (d[key] === undefined) {
    return defaultValue;
  }
  if (Array.isArray(d[key])) {
    return d[key];
  }
  return [d[key]];
};
