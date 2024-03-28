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
