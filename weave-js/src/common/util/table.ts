import {
  isAssignableTo,
  list,
  listObjectType,
  maybe,
  Type,
  typedDict,
  typedDictPropertyTypes,
} from '@wandb/weave/core';

import {TABLE_FILE_TYPE} from '../types/file';

export const getTableKeysFromNodeType = (
  inputNodeType: Type,
  defaultKey: string | null = null
) => {
  if (
    inputNodeType != null &&
    isAssignableTo(inputNodeType, list(typedDict({})))
  ) {
    const typeMap = typedDictPropertyTypes(listObjectType(inputNodeType));
    const tableKeys = Object.keys(typeMap)
      .filter(key => {
        return isAssignableTo(typeMap[key], maybe(TABLE_FILE_TYPE));
      })
      .sort();
    const value =
      tableKeys.length > 0 &&
      defaultKey != null &&
      tableKeys.indexOf(defaultKey) !== -1
        ? defaultKey
        : tableKeys?.[0] ?? '';
    return {tableKeys, value};
  }
  return {tableKeys: [], value: ''};
};
