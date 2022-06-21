import * as Types from '@wandb/cg/browser/model/types';

// type PathDictToTSTypeWithPath<T extends Types.Type> = Array<{
//   key: string;
//   path: Types.Node<T>;
// }>;

type UnionType<T extends Types.Union> = {
  [K in keyof T['members']]: K extends number
    ? TypeToTSTypeWithPath<T['members'][K]>
    : never;
};

export type TypeToTSTypeWithPath<T extends Types.Type> = T extends Types.Union
  ? UnionType<T>[number] // : T extends Dict // ? PathDictToTSTypeWithPath<T['objectType']>
  : Types.Node<T>;

export type PathObjOrDictWithPath<T extends Types.Type> =
  // | PathDictToTSTypeWithPath<T>
  Types.Node<T>;

// export function isSinglePathObjTSType<T extends Types.Type>(
//   type: Types.Node<T> // | PathDictToTSTypeWithPath<T>
// ): type is Types.Node<T> {
//   return !_.isArray(type);
// }
