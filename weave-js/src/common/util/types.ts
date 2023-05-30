import {
  Dispatch,
  ForwardRefExoticComponent,
  PropsWithoutRef,
  RefAttributes,
  SetStateAction,
} from 'react';

export type Nullable<T> = T | null | undefined;

export type ValueOf<T> = T[keyof T];

export type Struct<V = any> = Record<string, V>;

export type SetState<T> = Dispatch<SetStateAction<T>>;

export type FCWithRef<P, T> = ForwardRefExoticComponent<
  PropsWithoutRef<P> & RefAttributes<T>
>;

export function isNotNullOrUndefined<T>(v: T | null | undefined): v is T {
  return v != null;
}

export function isNotNullUndefinedOrFalse<T>(
  v: T | null | undefined | false
): v is T {
  return isNotNullOrUndefined(v) && v !== false;
}

export function isTruthy<T>(v: T | null | undefined): v is T {
  return !!v;
}

export function assertUnreachable(x: never): never {
  throw new Error('unreachable code');
}
