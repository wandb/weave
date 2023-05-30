import * as _ from 'lodash';

import * as TypeHelpers from '../helpers';
import * as Types from '../types';

export const mappable = (
  type: Types.Type,
  applyFn: (inType: Types.Type) => Types.Type
): Types.Type => {
  if (TypeHelpers.isList(type)) {
    return TypeHelpers.list(
      applyFn(TypeHelpers.listObjectType(type)),
      type.minLength,
      type.maxLength
    );
  }
  return applyFn(type);
};

export const mappableAsync = async (
  type: Types.Type,
  applyFn: (inType: Types.Type) => Promise<Types.Type>
): Promise<Types.Type> => {
  if (TypeHelpers.isList(type)) {
    return TypeHelpers.list(
      await applyFn(TypeHelpers.listObjectType(type)),
      type.minLength,
      type.maxLength
    );
  }
  return applyFn(type);
};

export const mappableStrip = (type: Types.Type): Types.Type => {
  if (TypeHelpers.isList(type)) {
    return TypeHelpers.listObjectType(type);
  }
  return type;
};

export const mappableVal = (v: any, applyFn: (v: any) => any): any => {
  if (_.isArray(v)) {
    return v.map(t => applyFn(t));
  }
  return applyFn(v);
};

export const mappableValAsync = (
  v: any,
  applyFn: (
    v: any,
    didMap: boolean,
    mapIndex: number | undefined
  ) => Promise<any>
): Promise<any> => {
  if (_.isArray(v)) {
    return Promise.all(v.map((t, i) => applyFn(t, true, i)));
  }
  return applyFn(v, false, undefined);
};
