import {
  isAssignableTo,
  isListLike,
  isUnion,
  list,
  listObjectType,
  opConcat,
  opRunHistory,
  typedDict,
  typedDictPropertyTypes,
  union,
} from '@wandb/weave/core';
import {Node, Type} from '@wandb/weave/core';

import {LIST_RUNS_TYPE} from '../../../common/types/run';
import {PanelStepperConfigType} from './types';

export const NONE_KEY_AND_TYPE: {[key: string]: Type} = {
  '<none>': 'any' as Type,
};

export const getDefaultWorkingKeyAndType = (
  config: PanelStepperConfigType | undefined,
  propertyKeysAndTypes: {[key: string]: Type}
) => {
  const defaultKey =
    config?.workingKeyAndType?.key &&
    config.workingKeyAndType.key in propertyKeysAndTypes
      ? config.workingKeyAndType.key
      : Object.keys(propertyKeysAndTypes)[0] ?? NONE_KEY_AND_TYPE.key;
  return {
    key: defaultKey,
    type: propertyKeysAndTypes[defaultKey],
  };
};

export const getKeysAndTypesFromPropertyType = (
  propertyType: Type | undefined
): {[key: string]: Type} => {
  if (propertyType == null) {
    return {};
  }

  if (isAssignableTo(propertyType, list(typedDict({})))) {
    return typedDictPropertyTypes(listObjectType(propertyType));
  }

  if (isUnion(propertyType)) {
    return propertyType.members.reduce(
      (acc: {[key: string]: Type}, member: Type) => {
        const memberKeysAndTypes = getKeysAndTypesFromPropertyType(member);
        return {...acc, ...memberKeysAndTypes};
      },
      {}
    );
  }

  if (isListLike(propertyType)) {
    return getKeysAndTypesFromPropertyType(listObjectType(propertyType));
  }

  return {};
};

export const convertInputNode = (inputNode: Node) => {
  if (isAssignableTo(inputNode.type, LIST_RUNS_TYPE)) {
    return opConcat({arr: opRunHistory({run: inputNode as any})});
  }
  if (isAssignableTo(inputNode.type, list(list(union([typedDict({})]))))) {
    return opConcat({arr: inputNode as any});
  }
  return inputNode;
};
