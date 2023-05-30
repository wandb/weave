import {isNullable, nonNullable, union} from '../helpers';
import type {Type} from '../types';
import {Nullable} from './types';

export const nullable = (type: Type, applyFn: (inType: Type) => Type): Type => {
  if (type === 'none') {
    return 'none';
  }
  if (isNullable(type)) {
    return union(['none', applyFn(nonNullable(type))]);
  }
  return applyFn(type);
};

export const nullableAsync = async (
  type: Type,
  applyFn: (inType: Type) => Promise<Type>
): Promise<Type> => {
  if (type === 'none') {
    return 'none';
  }
  if (isNullable(type)) {
    return union(['none', await applyFn(nonNullable(type))]);
  }
  return applyFn(type);
};

export const nullableStrip = (type: Type): Type => {
  if (type === 'none') {
    return 'none';
  }
  if (isNullable(type)) {
    return nonNullable(type);
  }
  return type;
};

export const nullableVal = <T, R>(
  val: Nullable<T>,
  applyFn: (inVal: T) => R
): Nullable<R> => {
  if (val == null) {
    return null;
  }
  return applyFn(val);
};

export const nullableValAsync = async <T, R>(
  val: Nullable<T>,
  applyFn: (inVal: T) => Promise<Nullable<R>>
): Promise<Nullable<R>> => {
  if (val == null) {
    return null;
  }
  return applyFn(val);
};

// Remove the nullable modifier
export const skipNullable = (
  type: Type,
  applyFn: (inType: Type) => Type
): Type => {
  if (type === 'none') {
    return 'none';
  }
  if (isNullable(type)) {
    return applyFn(nonNullable(type));
  }
  return applyFn(type);
};

export const skipNullableAsync = async (
  type: Type,
  applyFn: (inType: Type) => Promise<Type>
): Promise<Type> => {
  if (type === 'none') {
    return 'none';
  }
  if (isNullable(type)) {
    return applyFn(nonNullable(type));
  }
  return applyFn(type);
};
