// TODO: rename this to opKindParts.ts or opBuilderHelpers.

import * as _ from 'lodash';

import {
  concreteTaggedValue,
  getTypeDimDepth,
  getValueDimDepth,
  isConcreteTaggedValue,
  isList,
  isTaggedValue,
  isUnion,
  list,
  taggedValue,
  union,
} from '../helpers';
import type {ConcreteTaggedValue, Type, Val} from '../types';
import {
  mappable,
  mappableAsync,
  mappableStrip,
  mappableVal,
  mappableValAsync,
} from './mappable';
import {
  nullable,
  nullableAsync,
  nullableStrip,
  nullableVal,
  nullableValAsync,
  skipNullable,
  skipNullableAsync,
} from './nullable';
import {
  skipTaggable,
  skipTaggableAsync,
  skipTaggableValAsync,
  taggable,
  taggableAsync,
  taggableStrip,
  taggableVal,
  taggableValAsync,
} from './taggable';
import {Nullable} from './types';
/// // Functions to to create return types from input types. They
// preserve wrapped types like nullable and taggable

export const nullableTaggable = <T extends Type>(
  type: T,
  applyFn: (inType: Type) => Type
): Type => {
  // Could simplify this, since taggedValue is assignable to value, order
  // doesn't matter (so we can simplify at type creation time to a fixed
  // order, and then only unwrap that order here).
  return nullable(type, t => taggable(t, u => nullable(u, applyFn)));
};

export const nullableTaggableAsync = async (
  type: Type,
  applyFn: (inType: Type) => Promise<Type>
): Promise<Type> => {
  return nullableAsync(type, t =>
    taggableAsync(t, u => nullableAsync(u, applyFn))
  );
};

export const nullableTaggableStrip = (type: Type): Type => {
  return nullableStrip(taggableStrip(nullableStrip(type)));
};

export const nullableTaggableVal = <T, R>(
  val: Val<T>,
  applyFn: (inVal: Val<T>) => R
) => {
  return nullableVal(val, t => taggableVal(t, u => nullableVal(u, applyFn)));
};

export const nullableTaggableValAsync = (
  val: any,
  applyFn: (inVal: any, withTags?: any) => Promise<any>
): Promise<any> => {
  return nullableValAsync(val, t =>
    taggableValAsync(t, u => nullableValAsync(u, v => applyFn(v)))
  );
};

export const skipNullableTaggable = <T extends Type>(
  type: T,
  applyFn: (inType: Type) => Type
): Type => {
  return skipNullable(type, t => taggable(t, u => skipNullable(u, applyFn)));
};

export const skipNullableTaggableAsync = async (
  type: Type,
  applyFn: (inType: Type) => Promise<Type>
): Promise<Type> => {
  return skipNullableAsync(type, t =>
    taggableAsync(t, u => skipNullableAsync(u, applyFn))
  );
};

export const nullableSkipTaggable = (
  type: Type,
  applyFn: (inType: Type, tagType?: Type) => Type
): Type => {
  // Could simplify this, since taggedValue is assignable to value, order
  // doesn't matter (so we can simplify at type creation time to a fixed
  // order, and then only unwrap that order here).
  return nullable(type, t =>
    skipTaggable(t, (u, tagType) => nullable(u, v => applyFn(v, tagType)))
  );
};

export const nullableSkipTaggableAsync = (
  type: Type,
  applyFn: (inType: Type, tagType?: Type) => Promise<Type>
): Promise<Type> => {
  return nullableAsync(type, t =>
    skipTaggableAsync(t, (u, tagType) =>
      nullableAsync(u, v => applyFn(v, tagType))
    )
  );
};

type NullableSkipTaggableValAsync = {
  <Tag, Value, R>(
    value: Nullable<ConcreteTaggedValue<Tag, Value>>,
    applyFn: (
      inVal: Value,
      withTags: ConcreteTaggedValue<Tag, Value>
    ) => Promise<R>
  ): Promise<R>;
  <V, R>(
    value: Nullable<V>,
    applyFn: (value: V, withTags: undefined) => Promise<R>
  ): Promise<R>;
};

export const nullableSkipTaggableValAsync: NullableSkipTaggableValAsync = (
  val: any,
  applyFn: (inVal: any, withTags: any) => Promise<any>
): Promise<any> => {
  return nullableValAsync(val, t =>
    skipTaggableValAsync(t, (u, uWithTags) =>
      nullableValAsync(u, v => applyFn(v, uWithTags))
    )
  );
};

export const mappableNullable = (
  type: Type,
  applyFn: (inType: Type) => Type
): Type => {
  return nullable(type, t => mappable(t, u => nullable(u, applyFn)));
};

export const mappableNullableVal = (
  val: any,
  applyFn: (inVal: any) => any
): any => {
  return nullableVal(val, t => mappableVal(t, u => nullableVal(u, applyFn)));
};

export const mappableNullableValAsync = (
  val: any,
  applyFn: (inVal: any) => Promise<any>
): Promise<any> => {
  return nullableValAsync(val, t =>
    mappableValAsync(t, u => nullableValAsync(u, applyFn))
  );
};

export const mappableTaggable = (
  type: Type,
  applyFn: (inType: Type) => Type
): Type => {
  return taggable(type, t => mappable(t, u => taggable(u, applyFn)));
};

export const mappableTaggableVal = (
  val: any,
  applyFn: (inVal: any) => any
): any => {
  return taggableVal(val, t => mappableVal(t, u => taggableVal(u, applyFn)));
};

export const mappableTaggableValAsync = (
  val: any,
  applyFn: (inVal: any) => Promise<any>
): Promise<any> => {
  return taggableValAsync(val, t =>
    mappableValAsync(t, u => taggableValAsync(u, applyFn))
  );
};

export const mappableNullableTaggable = (
  type: Type,
  applyFn: (inType: Type) => Type
): Type => {
  return nullableTaggable(type, t =>
    mappable(t, u => nullableTaggable(u, applyFn))
  );
};

export const mappableNullableTaggableAsync = (
  type: Type,
  applyFn: (inType: Type) => Promise<Type>
): Promise<Type> => {
  return nullableTaggableAsync(type, t =>
    mappableAsync(t, u => nullableTaggableAsync(u, applyFn))
  );
};

export const mappableNullableTaggableStrip = (type: Type): Type => {
  return nullableTaggableStrip(mappableStrip(nullableTaggableStrip(type)));
};

export const mappableNullableTaggableVal = (
  val: any,
  applyFn: (inVal: any) => any
): any => {
  return nullableTaggableVal(val, t =>
    mappableVal(t, u => nullableTaggableVal(u, applyFn))
  );
};

export const mappableNullableTaggableValAsync = async (
  val: any,
  applyFn: (inVal: any) => Promise<any>
): Promise<any> => {
  // This function is a major cg hotspot. It is manual implementation of this
  // logic:
  // return nullableTaggableValAsync(val, t =>
  //   mappableValAsync(t, u => nullableTaggableValAsync(u, v => applyFn(v)))
  // );
  // Using the above logic instead results in a ton of allocation and gc
  // activity, because of all of the anonymous functions.
  if (val == null) {
    // nullable
    return val;
  }
  let outerTag: any;
  if (isConcreteTaggedValue(val)) {
    // taggable
    if (val._value == null) {
      // nullable
      return val;
    }
    outerTag = val._tag;
    val = val._value;
  }
  if (_.isArray(val)) {
    // mappable
    const res: any[] = [];
    for (const v of val) {
      if (v == null) {
        // nullable
        res.push(null);
      } else if (isConcreteTaggedValue(v)) {
        // taggable
        if (v._value == null) {
          // nullable
          res.push(v);
        } else {
          res.push(concreteTaggedValue(v._tag, await applyFn(v._value)));
        }
      } else {
        res.push(await applyFn(v));
      }
    }
    val = res;
  } else {
    val = await applyFn(val);
  }
  if (outerTag !== undefined) {
    return concreteTaggedValue(outerTag, val);
  } else {
    return val;
  }
};

export const mappableSkipTaggable = (
  type: Type,
  applyFn: (inType: Type) => Type
): Type => {
  return skipTaggable(type, t => mappable(t, u => skipTaggable(u, applyFn)));
};

export const mappableSkipTaggableAsync = (
  type: Type,
  applyFn: (inType: Type) => Promise<Type>
): Promise<Type> => {
  return skipTaggableAsync(type, t =>
    mappableAsync(t, u => skipTaggableAsync(u, applyFn))
  );
};

export const mappableNullableSkipTaggable = (
  type: Type,
  applyFn: (inType: Type) => Type
): Type => {
  return nullableSkipTaggable(type, t =>
    mappable(t, u => nullableSkipTaggable(u, applyFn))
  );
};

export const mappableNullableSkipTaggableAsync = (
  type: Type,
  applyFn: (inType: Type) => Promise<Type>
): Promise<Type> => {
  return nullableSkipTaggableAsync(type, t =>
    mappableAsync(t, u => nullableSkipTaggableAsync(u, applyFn))
  );
};

export const mappableNullableSkipTaggableValAsync = (
  val: any,
  applyFn: (
    inVal: any,
    withTags?: any,
    mapIndex?: number | undefined
  ) => Promise<any>
): Promise<any> => {
  return nullableSkipTaggableValAsync(val, (t, tWithTags) =>
    mappableValAsync(t, (u, didMap, mapIndex) =>
      nullableSkipTaggableValAsync(u, (v, vWithTags) =>
        applyFn(v, didMap ? vWithTags : tWithTags, mapIndex)
      )
    )
  );
};

// mntTypeApply will apply a `fn` to the `type` with the following rules:
// - the type will be "mapped" down to `dims` dimension (defaulting to 0 - unit dimension).
//   Note that if the input type does not have at least `dim` dimensions, error is thrown.
// - if `tags` is set to `true`, then the tags will be maintained through the mapping, else
//   will be removed, and added after the function is applied
// - if `nones` is set to `true`, then the 'none' type will be passed to the function,
//   else it will be skipped.
// Note: if there are unions in the type tree, the fn will be applied to each member of the union.
// This is different than the other mappable/nullable/taggable functions.
export type TypeProcessingConfig = {
  dims?: number;
  tags?: boolean;
  nones?: boolean;
};
export const mntTypeApply = (
  type: Type,
  fn: (type: Type) => Type,
  config?: TypeProcessingConfig
): Type => {
  const targetDims = config?.dims ?? 0;
  let targetListDepth: number | null = null;
  if (targetDims > 0) {
    const typeDimDepth = getTypeDimDepth(type);
    if (typeDimDepth < targetDims) {
      console.warn('TypeApply: Type does not have enough dimensions');
      return 'invalid';
    }
    targetListDepth = typeDimDepth - targetDims;
  }
  return mntTypeApplyHelper(
    type,
    fn,
    targetListDepth,
    config?.tags ?? false,
    config?.nones ?? false,
    null,
    {cache: null}
  );
};

export const mntTypeApplyAsync = async (
  type: Type,
  fn: (type: Type) => Promise<Type>,
  config?: TypeProcessingConfig
): Promise<Type> => {
  const targetDims = config?.dims ?? 0;
  let targetListDepth: number | null = null;
  if (targetDims > 0) {
    const typeDimDepth = getTypeDimDepth(type);
    if (typeDimDepth < targetDims) {
      console.warn('ApplyAsync: Type does not have enough dimensions');
      return Promise.resolve('invalid');
    }
    targetListDepth = typeDimDepth - targetDims;
  }
  return mntTypeApplyAsyncHelper(
    type,
    fn,
    targetListDepth,
    config?.tags ?? false,
    config?.nones ?? false,
    null,
    {cache: null}
  );
};

export const mntTypeStrip = (
  type: Type,
  config?: TypeProcessingConfig
): Type => {
  const targetDims = config?.dims ?? 0;
  let targetListDepth: number | null = null;
  if (targetDims > 0) {
    const typeDimDepth = getTypeDimDepth(type);
    if (typeDimDepth < targetDims) {
      console.warn('TypeStrip: Type does not have enough dimensions');
      return 'invalid';
    }
    targetListDepth = typeDimDepth - targetDims;
  }
  return mntTypeStripHelper(
    type,
    targetListDepth,
    config?.tags ?? false,
    config?.nones ?? false
  );
};

export const mntValueApply = (
  value: any,
  fn: (value: any) => any,
  config?: TypeProcessingConfig
): any => {
  const targetDims = config?.dims ?? 0;
  let targetListDepth: number | null = null;
  if (targetDims > 0) {
    const typeDimDepth = getValueDimDepth(value);
    if (typeDimDepth != null) {
      if (typeDimDepth < targetDims) {
        console.warn('ValueApply: Type does not have enough dimensions');
        return undefined;
      }
      targetListDepth = typeDimDepth - targetDims;
    }
  }
  return mntValueApplyHelper(
    value,
    fn,
    targetListDepth,
    config?.tags ?? false,
    config?.nones ?? false,
    null,
    {cache: null, valid: false}
  );
};

export const mntValueApplyAsync = async (
  value: any,
  fn: (value: any) => Promise<any>,
  config?: TypeProcessingConfig
): Promise<any> => {
  const targetDims = config?.dims ?? 0;
  let targetListDepth: number | null = null;
  if (targetDims > 0) {
    const typeDimDepth = getValueDimDepth(value);
    if (typeDimDepth != null) {
      if (typeDimDepth < targetDims) {
        throw new TypeError(
          'ValueApplyAsync: Type does not have enough dimensions'
        );
      }
      targetListDepth = typeDimDepth - targetDims;
    }
  }
  return mntValueApplyAsyncHelper(
    value,
    fn,
    targetListDepth,
    config?.tags ?? false,
    config?.nones ?? false,
    null,
    {cache: null, valid: false}
  );
};

const mntTypeApplyHelper = (
  type: Type,
  fn: (type: Type) => Type,
  listDepth: number | null,
  tags: boolean,
  nones: boolean,
  ancestorTag: Type | null,
  noneTypeResult: {cache: Type | null}
): Type => {
  if (isTaggedValue(type)) {
    // If it is a tagged value, unwrap it, but maintain the tag as an ancestor.
    if (tags) {
      return mntTypeApplyHelper(
        type.value,
        fn,
        listDepth,
        tags,
        nones,
        taggedValue(ancestorTag, type.tag),
        noneTypeResult
      );
    } else {
      return taggedValue(
        taggedValue(ancestorTag, type.tag),
        mntTypeApplyHelper(
          type.value,
          fn,
          listDepth,
          tags,
          nones,
          null,
          noneTypeResult
        )
      );
    }
  } else if (isList(type) && (listDepth == null || listDepth > 0)) {
    // If it is a list, unwrap it, but maintain the list as an ancestor.
    const newListDepth = listDepth != null ? listDepth - 1 : null;
    return list(
      mntTypeApplyHelper(
        type.objectType,
        fn,
        newListDepth,
        tags,
        nones,
        ancestorTag,
        noneTypeResult
      ),
      type.minLength,
      type.maxLength
    );
  } else if (isUnion(type)) {
    // If it is a union, apply the function to each member, then union the results.
    return union(
      type.members.map(m => {
        return mntTypeApplyHelper(
          m,
          fn,
          listDepth,
          tags,
          nones,
          ancestorTag,
          noneTypeResult
        );
      })
    );
  } else if (nones || type !== 'none') {
    // for valid types, wrap the ancestor tag, and lists appropriately before applying function
    if (tags) {
      type = taggedValue(ancestorTag, type);
      ancestorTag = null;
    }
    if (type === 'none') {
      if (noneTypeResult.cache == null) {
        noneTypeResult.cache = fn(type);
      }
      type = noneTypeResult.cache;
    } else {
      type = fn(type);
    }
  }

  // Finally, rewrap the final type on the way out:
  type = taggedValue(ancestorTag, type);

  return type;
};

const mntTypeApplyAsyncHelper = async (
  type: Type,
  fn: (type: Type) => Promise<Type>,
  listDepth: number | null,
  tags: boolean,
  nones: boolean,
  ancestorTag: Type | null,
  noneTypeResult: {cache: Type | null}
): Promise<Type> => {
  if (isTaggedValue(type)) {
    // If it is a tagged value, unwrap it, but maintain the tag as an ancestor.
    if (tags) {
      return mntTypeApplyAsyncHelper(
        type.value,
        fn,
        listDepth,
        tags,
        nones,
        taggedValue(ancestorTag, type.tag),
        noneTypeResult
      );
    } else {
      return taggedValue(
        taggedValue(ancestorTag, type.tag),
        await mntTypeApplyAsyncHelper(
          type.value,
          fn,
          listDepth,
          tags,
          nones,
          null,
          noneTypeResult
        )
      );
    }
  } else if (isList(type) && (listDepth == null || listDepth > 0)) {
    // If it is a list, unwrap it, but maintain the list as an ancestor.
    const newListDepth = listDepth != null ? listDepth - 1 : null;
    return list(
      await mntTypeApplyAsyncHelper(
        type.objectType,
        fn,
        newListDepth,
        tags,
        nones,
        ancestorTag,
        noneTypeResult
      ),
      type.minLength,
      type.maxLength
    );
  } else if (isUnion(type)) {
    // If it is a union, apply the function to each member, then union the results.
    return union(
      await Promise.all(
        type.members.map(m => {
          return mntTypeApplyAsyncHelper(
            m,
            fn,
            listDepth,
            tags,
            nones,
            ancestorTag,
            noneTypeResult
          );
        })
      )
    );
  } else if (nones || type !== 'none') {
    // for valid types, wrap the ancestor tag, and lists appropriately before applying function
    if (tags) {
      type = taggedValue(ancestorTag, type);
      ancestorTag = null;
    }
    if (type === 'none') {
      if (noneTypeResult.cache == null) {
        noneTypeResult.cache = await fn(type);
      }
      type = noneTypeResult.cache;
    } else {
      type = await fn(type);
    }
  }

  // Finally, rewrap the final type on the way out:
  type = taggedValue(ancestorTag, type);

  return type;
};

const mntTypeStripHelper = (
  type: Type,
  listDepth: number | null,
  tags: boolean,
  nones: boolean
): Type => {
  if (isTaggedValue(type)) {
    // If it is a tagged value, unwrap it, but maintain the tag as an ancestor.
    const res = mntTypeStripHelper(type.value, listDepth, tags, nones);
    return tags ? taggedValue(type.tag, res) : res;
  } else if (isList(type) && (listDepth == null || listDepth > 0)) {
    // If it is a list, unwrap it, but maintain the list as an ancestor.
    const newListDepth = listDepth != null ? listDepth - 1 : null;
    return mntTypeStripHelper(type.objectType, newListDepth, tags, nones);
  } else if (isUnion(type)) {
    // If it is a union, apply the function to each member, then union the results.
    const members = type.members
      .filter(m => {
        return (
          nones || (m !== 'none' && !(isTaggedValue(m) && m.value === 'none'))
        );
      })
      .map(m => {
        return mntTypeStripHelper(m, listDepth, tags, nones);
      });
    return members.length > 0 ? union(members) : 'none';
  }

  return type;
};

const mntValueApplyHelper = (
  value: any,
  fn: (value: any) => any,
  listDepth: number | null,
  tags: boolean,
  nones: boolean,
  ancestorTag: ConcreteTaggedValue | null,
  noneTypeResult: {cache: any; valid: boolean}
): any => {
  if (isConcreteTaggedValue<any, any>(value)) {
    // If it is a tagged value, unwrap it, but maintain the tag as an ancestor.
    if (tags) {
      return mntValueApplyHelper(
        value._value,
        fn,
        listDepth,
        tags,
        nones,
        ancestorTag != null
          ? concreteTaggedValue(ancestorTag, value._tag)
          : value._tag,
        noneTypeResult
      );
    } else {
      return concreteTaggedValue(
        ancestorTag != null
          ? concreteTaggedValue(ancestorTag, value._tag)
          : value._tag,
        mntValueApplyHelper(
          value._value,
          fn,
          listDepth,
          tags,
          nones,
          null,
          noneTypeResult
        )
      );
    }
  } else if (_.isArray(value) && (listDepth == null || listDepth > 0)) {
    // If it is a list, unwrap it, but maintain the list as an ancestor.
    const newListDepth = listDepth != null ? listDepth - 1 : null;
    return value.map(v =>
      mntValueApplyHelper(
        v,
        fn,
        newListDepth,
        tags,
        nones,
        ancestorTag,
        noneTypeResult
      )
    );
  } else if (nones || value != null) {
    // for valid types, wrap the ancestor tag, and lists appropriately before applying function
    if (tags && ancestorTag != null) {
      value = concreteTaggedValue(ancestorTag, value);
      ancestorTag = null;
    }
    if (value === 'none') {
      if (!noneTypeResult.valid) {
        noneTypeResult.cache = fn(value);
        noneTypeResult.valid = true;
      }
      value = noneTypeResult.cache;
    } else {
      value = fn(value);
    }
  }

  // Finally, rewrap the final type on the way out:
  if (ancestorTag != null) {
    value = concreteTaggedValue(ancestorTag, value);
  }

  return value;
};

const mntValueApplyAsyncHelper = async (
  value: any,
  fn: (value: any) => Promise<any>,
  listDepth: number | null,
  tags: boolean,
  nones: boolean,
  ancestorTag: ConcreteTaggedValue | null,
  noneTypeResult: {cache: any; valid: boolean}
): Promise<any> => {
  if (isConcreteTaggedValue<any, any>(value)) {
    // If it is a tagged value, unwrap it, but maintain the tag as an ancestor.
    if (tags) {
      return mntValueApplyAsyncHelper(
        value._value,
        fn,
        listDepth,
        tags,
        nones,
        ancestorTag != null
          ? concreteTaggedValue(ancestorTag, value._tag)
          : value._tag,
        noneTypeResult
      );
    } else {
      return concreteTaggedValue(
        ancestorTag != null
          ? concreteTaggedValue(ancestorTag, value._tag)
          : value._tag,
        await mntValueApplyAsyncHelper(
          value._value,
          fn,
          listDepth,
          tags,
          nones,
          null,
          noneTypeResult
        )
      );
    }
  } else if (_.isArray(value) && (listDepth == null || listDepth > 0)) {
    // If it is a list, unwrap it, but maintain the list as an ancestor.
    const newListDepth = listDepth != null ? listDepth - 1 : null;
    return Promise.all(
      value.map(v =>
        mntValueApplyAsyncHelper(
          v,
          fn,
          newListDepth,
          tags,
          nones,
          ancestorTag,
          noneTypeResult
        )
      )
    );
  } else if (nones || value != null) {
    // for valid types, wrap the ancestor tag, and lists appropriately before applying function
    if (tags && ancestorTag != null) {
      value = concreteTaggedValue(ancestorTag, value);
      ancestorTag = null;
    }
    if (value === 'none') {
      if (!noneTypeResult.valid) {
        noneTypeResult.cache = fn(value);
        noneTypeResult.valid = true;
      }
      value = noneTypeResult.cache;
    } else {
      value = await fn(value);
    }
  }

  // Finally, rewrap the final type on the way out:
  if (ancestorTag != null) {
    value = concreteTaggedValue(ancestorTag, value);
  }

  return value;
};

// TODO: mntValueStrip
