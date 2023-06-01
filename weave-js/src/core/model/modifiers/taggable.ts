import {
  concreteTaggedValue,
  isConcreteTaggedValue,
  isTaggedValue,
  isTaggedValueLike,
  isTaggedValueUnion,
  taggedValue,
  taggedValueTagType,
  taggedValueValueType,
  union,
} from '../helpers';
import type {ConcreteTaggedValue, TaggedValueType, Type, Val} from '../types';
export const taggable = (type: Type, applyFn: (inType: Type) => Type): Type => {
  if (isTaggedValue(type)) {
    return taggedValue(type.tag, applyFn(type.value));
  } else if (isTaggedValueUnion(type)) {
    // In the union case, apply to one member at a time. This way we get a
    // more specific union of TaggedValues instead of a TaggedValue with
    // unions for tags and values (we know which tag type goes with which
    // value).
    return union(type.members.map(m => taggedValue(m.tag, applyFn(m.value))));
  }
  return applyFn(type);
};

export const taggableAsync = async (
  type: Type,
  applyFn: (inType: Type) => Promise<Type>
): Promise<Type> => {
  if (isTaggedValue(type)) {
    return taggedValue(type.tag, await applyFn(type.value));
  } else if (isTaggedValueUnion(type)) {
    const appliedToMembers = await Promise.all(
      type.members.map(m => applyFn(m.value))
    );
    return union(
      type.members.map((m, i) => taggedValue(m.tag, appliedToMembers[i]))
    );
  }
  return applyFn(type);
};

export const taggableStrip = (type: Type): Type => {
  if (isTaggedValueLike(type)) {
    return taggedValueValueType(type);
  }
  return type;
};

type TaggableVal = {
  <Tag, Value, RTag, RValue>(
    val: ConcreteTaggedValue<Tag, Value>,
    func: (v: Value) => ConcreteTaggedValue<RTag, RValue>
  ): ConcreteTaggedValue<ConcreteTaggedValue<Tag, RTag>, RValue>;

  <Tag, Value, R>(
    val: ConcreteTaggedValue<Tag, Value>,
    func: (v: Value) => R
  ): ConcreteTaggedValue<Tag, R>;

  <V, R>(val: V, func: (v: V) => R): R;
};

export const taggableVal: TaggableVal = <T, R>(
  val: Val<T>,
  applyFn: (v: Val<T>) => R
) => {
  if (isConcreteTaggedValue(val)) {
    return concreteTaggedValue(val._tag, applyFn(val._value));
  }
  return applyFn(val);
};

type TaggableValAsync = {
  <Tag, Value, RTag, RValue>(
    val: ConcreteTaggedValue<Tag, Value>,
    func: (v: Value) => Promise<ConcreteTaggedValue<RTag, RValue>>
  ): Promise<ConcreteTaggedValue<ConcreteTaggedValue<Tag, RTag>, RValue>>;

  <Tag, Value, R>(
    val: ConcreteTaggedValue<Tag, Value>,
    func: (v: Value) => Promise<R>
  ): Promise<ConcreteTaggedValue<Tag, R>>;

  <V, R>(val: V, func: (v: V) => R): Promise<R>;
};

export const taggableValAsync: TaggableValAsync = async <T, R>(
  val: Val<T>,
  applyFn: (v: Val<T>) => Promise<R>
) => {
  if (isConcreteTaggedValue(val)) {
    return concreteTaggedValue(val._tag, await applyFn(val._value));
  }
  return applyFn(val);
};

type SkipTaggable = {
  <Tag extends Type, Value extends Type, R extends Type>(
    type: TaggedValueType<Tag, Value>,
    applyFn: (inType: Value, tagType?: Tag) => R
  ): R;
  <T, R extends Type>(type: T, applyFn: (inType: T, tagType?: Type) => R): R;
};

export const skipTaggable: SkipTaggable = (
  type: Type,
  applyFn: (inType: Type, tagType?: Type | undefined) => Type
): Type => {
  return isTaggedValueLike(type)
    ? applyFn(taggedValueValueType(type), taggedValueTagType(type))
    : applyFn(type);
};

export const skipTaggableAsync = async (
  type: Type,
  applyFn: (inType: Type, tagType?: Type) => Promise<Type>
): Promise<Type> => {
  return isTaggedValueLike(type)
    ? applyFn(taggedValueValueType(type), taggedValueTagType(type))
    : applyFn(type);
};

type SkipTaggableVal = {
  <Tag, Value, R>(
    value: ConcreteTaggedValue<Tag, Value>,
    applyFn: (inVal: Value, withTags: ConcreteTaggedValue<Tag, Value>) => R
  ): R;
  <T, R>(type: T, applyFn: (value: T) => R): R;
};

export const skipTaggableVal: SkipTaggableVal = (
  val: any,
  applyFn: (inVal: any, withTags?: any) => any
): any => {
  if (isConcreteTaggedValue(val)) {
    return applyFn(val._value, val);
  }
  return applyFn(val);
};

type SkipTaggableValAsync = {
  <Tag, Value, R>(
    value: ConcreteTaggedValue<Tag, Value>,
    applyFn: (
      inVal: Value,
      withTags: ConcreteTaggedValue<Tag, Value>
    ) => Promise<R>
  ): Promise<R>;
  <V, R>(
    value: V,
    applyFn: (value: V, withTags: undefined) => Promise<R>
  ): Promise<R>;
};

export const skipTaggableValAsync: SkipTaggableValAsync = async (
  val: any,
  applyFn: (inVal: any, withTags?: any) => Promise<any>
): Promise<any> => {
  if (isConcreteTaggedValue(val)) {
    return applyFn(val._value, val);
  }
  return applyFn(val);
};
