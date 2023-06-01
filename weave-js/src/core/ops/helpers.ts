import type {Type} from '../model';
import {mappableNullableTaggable, mappableNullableTaggableVal} from '../model';

export const standardOpType = (type: Type, applyFn: (inType: Type) => Type) => {
  return mappableNullableTaggable(type, applyFn);
};

export const standardOpValue = (val: any, applyFn: (inVal: any) => any) => {
  return mappableNullableTaggableVal(val, applyFn);
};
