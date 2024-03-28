import _, {isArray, isObject, mapValues} from 'lodash';

import {hexToId} from '../util/digest';
import {has} from '../util/has';
import {extension as fileExtension} from '../util/path';
import {splitOnce} from '../util/string';
import {taggable} from './modifiers';
import {
  ConcreteTaggedValue,
  ConstType,
  Dict,
  File,
  FunctionInputTypes,
  FunctionType,
  ListType,
  LoadedPathMetadata,
  MediaType,
  ObjectType,
  PathType,
  RootObjectType,
  SimpleType,
  TableType,
  TaggedValueType,
  TimestampType,
  Type,
  TypedDictType,
  Union,
} from './types';
import {
  ALL_LIST_TYPES,
  BASIC_MEDIA_TYPES,
  GROUPABLE_TYPES,
  SORTABLE_TYPES,
} from './types';

export function isSimpleTypeShape(t: Type): t is SimpleType {
  return typeof t === 'string';
}

export function getTypeName(t: Type): string {
  if (isSimpleTypeShape(t)) {
    return t;
  }
  return t.type;
}

// Returns a list of all paths for the object.
// Traversing lists are converted to "*",
// nulls and tags are stripped, and dictionary
// properties are converted to keys

export function allObjPaths(objectType: Type, depth = Infinity): PathType[] {
  let paths: PathType[] = [];
  objectType = nullableTaggableValue(objectType);
  if (isTypedDictLike(objectType)) {
    for (const [key, valType] of Object.entries(
      typedDictPropertyTypes(objectType)
    )) {
      if (valType == null) {
        throw new Error('allObjPaths: found null property type');
      }
      let childPaths: PathType[] = [];
      if (depth > 0) {
        childPaths = allObjPaths(valType, depth - 1).map(p => ({
          path: [key, ...p.path],
          type: p.type,
        }));
      }
      if (childPaths.length === 0) {
        childPaths = [{path: [key], type: valType}];
      }
      paths = [...paths, ...childPaths];
    }
  } else if (isObjectTypeLike(objectType) && !isMediaType(objectType)) {
    for (const [key, valType] of Object.entries(
      unionObjectTypeAttrTypes(objectType)
    )) {
      if (valType == null) {
        throw new Error('allObjPaths: found null property type');
      }
      const objKey = '__object__' + key;
      let childPaths: PathType[] = [];
      // if (depth > 0) {
      //   childPaths = allObjPaths(valType, depth - 1).map(p => ({
      //     path: [objKey, ...p.path],
      //     type: p.type,
      //   }));
      // }
      if (childPaths.length === 0) {
        childPaths = [{path: [objKey], type: valType}];
      }
      paths = [...paths, ...childPaths];
    }
  } else if (isListLike(objectType) && depth > 0) {
    const valType = listObjectType(objectType);
    const childPaths: PathType[] = allObjPaths(valType, depth - 1)
      .filter(p => p.path.length > 0)
      .map(p => ({
        path: ['*', ...p.path],
        type: p.type,
      }));
    paths = [...paths, ...childPaths];
  }
  return paths;
}

// TODO(np): This seriously needs tests
export function toPythonTyping(type: Type): string {
  const PYTHON_UNCONVERTED_TYPE = '**UNCONVERTED_TYPE**';

  if (type === undefined) {
    return PYTHON_UNCONVERTED_TYPE;
  }

  if (isSimpleTypeShape(type)) {
    if (type === 'number') {
      return 'float';
    } else if (type === 'string') {
      return 'str';
    }
    return type;
  } else if (type.type === 'tagged') {
    // ignore
    return toPythonTyping(type.value);
  } else if (type.type === 'typedDict') {
    // typing.TypedDict({ 'key1': type1, 'keyN': typeN })
    return `typing.TypedDict('TypedDict', {${_.map(
      type.propertyTypes,
      (v, k) => `'${k}': ${toPythonTyping(v!)}`
    ).join(', ')}})`;
  } else if (type.type === 'dict') {
    // dict[str, value_type]
    return `dict[str, ${toPythonTyping(type.objectType)}]`;
  } else if (type.type === 'list') {
    // list[element_type]
    return `list[${toPythonTyping(type.objectType)}]`;
  } else if (type.type === 'function') {
    // typing.Callable[[arg1type, arg2type], return]
    return `typing.Callable[[${_.map(type.inputTypes, (v, k) =>
      toPythonTyping(v)
    ).join(', ')}], ${toPythonTyping(type.outputType)}]`;
  } else if (type.type === 'dir') {
    return 'Dir';
  } else if (type.type === 'union') {
    return type.members.map(toPythonTyping).join('|');
  } else if (type.type === 'table') {
    return PYTHON_UNCONVERTED_TYPE;
  } else if (type.type === 'joined-table') {
    return PYTHON_UNCONVERTED_TYPE;
  } else if (type.type === 'partitioned-table') {
    return PYTHON_UNCONVERTED_TYPE;
  } else if (type.type === 'file') {
    return PYTHON_UNCONVERTED_TYPE;
    // if (type.wbObjectType != null) {
    //   return `File<${toString(type.wbObjectType, simple, level)}>`;
    // }
    // return `File<{${
    //   type.extension != null ? 'extension: ' + type.extension : ''
    // }}>`;
  } else if (type.type === 'ndarray') {
    return PYTHON_UNCONVERTED_TYPE;
    // return `NDArray<${type.shape}>`;
  } else if (isMediaType(type)) {
    return type.type;
  }

  return PYTHON_UNCONVERTED_TYPE;
}

export const isLoadedPathMetadata = (o: any): o is LoadedPathMetadata => {
  return o._type === 'loaded-path';
};

const filePrefixToMediaType = (prefix: string): MediaType | null => {
  if (prefix === 'image-file') {
    return {type: 'image-file'};
  } else if (prefix === 'video-file') {
    return {type: 'video-file'};
  } else if (prefix === 'audio-file') {
    return {type: 'audio-file'};
  } else if (prefix === 'html-file') {
    return {type: 'html-file'};
  } else if (prefix === 'bokeh-file') {
    return {type: 'bokeh-file'};
  } else if (prefix === 'object3D-file') {
    return {type: 'object3D-file'};
  } else if (prefix === 'molecule-file') {
    return {type: 'molecule-file'};
  } else if (prefix === 'pytorch-model-file') {
    return {type: 'pytorch-model-file'};
  } else if (prefix === 'table') {
    return {type: 'table', columnTypes: {}};
  } else if (prefix === 'joined-table') {
    return {type: 'joined-table', columnTypes: {}};
  } else if (prefix === 'partitioned-table') {
    return {type: 'partitioned-table', columnTypes: {}};
  }
  return null;
};

export const filePathToType = (path: string) => {
  const filePath = path;
  const fileType: File = {
    type: 'file' as const,
    extension: fileExtension(filePath),
  };
  const chromePatchMatch = path.match(/.+\.(trace)(.json)?(?:.gz|.zip)?$/);
  if (chromePatchMatch != null) {
    const chromePatchMatchSliced = chromePatchMatch.slice(1);
    fileType.extension = chromePatchMatchSliced.join('');
  } else if (filePath.endsWith('.json')) {
    const components = filePath.split('.');
    if (components.length >= 3) {
      const potentialWbObjectType = components[components.length - 2];
      const wbObjectType = filePrefixToMediaType(potentialWbObjectType);
      if (wbObjectType != null) {
        fileType.wbObjectType = wbObjectType;
      }
    }
  }
  return fileType;
};

function getIdAndPathFromURI(url: string): {id: string; path: string} {
  if (url.startsWith('//')) {
    url = url.slice(2);
  } else if (url.startsWith('/')) {
    url = url.slice(1);
  } else {
    throw new Error('Invalid artifact reference ' + url);
  }
  const [artId, refAssetPath] = splitOnce(url, '/');
  if (refAssetPath == null) {
    throw new Error('Invalid artifact reference ' + url);
  }
  return {id: artId, path: refAssetPath};
}

const WANDB_ARTIFACT_SCHEME = 'wandb-artifact:';
const WANDB_ARTIFACT_CLIENT_SCHEME = 'wandb-client-artifact:';
export function parseArtifactRef(ref: string) {
  if (ref.startsWith(WANDB_ARTIFACT_SCHEME)) {
    const {id, path} = getIdAndPathFromURI(
      ref.slice(WANDB_ARTIFACT_SCHEME.length)
    );
    return {artifactId: hexToId(id), assetPath: path};
  } else if (ref.startsWith(WANDB_ARTIFACT_CLIENT_SCHEME)) {
    const {id, path} = getIdAndPathFromURI(
      ref.slice(WANDB_ARTIFACT_CLIENT_SCHEME.length)
    );
    return {artifactId: id, assetPath: path};
  }
  throw new Error('invalid artifact reference: ' + ref);
}

// TODO define when toTag is tagged value
// Can assign a tagged value as long as the target tag is possibly present
// somewhere in the lhs tag chain
export function tagAssignable(tagType: Type, toTag: Type): boolean {
  if (isTaggedValue(tagType)) {
    return (
      isAssignableTo(tagType.value, toTag) || tagAssignable(tagType.tag, toTag)
    );
  } else if (isTaggedValueUnion(tagType)) {
    return tagType.members.some(m => tagAssignable(m, toTag));
  } else {
    return isAssignableTo(tagType, toTag);
  }
}

export function isAssignableTo(type: Type, toType: Type): boolean {
  // even void is assignable to any!
  if (toType === 'any') {
    return true;
  }
  // invalid should be assignable to invalid, so just treat it like
  // any other basic type.
  // invalid is equivalent to void, meaning nothing. Function<any, void>
  // is clearly a subtype of Function<any, void>
  // TODO: confirm this doesn't break anything
  // if (type === 'invalid') {
  //   return false;
  // }

  if (isTaggedValue(type) && isAssignableTo(type.value, toType)) {
    return true;
  } else if (isUnion(type)) {
    // Union to union assignment. Each member in type must be assignable to
    // toType.
    if (type.members.length === 0) {
      return false;
    }
    return type.members.every(typeMemberType =>
      isAssignableTo(typeMemberType, toType)
    );
  } else if (isUnion(toType)) {
    return toType.members.some(fitMemberType =>
      isAssignableTo(type, fitMemberType)
    );
  } else if (isTaggedValue(type)) {
    // A tag value can be assigned to a tag value if the value itself is assignable,
    // and if there is any tag in the tag chain of type that's assignable to toType's
    // tag.
    if (isTaggedValue(toType) && isAssignableTo(type.value, toType.value)) {
      if (isTaggedValueLike(toType.tag)) {
        // If we're assigning to a tagged value whose tag is tagged value,
        // just check assignability of our tag to their tag.
        // This case is not used by any ops currently, but the union() function
        // in this file checks for type equality by doing a->b && b->a which
        // triggers this path.
        return isAssignableTo(toType.tag, type.tag);
      } else {
        // Use our special tagAssignable check, which says we can assign a taggedvalue
        // as long as the tag is possibly present somewhere in the tag chain.
        return tagAssignable(type.tag, toType.tag);
      }
    }
    return false;
    // Weave Python additions
  } else if (isConstType(type)) {
    if (isConstType(toType)) {
      return (
        isAssignableTo(type.valType, toType.valType) &&
        _.isEqual(type.val, toType.val)
      );
    }
    return isAssignableTo(type.valType, toType);
  } else if (isFunctionType(type) && !isFunctionType(toType)) {
    if (isAssignableTo(type.outputType, toType)) {
      return true;
    }
  }
  // if (!isSimpleTypeShape(type) && type.type === 'run-type') {
  //   return isAssignableTo(type._output, toType);
  if (isSimpleTypeShape(type) && isSimpleTypeShape(toType)) {
    // TODO: Stupid number hacks. This is totally not correct.
    if ((type === 'int' || type === 'float') && toType === 'number') {
      return true;
    }
    if (type === 'number' && (toType === 'int' || toType === 'float')) {
      return true;
    }
    if (type === 'int' && toType === 'float') {
      return true;
    }
    // End Weave Python additions
    return type === toType;
  } else if (!isSimpleTypeShape(type) && !isSimpleTypeShape(toType)) {
    if (type.type === 'dict' && toType.type === 'dict') {
      return isAssignableTo(type.objectType, toType.objectType);
    } else if (type.type === 'dict' && toType.type === 'typedDict') {
      for (const propType of Object.values(toType.propertyTypes)) {
        if (!isAssignableTo(type.objectType, propType!)) {
          return false;
        }
      }
      return true;
    } else if (
      (type.type as string) === 'plot' &&
      (toType.type as string) === 'plot'
    ) {
      // TODO: not true! Check column types!
      return true;
    } else if (type.type === 'table' && toType.type === 'table') {
      // TODO: not true! Check column types!
      return true;
    } else if (type.type === 'joined-table' && toType.type === 'joined-table') {
      // TODO: not true! Check column types!
      return true;
    } else if (
      type.type === 'partitioned-table' &&
      toType.type === 'partitioned-table'
    ) {
      // TODO: not true! Check column types!
      return true;
    } else if (type.type === 'typedDict' && toType.type === 'typedDict') {
      // Must have all keys in toType and types must match
      for (const key of Object.keys(toType.propertyTypes)) {
        const toKeyType = toType.propertyTypes[key]!;
        const keyType = type.propertyTypes[key];
        if (
          (toType.notRequiredKeys ?? []).includes(key) &&
          keyType === undefined
        ) {
          continue;
        }
        if (keyType === undefined || !isAssignableTo(keyType, toKeyType)) {
          return false;
        }
      }
      return true;
    } else if (type.type === 'typedDict' && toType.type === 'dict') {
      // Must have all keys in toType and types must match
      const properties = Object.keys(type.propertyTypes);
      if (properties.length === 0) {
        // Must have at least one key to match. This is kind of odd,
        // we can revisit later if we need. This prevents us from creating
        // panels like PanelIdCompare when we have an empty {}, like in the
        // return type of opTableRows.
        return false;
      }
      for (const key of properties) {
        const keyType = type.propertyTypes[key];
        if (!isAssignableTo(keyType!, toType.objectType)) {
          return false;
        }
      }
      return true;
      // For now, isList() actually checks if something "implements the list interface"
      // while checking if toType.type == 'list' is actually checking if the type
      // "is the list interface".
      // TODO: improve this with actual interface types or something better
    } else if (isList(type) && toType.type === 'list') {
      if (
        toType.maxLength != null &&
        (type.maxLength == null || type.maxLength > toType.maxLength)
      ) {
        return false;
      } else if (
        toType.minLength != null &&
        (type.minLength ?? 0) < toType.minLength
      ) {
        return false;
      }
      return isAssignableTo(type.objectType, toType.objectType);
    } else if (type.type === 'file' && toType.type === 'file') {
      if (
        toType.wbObjectType != null &&
        !isAssignableTo(type.wbObjectType ?? 'none', toType.wbObjectType)
      ) {
        return false;
      }
      if (toType.extension != null && type.extension !== toType.extension) {
        return false;
      }
      return true;
    } else if (type.type === 'dir' && toType.type === 'dir') {
      return true;
    } else if (type.type === 'function' && toType.type === 'function') {
      return isAssignableTo(type.outputType, toType.outputType);
    } else if (type.type === 'ndarray' && toType.type === 'ndarray') {
      // TODO: not true! Check shape!
      return true;
    } else if (type.type === 'image-file' && toType.type === 'image-file') {
      return true;
    } else if (type.type === 'video-file' && toType.type === 'video-file') {
      return true;
    } else if (type.type === 'audio-file' && toType.type === 'audio-file') {
      return true;
    } else if (type.type === 'html-file' && toType.type === 'html-file') {
      return true;
    } else if (type.type === 'bokeh-file' && toType.type === 'bokeh-file') {
      return true;
    } else if (
      type.type === 'wb_trace_tree' &&
      toType.type === 'wb_trace_tree'
    ) {
      return true;
    } else if (
      type.type === 'object3D-file' &&
      toType.type === 'object3D-file'
    ) {
      return true;
    } else if (
      type.type === 'molecule-file' &&
      toType.type === 'molecule-file'
    ) {
      return true;
    } else if (
      type.type === 'pytorch-model-file' &&
      toType.type === 'pytorch-model-file'
    ) {
      return true;
    } else if (type.type === 'timestamp' && toType.type === 'timestamp') {
      return true;
      // Weave Python additions
    } else if (
      // TODO: Check all subtypes
      type.type === 'container_panel_type' &&
      toType.type === 'Panel'
    ) {
      return true;
    } else {
      // More general type assignment, we can get rid of most of the cases
      // above. Just need to make it match the Python version.
      // TODO: simplify this whole function.
      if (!isTypeOrDescendent(type, toType.type)) {
        return false;
      }
      // TablePanel is a very sophisticated type and there are issues with empty
      // lists resulting in unknowns and the const functions have unknown return
      // types. Here we just say that if both are TablePanels, then assume it is
      // good
      if (
        (!isSimpleTypeShape(type) &&
          !isSimpleTypeShape(toType) &&
          (type.type as string) === 'tablePanel' &&
          (toType.type as string) === 'tablePanel') ||
        ((type.type as string) === 'Query' &&
          (toType.type as string) === 'Query') ||
        ((type.type as string) === 'tracePanel' &&
          (toType.type as string) === 'tracePanel')
      ) {
        return true;
      }
      return _.every(
        Object.keys(toType)
          .filter(k => k !== 'type' && !k.startsWith('_'))
          .map(k => {
            const currType = (type as any)[k] as Type;
            if (currType == null) {
              return false;
            }
            const otherType = (toType as any)[k] as Type;
            return isAssignableTo(currType, otherType);
          })
      );
    }
  } else if (!isSimpleTypeShape(type) && isSimpleTypeShape(toType)) {
    if (type.type === 'histogram' && toType === 'histogram') {
      return true;
    }
  }

  // End Weave Python additions

  // if (isTensor(toType)) {
  //   while (!isSimpleTypeShape(type) && type.type === 'list') {
  //     if (isAssignableTo(type, toType.objectType)) {
  //       return true;
  //     }
  //     return isAssignableTo(type.objectType, toType.objectType);
  //   }
  //   return isAssignableTo(type, toType.objectType);
  // }
  return false;
}

// Implements linear tag-chaining in the same way makeTaggingStandardOp does.
export function withNamedTag(tagName: string, tag: Type, value: Type): Type {
  if (isTaggedValueLike(tag)) {
    return taggedValue(
      taggedValueTagType(tag),
      taggedValue(typedDict({[tagName]: taggedValueValueType(tag)}), value)
    );
  }
  return taggedValue(typedDict({[tagName]: tag}), value);
}

export function concreteWithNamedTag(
  tagName: string,
  tag: any,
  value: any
): any {
  if (isConcreteTaggedValue(tag)) {
    return concreteTaggedValue(
      tag._tag,
      concreteTaggedValue({[tagName]: tag._value}, value)
    );
  }
  return concreteTaggedValue({[tagName]: tag}, value);
}

export function withGroupTag(base: Type, keyType: Type): Type {
  return withNamedTag('groupKey', keyType, base);
}
export function withJoinTag(base: Type, keyType: Type): Type {
  return taggedValue(typedDict({joinKey: 'string', joinObj: keyType}), base);
}

export function withTableRowTag(base: Type, tableType: Type): Type {
  return withNamedTag('table', tableType, base);
}

export function withFileTag(base: Type, fileType: Type): Type {
  return taggedValue(typedDict({file: fileType}), base);
}

export function fileTable(): Type {
  return withFileTag(
    {type: 'table', columnTypes: {}},
    file('json', {type: 'table', columnTypes: {}})
  );
}

export function tableRowValue(valueType: Type): Type {
  return withTableRowTag(
    valueType,
    withFileTag(
      maybe({type: 'table', columnTypes: {}}),
      file('json', {type: 'table', columnTypes: {}})
    )
  );
}

export function tableRowValueMaybeFile(valueType: Type): Type {
  return withTableRowTag(
    valueType,
    maybe(
      withFileTag(
        maybe({type: 'table', columnTypes: {}}),
        file('json', {type: 'table', columnTypes: {}})
      )
    )
  );
}

export function nDims(t: Type): number {
  t = nullableTaggableValue(t);
  if (isListLike(t)) {
    return 1 + nDims(listObjectType(t));
  }
  return 0;
}

// This is called a lot at the top level of modules, so we don't
// use union(), which relies on isAssignableTo. Doing this speeds up the
// unit test startup time.
export function maybe(t: Type): Type {
  if (isNullable(t)) {
    return t;
  } else if (isUnion(t)) {
    return {type: 'union', members: ['none', ...t.members]};
  } else {
    return {type: 'union', members: ['none', t]};
  }
}

// This is called a lot at the top level of modules, so we don't
// use union(), which relies on isAssignableTo. Doing this speeds up the
// unit test startup time.
export function oneOrMany(objectType: Type): Type {
  return {type: 'union', members: [list(objectType), objectType]};
}

export function nullableOneOrMany(objType: Type): Type {
  return maybe(oneOrMany(maybe(objType)));
}

// If a type is a maybe, get the inner type.
export function nonNullable(t: Type): Type {
  if (isUnion(t)) {
    return union(t.members.filter(memberType => memberType !== 'none'));
  }
  return t;
}

export function nonNullableDeep(t: Type): Type {
  if (isTaggedValue(t)) {
    return taggedValue(t.tag, nonNullableDeep(t.value));
  }
  if (isUnion(t)) {
    return union(
      t.members
        .map(memberType => nonNullableDeep(memberType))
        .filter(memberType => !isAssignableTo(memberType, 'none'))
    );
  }
  return t;
}

// This should not skip tags. If we need a version that does that,
// make a new function called isNullableLike

export function isNullable(t: Type): boolean {
  return isUnion(t) && t.members.findIndex(m => m === 'none') !== -1;
}

export function union(members: Type[]): Type {
  if (members.length === 0) {
    return 'invalid';
  }
  let allMembers: Type[] = [];
  for (const mem of members) {
    if (!isSimpleTypeShape(mem) && mem?.type === 'union') {
      allMembers = allMembers.concat(mem.members);
    } else if (isTaggedValue(mem) && isUnion(mem.value)) {
      allMembers = allMembers.concat(
        mem.value.members.map(m => taggedValue(mem.tag, m))
      );
    } else {
      allMembers.push(mem);
    }
  }
  const uniqMembers = _.uniqWith(
    allMembers,
    (a, b) =>
      _.isEqual(a, b) ||
      (a && b && isAssignableTo(a, b) && isAssignableTo(b, a))
  );

  // Split TaggedValue members out.
  const nonTaggedMembers: Type[] = [];
  const taggedMembers: TaggedValueType[] = [];
  for (const member of uniqMembers) {
    if (isTaggedValue(member)) {
      taggedMembers.push(member);
    } else {
      nonTaggedMembers.push(member);
    }
  }
  // Merge TaggedValues that have the same exact tags.
  const taggedMembersByTag = _.groupBy(taggedMembers, tv =>
    JSON.stringify(tv.tag)
  );
  const taggedMembersMerged = Object.values(taggedMembersByTag).map(
    sameTagMembers => {
      return {
        type: 'tagged' as const,
        tag: sameTagMembers[0].tag,
        value: union(sameTagMembers.map(m => m.value)),
      };
    }
  );

  const fullMembers = nonTaggedMembers.concat(taggedMembersMerged);
  if (fullMembers.length === 1) {
    return fullMembers[0];
  }
  return {type: 'union' as const, members: fullMembers};
}

export function isTaggedValue(t: Type): t is TaggedValueType {
  return !isSimpleTypeShape(t) && t?.type === 'tagged';
}

// Weave Python additions
export function isConstType(t: Type): t is ConstType {
  return !isSimpleTypeShape(t) && t.type === 'const';
}
// End Weave Python additions

export function isTaggedValueUnion(
  t: Type
): t is {type: 'union'; members: TaggedValueType[]} {
  return isUnion(t) && t.members.every(isTaggedValue);
}

export function isTaggedValueLike(t: Type): t is TaggedValueType | Union {
  if (isTaggedValue(t)) {
    return true;
  } else if (isTaggedValueUnion(t)) {
    return true;
  }
  return false;
}

export function taggedValueValueType(t: Type): Type {
  if (isTaggedValue(t)) {
    return t.value;
  } else if (isUnion(t)) {
    return union(t.members.map(m => (m as TaggedValueType).value));
  }
  throw new Error('taggedValueValueType: expected union or tagged value');
}

export function withoutTags(t: Type): Type {
  if (isTaggedValue(t)) {
    return withoutTags(t.value);
  } else if (isUnion(t)) {
    return union(t.members.map(m => withoutTags(m)));
  } else if (isList(t)) {
    return list(withoutTags(t.objectType), t.minLength, t.maxLength);
  } else if (isDict(t)) {
    return dict(withoutTags(t.objectType));
  } else if (isTypedDict(t)) {
    const mapped = mapValues(
      t.propertyTypes as {[key: string]: Type},
      withoutTags
    );
    return typedDict(mapped);
  }
  return t;
}

export function taggedValueTagType(t: Type): Type {
  if (isTaggedValue(t)) {
    return t.tag;
  } else if (isUnion(t)) {
    return union(t.members.map(m => (m as TaggedValueType).tag));
  }
  throw new Error('taggedValueTagType: expected union or tagged value');
}

// export function taggedValue(tagType: Type, valueType: Type): Type {
//   if (isTaggedValue(valueType)) {
//     // no tagged values allowed in the value-side! We ensure that recursive
//     // tags are always moved to the tag-side of a TaggedValue in opTypes.ts (taggable)
//     throw new Error('invalid');
//   }
//   return {
//     type: 'tagged',
//     tag: tagType,
//     value: valueType,
//   };
// }
export function taggedValue(
  tagType: Type | undefined | null,
  valueType: Type
): Type {
  if (tagType == null) {
    return valueType;
  }
  if (isUnion(valueType)) {
    return union(valueType.members.map(mem => taggedValue(tagType, mem)));
  }
  if (isTaggedValue(valueType)) {
    return taggedValue(taggedValue(tagType, valueType.tag), valueType.value);
  }
  return {
    type: 'tagged',
    tag: tagType,
    value: valueType,
  };
}

export function isConcreteTaggedValue<T, V>(
  value: unknown
): value is ConcreteTaggedValue<T, V> {
  return has('_tag', value) && has('_value', value);
}

export function concreteTaggedValue<Tag, ValueTag, ValueValue>(
  tag: Tag,
  value: ConcreteTaggedValue<ValueTag, ValueValue>
): ConcreteTaggedValue<ConcreteTaggedValue<Tag, ValueTag>, ValueValue>;
export function concreteTaggedValue<T, V>(
  tag: T,
  value: V
): ConcreteTaggedValue<T, V>;
export function concreteTaggedValue<T, V>(
  tag: T,
  value: V
): ConcreteTaggedValue<unknown, unknown> {
  if (isConcreteTaggedValue(value) && value._tag === tag) {
    return value;
  }
  if (isConcreteTaggedValue(value)) {
    return {
      _tag: concreteTaggedValue(tag, value._tag),
      _value: value._value,
    };
  }
  return {
    _tag: tag,
    _value: value,
  };
}

export function unwrapTaggedValues(result: any): any {
  if (result != null && result._tag !== undefined) {
    return unwrapTaggedValues(result._value);
  }
  if (isArray(result)) {
    return result.map((row: any) => unwrapTaggedValues(row));
  } else if (isObject(result) && !(result instanceof Date)) {
    return mapValues(result, (v: any) => unwrapTaggedValues(v));
  }
  return result;
}

export function isUnion(t: Type): t is Union {
  return !isSimpleTypeShape(t) && t?.type === 'union';
}

export function isTypedDict(t: Type): t is TypedDictType {
  return !isSimpleTypeShape(t) && t?.type === 'typedDict';
}

export function isObjectType(t: any): t is ObjectType {
  return !isSimpleTypeShape(t) && (t as any)?._is_object;
}

export function isFunctionType(
  maybeFunctionType: Type
): maybeFunctionType is FunctionType {
  return (
    typeof maybeFunctionType === 'object' &&
    maybeFunctionType.type === 'function'
  );
}

// TODO: Replace isTypedDict with isTypedDictLike in most places
export function isTypedDictLike(t: Type): t is TypedDictType | Union {
  return (
    isTypedDict(t) ||
    (isTaggedValue(t) && isTypedDictLike(t.value)) ||
    (isUnion(t) && t.members.every(isTypedDictLike))
  );
}

export function isObjectTypeLike(t: any): t is ObjectType | Union {
  return (
    isObjectType(t) ||
    (isTaggedValue(t) && isObjectTypeLike(t.value)) ||
    (isUnion(t) && t.members.every(isObjectTypeLike))
  );
}

export function typedDict(propertyTypes: {[key: string]: Type}): TypedDictType {
  return {
    type: 'typedDict',
    propertyTypes,
  };
}

export function rootObject(): RootObjectType {
  return {
    type: 'Object',
  };
}

export function isDict(t: Type): t is Dict {
  return !isSimpleTypeShape(t) && t?.type === 'dict';
}

export function dict(objectType: Type): Type {
  return {
    type: 'dict',
    objectType,
  };
}

export function isList(t: Type): t is ListType {
  return !isSimpleTypeShape(t) && ALL_LIST_TYPES.includes(t.type as any);
}

// TODO: Replace isList with isListLike in most places
export function isListLike(t: Type): t is ListType | Union {
  return (
    isList(t) ||
    (isTaggedValue(t) && isList(t.value)) ||
    (isFunction(t) && isListLike(t.outputType)) ||
    (isUnion(t) &&
      t.members.every(
        member =>
          isList(member) || (isTaggedValue(member) && isList(member.value))
      ))
  );
}

export function list(
  objectType: Type,
  minLength?: number,
  maxLength?: number
): ListType {
  if (minLength != null && maxLength != null) {
    return {
      type: 'list',
      objectType,
      minLength,
      maxLength,
    };
  } else if (minLength != null) {
    return {
      type: 'list',
      objectType,
      minLength,
    };
  } else if (maxLength != null) {
    return {
      type: 'list',
      objectType,
      maxLength,
    };
  }
  return {
    type: 'list',
    objectType,
  };
}

export function listWithLength(length: number, objectType: Type): ListType {
  return list(objectType, length, length);
}

function isTypeOrDescendent(type: Type, checkName: string): boolean {
  while (true) {
    if (isSimpleTypeShape(type)) {
      return false;
    }
    if (type.type === checkName) {
      return true;
    }
    if ((type as any)._base_type == null) {
      return false;
    }
    type = (type as any)._base_type;
  }
}

export function isFile(t: Type): t is File {
  return isTypeOrDescendent(t, 'file');
}

export function isFileLike(t: Type): t is File {
  if (isTaggedValue(t)) {
    t = taggedValueValueType(t);
  }

  return isFile(t);
}

export function fileWbObjectType(t: Type): Type | undefined {
  t = nullableTaggableValue(t);
  if (!isFile(t)) {
    throw new Error('fileWbObjectType: incoming type is not a file');
  }
  return t.wbObjectType;
}

export function file(extension: string, wbObjectType: MediaType): Type {
  return {
    type: 'file',
    extension,
    wbObjectType,
  };
}

export function isFunction(t: Type): t is FunctionType {
  return !isSimpleTypeShape(t) && t?.type === 'function';
}

export function isTable(t: Type): t is TableType {
  return !isSimpleTypeShape(t) && t?.type === 'table';
}

export function isPartitionedTable(t: Type): t is TableType {
  return !isSimpleTypeShape(t) && t?.type === 'partitioned-table';
}

export function isJoinedTable(t: Type): t is TableType {
  return !isSimpleTypeShape(t) && t?.type === 'joined-table';
}

export function isTimestamp(t: Type): t is TimestampType {
  return !isSimpleTypeShape(t) && t.type === 'timestamp';
}

export function functionType(
  inputTypes: FunctionInputTypes,
  outputType: Type
): Type {
  return {type: 'function', inputTypes, outputType};
}

export const canSortType = (type?: Type): boolean => {
  if (type == null) {
    return false;
  }
  return isAssignableTo(type, union(SORTABLE_TYPES));
};

export const canGroupType = (type?: Type): boolean => {
  if (type == null) {
    return false;
  }
  return isAssignableTo(type, union(GROUPABLE_TYPES));
};

export const numberBin = typedDict({start: 'number', stop: 'number'});
export const timestampBin = typedDict({
  start: {type: 'timestamp'},
  stop: {type: 'timestamp'},
});

/// // Functions to unwrap inner types

export const listObjectType = (type: Type): Type => {
  type = nullableTaggableValue(type);
  if (isUnion(type)) {
    return union(type.members.map(m => listObjectType(m)));
  }
  if (isFunction(type)) {
    return listObjectType(type.outputType);
  }
  if (!isList(type)) {
    throw new Error('listObjectType: incoming type is not a list');
  }
  return type.objectType;
};

// Unwraps the inner type of a list, and passes tagged value along.
export const listObjectTypePassTags = (type: Type): Type => {
  return taggable(type, untaggedType => {
    untaggedType = nullableTaggableValue(untaggedType);
    if (isUnion(untaggedType)) {
      return union(untaggedType.members.map(m => listObjectTypePassTags(m)));
    }
    if (isFunction(untaggedType)) {
      return listObjectTypePassTags(untaggedType.outputType);
    }
    if (!isList(untaggedType)) {
      throw new Error('listObjectType: incoming type is not a list');
    }
    return untaggedType.objectType;
  });
};

export const listLength = (type: Type): number | undefined => {
  const max = listMaxLength(type);
  const min = listMinLength(type);
  // List length is only "defined" if the max and min are equal and non-null
  if (max != null && max === min) {
    return max;
  }
  return undefined;
};

export const listMaxLength = (type: Type): number | undefined => {
  type = nullableTaggableValue(type);
  if (isUnion(type)) {
    const memberMaxLengths = type.members.map(m => listMaxLength(m));
    if (memberMaxLengths.some(m => m == null)) {
      return undefined;
    }
    return Math.max(...(memberMaxLengths as number[]));
  }
  if (!isList(type)) {
    throw new Error('listMaxLength: incoming type is not a list');
  }
  return type.maxLength;
};

export const listMinLength = (type: Type): number | undefined => {
  type = nullableTaggableValue(type);
  if (isUnion(type)) {
    const memberMinLengths = type.members.map(m => listMinLength(m));
    if (memberMinLengths.some(m => m == null)) {
      return undefined;
    }
    return Math.min(...(memberMinLengths as number[]));
  }
  if (!isList(type)) {
    throw new Error('listMinLength: incoming type is not a list');
  }
  return type.minLength;
};

export const taggableValue = (type: Type): Type => {
  if (isTaggedValueLike(type)) {
    type = taggedValueValueType(type);
  }
  if (isUnion(type) && type.members.every(isTaggedValue)) {
    type = union(type.members.map(m => (m as TaggedValueType).value));
  }
  return type;
};

const nonFunction = (type: Type): Type => {
  if (isFunction(type)) {
    return type.outputType;
  }
  return type;
};

export const nullableTaggableValue = (type: Type): Type => {
  return nonFunction(
    nonNullable(taggableValue(nonNullable(nonFunction(type))))
  );
};

export const typedDictPropertyTypes = (type: Type): {[key: string]: Type} => {
  type = nullableTaggableValue(type);
  if (isUnion(type)) {
    // TODO: (tim) make this nicer code. This makes a union out of the "union" of keys
    return type.members.reduce<{[key: string]: any}>((prev, curr, ndx) => {
      const unwrappedCurr = nullableTaggableValue(curr);
      if (!isTypedDict(unwrappedCurr) && unwrappedCurr !== 'none') {
        throw new Error(
          'typedDictPropertyTypes: incoming union type contains non-dict'
        );
      }
      let newVal: {[key: string]: any} = {};
      if (ndx === 0) {
        newVal =
          unwrappedCurr !== 'none' ? unwrappedCurr.propertyTypes ?? {} : {};
      } else {
        for (const existingProp in prev) {
          if (prev[existingProp] != null) {
            const prevProp = prev[existingProp];
            if (
              unwrappedCurr !== 'none' &&
              unwrappedCurr.propertyTypes[existingProp]
            ) {
              const currProp = unwrappedCurr.propertyTypes[existingProp];
              if (currProp) {
                newVal[existingProp] = union([prevProp, currProp]);
              } else {
                newVal[existingProp] = union([prevProp, 'none']);
              }
            } else {
              newVal[existingProp] = union([prevProp, 'none']);
            }
          } else {
            newVal[existingProp] = prev[existingProp];
          }
        }

        if (unwrappedCurr !== 'none') {
          for (const newProp in unwrappedCurr.propertyTypes) {
            if (unwrappedCurr.propertyTypes[newProp]) {
              const currProp = unwrappedCurr.propertyTypes[newProp];
              if (currProp != null && prev[newProp] == null) {
                newVal[newProp] = union([currProp, 'none']);
              }
            }
          }
        }
      }
      return newVal;
    }, {});
  }
  if (!isTypedDict(type)) {
    throw new Error('typedDictPropertyTypes: expected a typed dict');
  }
  return type.propertyTypes as {[key: string]: Type};
};

export const objectTypeAttrTypes = (
  type: ObjectType
): {[key: string]: Type} => {
  return _.fromPairs(
    Object.keys(type)
      .filter(k => k !== 'type' && !k.startsWith('_'))
      .map(k => {
        return [k, type[k]];
      })
  );
};

// Copied from typedDictPropertyTypes
export const unionObjectTypeAttrTypes = (type: Type): {[key: string]: Type} => {
  type = nullableTaggableValue(type);
  if (isUnion(type)) {
    // TODO: (tim) make this nicer code. This makes a union out of the "union" of keys
    return type.members.reduce<{[key: string]: any}>((prev, curr, ndx) => {
      const unwrappedCurr = nullableTaggableValue(curr);
      if (!isObjectType(unwrappedCurr) && unwrappedCurr !== 'none') {
        throw new Error(
          'objectTypeAttrTypes: incoming union type contains non-dict'
        );
      }
      const attrTypes =
        unwrappedCurr === 'none' ? {} : objectTypeAttrTypes(unwrappedCurr);
      let newVal: {[key: string]: any} = {};
      if (ndx === 0) {
        newVal = unwrappedCurr !== 'none' ? attrTypes : {};
      } else {
        for (const existingProp in prev) {
          if (prev[existingProp] != null) {
            const prevProp = prev[existingProp];
            if (unwrappedCurr !== 'none' && attrTypes[existingProp]) {
              const currProp = attrTypes[existingProp];
              if (currProp) {
                newVal[existingProp] = union([prevProp, currProp]);
              } else {
                newVal[existingProp] = union([prevProp, 'none']);
              }
            } else {
              newVal[existingProp] = union([prevProp, 'none']);
            }
          } else {
            newVal[existingProp] = prev[existingProp];
          }
        }

        if (unwrappedCurr !== 'none') {
          for (const newProp in attrTypes) {
            if (attrTypes[newProp]) {
              const currProp = attrTypes[newProp];
              if (currProp != null && prev[newProp] == null) {
                newVal[newProp] = union([currProp, 'none']);
              }
            }
          }
        }
      }
      return newVal;
    }, {});
  }
  if (!isObjectType(type)) {
    // console.log('GOT TYPE', type);
    throw new Error('unionObjectTypeAttrTypes: expected an ObjectType');
  }
  return objectTypeAttrTypes(type) as {[key: string]: Type};
};

export const isMediaType = (type: Type): type is MediaType => {
  return (
    !isSimpleTypeShape(type) &&
    BASIC_MEDIA_TYPES.filter(mt => type.type === mt.type).length > 0
  );
};

export const isMediaTypeLike = (type: Type): type is MediaType => {
  return BASIC_MEDIA_TYPES.some(t => isAssignableTo(t, type));
};

export const findNamedTagInType = (
  type: Type,
  tagName: string,
  tagType: Type
): Type => {
  if (isTaggedValue(type)) {
    if (isAssignableTo(type.tag, typedDict({[tagName]: maybe(tagType)}))) {
      if (isTaggedValue(type.tag)) {
        return taggedValue(
          type.tag.tag,
          typedDictPropertyTypes(type.tag)[tagName]
        );
      }
      return typedDictPropertyTypes(type.tag)[tagName];
    } else {
      return findNamedTagInType(type.tag, tagName, tagType);
    }
  } else if (isTaggedValueUnion(type)) {
    return union(
      type.members.map(m => findNamedTagInType(m, tagName, tagType))
    );
  }
  return 'none';
};

export const findNamedTagInVal = (val: any, tagName: string): any => {
  if (!isConcreteTaggedValue(val)) {
    return null;
  }
  const tag = getNamedTagFromValue(val, tagName);
  if (tag != null) {
    if (isConcreteTaggedValue(tag)) {
      return concreteTaggedValue(tag._tag, (tag._value as any)[tagName]);
    }
    return tag?.[tagName] ?? null;
  }
  return null;
};

export const getTypeDimDepth = (type: Type): number => {
  if (isTaggedValue(type)) {
    return getTypeDimDepth(type.value);
  } else if (isUnion(type)) {
    const unionDims = _.uniq(
      type.members.filter(m => !isAssignableTo(m, 'none')).map(getTypeDimDepth)
    );
    if (unionDims.length === 0) {
      return 0;
    }
    if (unionDims.length !== 1) {
      throw new TypeError('Type has ambiguous number of dimensions');
    }
    return unionDims[0];
  } else if (isList(type)) {
    return getTypeDimDepth(type.objectType) + 1;
  } else {
    return 0;
  }
};

export const getValueDimDepth = (value: any): number | null => {
  if (isConcreteTaggedValue<any, any>(value)) {
    return getValueDimDepth(value._value);
  } else if (_.isArray(value)) {
    let innerDim: number | null = 0;
    for (const v of value) {
      const potentialInnerDim = getValueDimDepth(v);
      // Settle on the first known dimension. Ideally we would
      // look at every element, but that would be too expensive.
      if (potentialInnerDim !== null) {
        innerDim = potentialInnerDim;
        break;
      }
    }
    return innerDim + 1;
  } else if (value == null) {
    return null;
  } else {
    return 0;
  }
};

// Union and Tagged Value are under-specified
// They should be a union of objects or tagged value of object
export const objectKeyType = (
  type: TypedDictType | Union,
  key: string
): Type => {
  const keyType = typedDictPropertyTypes(type)[key];
  if (keyType == null) {
    return 'none';
  }
  return keyType;
};

export const objectKeyVal = (val: any, key: string) => {
  if (val[key] == null) {
    return null;
  }
  return val[key];
};

export const getTagFromValue = (val: any) => {
  const tag = val._tag;
  if (isConcreteTaggedValue(tag)) {
    return tag._value;
  }
  return tag;
};

export const getValueFromTaggedValue = (val: any) => {
  return isConcreteTaggedValue(val) ? val._value : val;
};

export const getTagFromTaggedValue = (val: any) => {
  return isConcreteTaggedValue(val) ? val._tag : null;
};

export const getNamedTagFromValue = (val: any, name: string): any => {
  if (val == null) {
    throw new Error('getNamedTagFromValue: val is null');
  }
  const tag = val._tag;
  if (isConcreteTaggedValue(tag)) {
    if (name in (tag._value as any)) {
      return tag;
    }
    return getNamedTagFromValue(tag, name);
  } else {
    if (tag != null && name in tag) {
      return tag;
    }
  }
  return null;
};

export const getActualNamedTagFromValue = (val: any, name: string): any => {
  return getValueFromTaggedValue(getNamedTagFromValue(val, name));
};
