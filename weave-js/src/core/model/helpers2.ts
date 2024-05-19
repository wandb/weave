import _ from 'lodash';

import {
  isDict,
  isListLike,
  isTypedDictLike,
  listObjectType,
  objectKeyType,
  objectKeyVal,
  typedDict,
  typedDictPropertyTypes,
} from './helpers';
import {nullableTaggable, nullableTaggableVal} from './modifiers';
import {Type} from './types';

export const typedDictPathVal = (val: any, path: string[]): any => {
  const res = nullableTaggableVal(val, t => {
    if (!_.isObject(t)) {
      return null;
    }
    const key = path[0];
    if (key === '*') {
      const newObj: {[key: string]: any} = {};
      for (const subKey of Object.keys(t)) {
        newObj[subKey] = typedDictOrListPathVal(
          (t as any)[subKey],
          path.slice(1)
        );
      }
      return newObj;
    }
    const keyVal = objectKeyVal(t, path[0]);
    if (keyVal == null) {
      return null;
    }
    if (path.length > 1) {
      return typedDictOrListPathVal(keyVal, path.slice(1));
    }
    return keyVal;
  });
  return res;
};

const typedDictOrListPathVal = (val: any, path: string[]): any => {
  return nullableTaggableVal(val, t => {
    if (!_.isObject(t) && !_.isArray(t)) {
      return null;
    }
    if (_.isArray(t) && path[0] === '*') {
      if (path.length === 1) {
        return t;
      } else {
        return t.map(item => typedDictOrListPathVal(item, path.slice(1)));
      }
    } else if (_.isObject(t)) {
      return typedDictPathVal(t, path);
    } else {
      return 'none';
    }
  });
};

export const typedDictPathType = (type: Type, path: string[]): Type => {
  return nullableTaggable(type, t => {
    if (isDict(t)) {
      if (path.length === 1) {
        return t.objectType;
      }
      return typedDictPathType(t.objectType, path.slice(1));
    } else if (!isTypedDictLike(t)) {
      return 'none';
    }
    const key = path[0];
    if (key === '*') {
      const newPropertyTypes: {[key: string]: any} = {};
      for (const [subKey, subVal] of Object.entries(
        typedDictPropertyTypes(t)
      )) {
        if (subVal == null) {
          throw new Error('typedDictPathType: found null property type');
        }
        newPropertyTypes[subKey] = typedDictOrListPathType(
          subVal,
          path.slice(1)
        );
      }
      return typedDict(newPropertyTypes);
    }
    const keyType = objectKeyType(t, path[0]);
    if (path.length > 1) {
      return typedDictOrListPathType(keyType, path.slice(1));
    }
    return keyType;
  });
};

const typedDictOrListPathType = (type: Type, path: string[]): Type => {
  return nullableTaggable(type, t => {
    if (!isTypedDictLike(t) && !isListLike(t)) {
      return 'none';
    }
    if (isTypedDictLike(t)) {
      return typedDictPathType(t, path);
    } else if (isListLike(t) && path[0] === '*') {
      const objType = listObjectType(t);
      if (path.length === 1) {
        return {
          type: 'list',
          objectType: objType,
          maxLength: t.maxLength ?? undefined,
          minLength: t.minLength ?? undefined,
        };
      } else {
        return {
          type: 'list',
          objectType: typedDictOrListPathType(objType, path.slice(1)),
          maxLength: t.maxLength ?? undefined,
          minLength: t.minLength ?? undefined,
        };
      }
    } else {
      return 'none';
    }
  });
};
