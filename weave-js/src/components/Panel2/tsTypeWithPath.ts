import {Node, Type, Union} from '@wandb/weave/core';

// type PathDictToTSTypeWithPath<T extends Types.Type> = Array<{
//   key: string;
//   path: GraphTypes.Node<T>;
// }>;

type UnionType<T extends Union> = {
  [K in keyof T['members']]: K extends number
    ? TypeToTSTypeWithPath<T['members'][K]>
    : never;
};

export type TypeToTSTypeWithPath<T extends Type> = T extends Union
  ? UnionType<T>[number] // : T extends Dict // ? PathDictToTSTypeWithPath<T['objectType']>
  : Node<T>;

export type PathObjOrDictWithPath<T extends Type> =
  // | PathDictToTSTypeWithPath<T>
  Node<T>;

// export function isSinglePathObjTSType<T extends Types.Type>(
//   type: GraphTypes.Node<T> // | PathDictToTSTypeWithPath<T>
// ): type is GraphTypes.Node<T> {
//   return !_.isArray(type);
// }
