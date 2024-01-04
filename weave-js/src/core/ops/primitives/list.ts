// include the pca.js types, in case we're importing the source
// from outside of the cg project

// tslint doesn't like <reference>
/* tslint:disable-next-line */
/// <reference path="./projection.d.ts" />

import * as _ from 'lodash';

import callFunction from '../../callers';
import * as HL from '../../hl';
import {typeToString} from '../../language/js/print';
import {
  allObjPaths,
  concreteTaggedValue,
  concreteWithNamedTag,
  constFunction,
  constNode,
  constNodeUnsafe,
  constNumber,
  constString,
  Frame,
  getTagFromTaggedValue,
  getValueFromTaggedValue,
  isAssignableTo,
  isConcreteTaggedValue,
  isFunction,
  isListLike,
  isTaggedValue,
  isTypedDict,
  isTypedDictLike,
  isUnion,
  list,
  listMaxLength,
  listMinLength,
  listObjectType,
  ListType,
  maybe,
  Node,
  nonNullable,
  nullableTaggable,
  nullableTaggableVal,
  nullableTaggableValue,
  OpFn,
  OpInputs,
  pushFrame,
  skipNullable,
  skipTaggable,
  taggableStrip,
  taggedValue,
  taggedValueTagType,
  taggedValueValueType,
  Type,
  typedDict,
  typedDictPropertyTypes,
  TYPES_WITH_DIGEST,
  union,
  unwrapTaggedValues,
  withGroupTag,
  withJoinTag,
} from '../../model';
import {typedDictPathVal} from '../../model/helpers2';
import {makeOp} from '../../opStore';
import {replaceInputVariables} from '../../refineHelpers';
import {MAX_RUN_LIMIT} from '../../util/constants';
import {docType} from '../../util/docs';
import {opAssetFile} from '../domain/asset';
import {opFileDigest} from '../domain/file';
import {
  makeBasicOp,
  makeConfigurableStandardOp,
  makeTagConsumingStandardOp,
  makeTagGetterOp,
} from '../opKinds';
import {randomlyDownsample} from '../util';
import {opDict} from './literals';
import {splitEscapedString} from './splitEscapedString';
import {tSNE} from './tsne';
import {escapeDots, opPick} from './typedDict';

const listArg0 = {
  arr: {type: 'list' as const, objectType: 'any' as const},
};

const makeListOp = makeBasicOp;

const unwrapConcreteList = (l: any): any[] => {
  if (isConcreteTaggedValue(l)) {
    const tag = getTagFromTaggedValue(l);
    const lst = getValueFromTaggedValue(l);
    if (_.isArray(lst) && tag != null) {
      return lst.map(item => concreteTaggedValue(tag, item));
    }
  }
  return l;
};

// Internally convert grouping/joining on assets to their digest
const toSafeCall = (call: Node<Type>) => {
  const callType = nullableTaggableValue(call.type);
  if (TYPES_WITH_DIGEST.some(t => isAssignableTo(callType, t))) {
    return opFileDigest({file: opAssetFile({asset: call})});
    // TODO: what is this code for. Its slow.
  } else if (isTypedDict(call.type)) {
    const newGroupedNode: Frame = {};
    for (const propertyType in call.type.propertyTypes) {
      if (call.type.propertyTypes[propertyType] != null) {
        newGroupedNode[propertyType] = toSafeCall(
          opPick({
            obj: call,
            key: constString(escapeDots(propertyType)),
          })
        );
      }
    }
    return opDict(newGroupedNode as any);
  } else {
    return call;
  }
};

// TODO: should this be mapped, and we make a different op called len
// that does this behavior?
// At the least, this should be called len or length.
export const opCount = makeListOp({
  name: 'count',
  argTypes: {
    arr: {type: 'list', objectType: 'any'},
  },
  description: `Returns the count of elements in the ${docType('list')}.`,
  argDescriptions: {
    arr: `The ${docType('list')} to count.`,
  },
  returnValueDescription: `The count of elements in the ${docType('list')}.`,
  returnType: inputsTypes => 'number',
  resolver: ({arr}) => arr.length,
});

export const opJoinToStr = makeListOp({
  name: 'joinToStr',
  argTypes: {
    arr: {type: 'list', objectType: 'any'},
    sep: 'string',
  },
  description: `Joins the elements of the ${docType('list')} into a ${docType(
    'string'
  )}.`,
  argDescriptions: {
    arr: `The ${docType('list')} to join.`,
    sep: 'The separator to use between elements.',
  },
  returnValueDescription: `The joined ${docType('string')}.`,
  returnType: inputsTypes => 'string',
  resolver: ({arr, sep}) => {
    // TODO(np): Hack around arr coming in as a list of tagged values
    if (arr.length > 0 && isConcreteTaggedValue(arr[0])) {
      return arr.map(unwrapTaggedValues).join(sep);
    }
    return arr.join(sep);
  },
});

// Not exposed, but we need some kind of mapped count for count of count.
export const opCountInner = makeOp({
  hidden: true,
  name: 'mapcount',
  argTypes: {
    arr: {type: 'list', objectType: {type: 'list', objectType: 'any'}},
  },
  description: `Returns the count of elements in each ${docType(
    'list'
  )} in a ${docType('list')} of ${docType('list')}.`,
  argDescriptions: {
    arr: `The ${docType('list')} of ${docType('list', {
      plural: true,
    })} to count.`,
  },
  returnValueDescription: `The count of elements in each ${docType('list')}`,
  returnType: {type: 'list', objectType: 'number'},
  resolver: inputs => {
    const {arr} = inputs;
    if (
      (_.isArray(arr) && _.isArray(arr[0])) ||
      (arr[0]?._value != null && _.isArray(arr[0]._value))
    ) {
      return arr.map((innerArr: any) => {
        if (innerArr._value != null) {
          return innerArr._value.length;
        }
        return innerArr.length;
      });
    }
    throw new Error('opCountInner: not a list of lists');
  },
});

// TODO: This should produce some new type like undefined when indexing
// out of bounds. tagging undefined should produce undefined (it can't be
// tagged)
export const opIndex = makeListOp({
  name: 'index',
  description: `Retrieve a value from a ${docType('list')} by index`,
  argDescriptions: {
    arr: `The ${docType('list')} to index into.`,
    index: 'The index to retrieve',
  },
  returnValueDescription: `A value from the ${docType('list')}`,
  argTypes: {
    arr: {type: 'list', objectType: 'any'},
    index: {
      type: 'union',
      members: [
        'number',
        {
          type: 'list',
          objectType: {type: 'union', members: ['number', 'none']},
        },
      ],
    },
  },
  renderInfo: {
    type: 'brackets',
  },
  returnType: ({arr, index}) => {
    if (isListLike(index)) {
      return arr;
    }
    return listObjectType(arr);
  },
  resolver: ({arr, index}) => {
    if (_.isArray(index)) {
      return index.map(i => (i == null ? null : arr[i]));
    }
    return arr[index];
  },
  resolverIsSync: true,
});

export const opOffset = makeListOp({
  hidden: true,
  name: 'offset',
  argTypes: {arr: {type: 'list', objectType: 'any'}, offset: 'number'},
  description: `Returns a ${docType(
    'list'
  )} with the first \`offset\` elements removed.`,
  argDescriptions: {
    arr: `The ${docType('list')} to remove elements from.`,
    offset: 'The count of elements to remove.',
  },
  returnValueDescription: `The ${docType(
    'list'
  )} with the first \`offset\` elements removed.`,
  returnType: ({arr}) => arr,
  resolver: ({arr, offset}) => arr.slice(offset),
});

export const opLimit = makeListOp({
  hidden: true,
  name: 'limit',
  argTypes: {arr: {type: 'list', objectType: 'any'}, limit: 'number'},
  description: `Returns a ${docType('list')} of the first \`limit\` elements.`,
  argDescriptions: {
    arr: `The ${docType('list')} to limit.`,
    limit: 'The count of elements to limit to.',
  },
  returnValueDescription: `The ${docType(
    'list'
  )} with the first \`limit\` elements.`,
  returnType: ({arr}, inputNodes) => {
    if (inputNodes.limit.nodeType === 'const') {
      return {
        ...arr,
        maxLength: inputNodes.limit.val,
      };
    }
    return arr;
  },
  resolver: ({arr, limit}) => arr.slice(0, limit),
});

// Exported for PanelFacet :( :(. TODO: fix
export const compareItems = (a: any, b: any): number => {
  if (_.isArray(a)) {
    for (let i = 0; i < a.length; i++) {
      const res = compareItems(a[i], b[i]);
      if (res !== 0) {
        return res;
      }
    }
  } else {
    if (a == null) {
      return -1;
    } else if (b == null) {
      return 1;
    } else if (a < b) {
      return -1;
    } else if (a > b) {
      return 1;
    }
  }
  return 0;
};

export const opSort = makeListOp({
  name: 'sort',
  argTypes: {
    arr: {type: 'list', objectType: 'any'},
    compFn: {
      type: 'function',
      inputTypes: {row: 'any'},
      outputType: {type: 'list', objectType: 'any'},
    },
    columnDirs: {type: 'list', objectType: 'string'},
  },
  description: `Sorts the ${docType('list')}.`,
  argDescriptions: {
    arr: `The ${docType('list')} to sort.`,
    compFn: `A function to apply to each element of the array. The return value is a ${docType(
      'list'
    )} of values to sort by.`,
    columnDirs: `A ${docType(
      'list'
    )} of directions for each element in the value ${docType('list')}`,
  },
  returnValueDescription: `The sorted ${docType('list')}.`,
  returnType: inputTypes => inputTypes.arr,
  resolver: async (
    inputs,
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context,
    engine
  ) => {
    const comparableObjs = await engine().mapNode(
      inputs.compFn,
      unwrapConcreteList(rawInputs.arr),
      true
    );
    return (inputs.arr as any[])
      .map((row, ndx) => {
        return {
          row,
          comparableObj: comparableObjs[ndx],
        };
      })
      .sort((rowA, rowB) => {
        for (let i = 0; i < inputs.columnDirs.length; i++) {
          const comp = compareItems(
            rowA.comparableObj[i],
            rowB.comparableObj[i]
          );
          if (comp !== 0) {
            return comp * (inputs.columnDirs[i] === 'asc' ? 1 : -1);
          }
        }
        return 0;
      })
      .map(item => {
        return item.row;
      });
  },
});

export const opFilter = makeListOp({
  name: 'filter',
  argTypes: {
    arr: {type: 'list', objectType: 'any'},
    filterFn: {
      type: 'function',
      inputTypes: {row: 'any'},
      outputType: maybe('boolean'),
    },
  },
  description: `Filters the ${docType('list')}.`,
  argDescriptions: {
    arr: `The ${docType('list')} to filter.`,
    filterFn: `A function to apply to each element of the ${docType(
      'list'
    )}. The return value is a boolean indicating whether the element should be included in the result.`,
  },
  returnValueDescription: `The filtered ${docType('list')}.`,
  returnType: ({arr}) => arr,
  resolver: async (
    inputs,
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context,
    engine
  ) => {
    const {arr} = inputs;
    const result: any[] = [];
    const predicateResult = await engine().mapNode(
      inputs.filterFn,
      unwrapConcreteList(rawInputs.arr),
      true
    );
    for (let i = 0; i < predicateResult.length; i++) {
      const predRes = predicateResult[i];
      const val = arr[i];
      if (predRes) {
        result.push(val);
      }
    }
    return result;
  },
});

export const opIndexCheckpoint = makeListOp({
  name: 'list-createIndexCheckpointTag',
  hidden: true,
  argTypes: {
    arr: {type: 'list', objectType: 'any'},
  },
  description: `Tags each item in the ${docType('list')} with its index`,
  argDescriptions: {
    arr: `The ${docType('list')} to tag with indices`,
  },
  returnValueDescription: `The ${docType(
    'list'
  )} with each element tagged with its index`,
  returnType: ({arr}) => {
    return list(
      taggedValue(typedDict({indexCheckpoint: 'number'}), listObjectType(arr)),
      listMinLength(arr),
      listMaxLength(arr)
    );
  },
  resolver: async ({arr}, inputTypes) => {
    return arr.map((x, i) => concreteTaggedValue({indexCheckpoint: i}, x));
  },
});

export const opGetIndexCheckpointTag = makeTagGetterOp({
  name: 'tag-indexCheckpoint',
  tagName: 'indexCheckpoint',
  tagType: 'number',
  hidden: true,
});

export const opDropNa = makeConfigurableStandardOp({
  name: 'dropna',
  typeConfig: {dims: 1},
  argTypes: {
    arr: {type: 'list', objectType: 'any'},
  },
  description: `Drops elements of a ${docType('list')} which are null`,
  argDescriptions: {
    arr: `The ${docType('list')} to drop elements from.`,
  },
  returnValueDescription: `The ${docType('list')} with null elements removed.`,
  returnType: ({arr}) => {
    const objectType = arr.objectType;
    const objectTypeTag = isTaggedValue(objectType) ? objectType.tag : null;
    const strippedObjType = isTaggedValue(objectType)
      ? objectType.value
      : objectType;
    const uTypes = (
      isUnion(strippedObjType) ? strippedObjType.members : [strippedObjType]
    ).filter(t => {
      return taggableStrip(t) !== 'none';
    });
    const innerType =
      uTypes.length > 0 ? taggedValue(objectTypeTag, union(uTypes)) : 'none';
    return list(innerType, 0, listMaxLength(arr));
  },
  resolver: async ({arr}) =>
    arr.filter(x => (isConcreteTaggedValue(x) ? x._value : x) != null),
});

export const opMap = makeListOp({
  name: 'map',
  argTypes: {
    ...listArg0,
    mapFn: {
      type: 'function',
      inputTypes: {row: 'any', index: 'number'},
      outputType: 'any',
    },
  },
  description: `Applies a map function to each element in the ${docType(
    'list'
  )}`,
  argDescriptions: {
    arr: `The ${docType('list')} to map over.`,
    mapFn: `A function to apply to each element of the ${docType('list')}.`,
  },
  returnValueDescription: `The ${docType(
    'list'
  )} with each element mapped over.`,
  returnType: ({arr, mapFn}) => {
    if (!isFunction(mapFn)) {
      throw new Error('opMap: expected mapFn to be a function');
    }
    return list(mapFn.outputType, listMinLength(arr), listMaxLength(arr));
  },
  resolver: async (
    inputs,
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context,
    engine
  ) => {
    return await engine().mapNode(
      inputs.mapFn,
      unwrapConcreteList(rawInputs.arr),
      false
    );
  },
  resolveOutputType: async (
    inputTypes,
    node,
    executableNode,
    client,
    stack
  ) => {
    // Warning: This assumes that all members in array have the same type!
    // Not a particularly good assumption. We're not really using opMap
    const inputs = node.fromOp.inputs;
    const mapFn = inputs.mapFn;
    const arrType = inputTypes.arr as ListType;
    if (mapFn.nodeType !== 'const') {
      throw new Error('invalid, mapFn must be const');
    }
    // We union the types of everything in the array!

    const runnableNode = replaceInputVariables(
      executableNode.fromOp.inputs.arr,
      client.opStore
    );
    // We union the types of everything in the array!
    let count = await client.query(opCount({arr: runnableNode}));
    // Put a limit in place for now. We'll expand this later. (25 matches run limit on Weave).
    // TODO: fix
    if (count > MAX_RUN_LIMIT) {
      console.warn('Dropping types in opMap refine');
      count = MAX_RUN_LIMIT;
    }
    const allRefinedProms = _.range(count).map(i =>
      HL.refineNode(
        client,
        mapFn.val,
        pushFrame(stack, {
          row: opIndex({arr: runnableNode, index: constNumber(i)}),
        })
      )
    );
    const allRefined = await Promise.all(allRefinedProms);
    const allUnion = count === 0 ? 'none' : union(allRefined.map(n => n.type));
    return {
      type: 'list',
      objectType: allUnion,
      minLength: arrType.minLength,
      maxLength: arrType.maxLength,
    };
  },
});

export const applyOpToOneOrMany = (
  opFn: OpFn,
  firstArgName: string,
  items: Node,
  extraArgs: OpInputs
) => {
  if (isListLike(items.type)) {
    return opMap({
      arr: items as any,
      mapFn: constFunction({row: listObjectType(items.type)}, ({row}) =>
        opFn({
          [firstArgName]: row,
          ...extraArgs,
        })
      ) as any,
    });
  }
  return opFn({[firstArgName]: items, ...extraArgs});
};

// Creating a duplicate of opMap which
// uses the new generic mapper that passes
// tags down the line. This will apply the function
// to all elements in a multi-dimensional array (or
// just apply the function to the object if not array)
export const opMapEach = makeTagConsumingStandardOp({
  name: 'mapEach',
  hidden: true,
  argTypes: {
    obj: 'any',
    mapFn: {type: 'function', inputTypes: {row: 'any'}, outputType: 'any'},
  },
  description: `Applies a map function to each "cell" in a multi-dimensional ${docType(
    'list'
  )}`,
  argDescriptions: {
    obj: `The ${docType('list')} to map over.`,
    mapFn: `A function to apply to each element of the ${docType('list')}.`,
  },
  returnValueDescription: `The ${docType(
    'list'
  )} with each element mapped over.`,
  returnType: ({obj, mapFn}) => {
    if (!isFunction(mapFn)) {
      throw new Error('opMapEach: expected mapFn to be a function');
    }
    return mapFn.outputType;
  },
  resolver: async (
    {obj, mapFn},
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context,
    engine
  ) =>
    new Promise(async resolve =>
      resolve(
        (
          await engine().executeNodes(
            [
              callFunction(mapFn, {
                row: constNodeUnsafe(inputTypes.obj, obj),
              }),
            ],
            false
          )
        )[0]
      )
    ),
});

function groupKeyObjToString(groupKeyPossibleObj: any): string {
  let groupKey = '';
  if (_.isObject(groupKeyPossibleObj)) {
    groupKey = JSON.stringify(unwrapTaggedValues(groupKeyPossibleObj));
  } else if (groupKeyPossibleObj != null) {
    groupKey = '' + groupKeyPossibleObj;
  }
  return groupKey;
}

export const opGroupby = makeListOp({
  hidden: true,
  name: 'groupby',
  argTypes: {
    arr: {type: 'list', objectType: 'any'},
    groupByFn: {type: 'function', inputTypes: {row: 'any'}, outputType: 'any'},
  },
  description: `Groups elements of a ${docType('list')} based on a function`,
  argDescriptions: {
    arr: `The ${docType('list')} to group.`,
    groupByFn: `A function to group the ${docType('list')} by.`,
  },
  returnValueDescription: `A ${docType('list')} of ${docType(
    'list'
  )}, each containing the elements of the original ${docType(
    'list'
  )} grouped by the function.`,
  returnType: ({arr, groupByFn}) => {
    const objectType = listObjectType(arr);
    if (!isFunction(groupByFn)) {
      throw new Error('invalid group by arg');
    }
    return list(withGroupTag(list(objectType), groupByFn.outputType));
  },
  resolver: async (
    inputs,
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context,
    engine
  ) => {
    const tableRows: any[] = inputs.arr;
    // console.log('OP GROUP BY RESOLVER', tableRows.length);
    const groupByFn = inputs.groupByFn;
    const groupSafeKeyFn =
      groupByFn.nodeType === 'void' ? groupByFn : toSafeCall(groupByFn);
    const localEngine = engine();

    const hasVars = HL.someNodes(
      groupByFn,
      checkNode => checkNode.nodeType === 'var',
      true
    );

    let groupRawKeys: any[];
    let groupSafeKeys: any[];

    if (hasVars) {
      groupRawKeys = await context.trace('groupRawKeys', async () => {
        return (await localEngine.mapNode(groupByFn, tableRows, false)).map(
          (x: any) => x ?? ''
        );
      });
      // console.timeEnd('opGroupBy-rawKeys');

      // console.time('opGroupBy-safeKeys');
      groupSafeKeys = await context.trace('groupSafeKeys', async () => {
        return (await localEngine.mapNode(groupSafeKeyFn, tableRows, true)).map(
          (x: any) => x ?? ''
        );
      });
      // console.timeEnd('opGroupBy-safeKeys');
    } else {
      const groupKey = (await localEngine.executeNodes([groupByFn], false))[0];
      groupRawKeys = Array(tableRows.length).fill(groupKey);
      groupSafeKeys = groupRawKeys;
    }
    // console.time('opGroupBy-final');
    const result: {[key: string]: {_tag: any; _value: any[]}} = {};
    await context.trace('final', async () => {
      for (let i = 0; i < groupRawKeys.length; i++) {
        const groupRawKey = groupRawKeys[i];
        const groupSafeKey: string = groupKeyObjToString(groupSafeKeys[i]);
        const tableRow = tableRows[i];
        if (result[groupSafeKey] == null) {
          result[groupSafeKey] = concreteWithNamedTag(
            'groupKey',
            groupRawKey,
            []
          );
        }
        result[groupSafeKey]._value.push(tableRow);
      }
    });

    // console.timeEnd('opGroupBy-final');
    return Object.values(result);
  },
  resolveOutputType: async (
    inputTypes,
    node,
    executableNode,
    context,
    stack
  ) => {
    // Warning: This assumes that all members in array have the same type!
    // Not a particularly good assumption. We're not really using opMap
    // right now.
    const inputs = node.fromOp.inputs;
    const {arr, groupByFn} = inputs;
    const objectType = inputTypes.arr.objectType;
    if (groupByFn.nodeType !== 'const') {
      throw new Error('invalid, mapFn must be const');
    }
    // return TypeHelpers.list(
    //   TypeHelpers.taggedValue(groupByFn.type.outputType, TypeHelpers.list(objectType))
    // );
    const refined = await HL.refineNode(
      context,
      groupByFn.val,
      pushFrame(stack, {
        row: opIndex({arr, index: constNumber(0)}),
      })
    );
    return list(withGroupTag(list(objectType), refined.type));
  },
});

export const opGroupGroupKey = makeTagGetterOp({
  hidden: true,
  name: 'group-groupkey',
  tagName: 'groupKey',
  tagType: 'any',
});

const listToDict = (
  prev: {[key: string]: number[]},
  curr: any,
  ndx: number
) => {
  if (!prev[curr]) {
    prev[curr] = [];
  }
  prev[curr].push(ndx);
  return prev;
};

// This is an outer join

// This not converted to makeListOp. There are two problems:
// 1. Both arr1 and arr2 need to be nullableTaggable (makeListOp only handles the
//   first argument)
// 2. opJoin returnType enforces that alias1 and alias2 are const nodes.
// TODO: fix
export const opJoin = makeOp({
  name: 'join',
  argTypes: {
    arr1: maybe({type: 'list', objectType: 'any'}),
    arr2: maybe({type: 'list', objectType: 'any'}),
    join1Fn: {type: 'function', inputTypes: {row: 'any'}, outputType: 'any'},
    join2Fn: {type: 'function', inputTypes: {row: 'any'}, outputType: 'any'},
    alias1: 'string',
    alias2: 'string',
    leftOuter: 'boolean',
    rightOuter: 'boolean',
  },
  description: `Joins two ${docType('list')}`,
  argDescriptions: {
    arr1: `The first ${docType('list')} to join.`,
    arr2: `The second ${docType('list')} to join.`,
    join1Fn: `A function that returns the join key for each element in the first ${docType(
      'list'
    )}`,
    join2Fn: `A function that returns the join key for each element in the second ${docType(
      'list'
    )}`,
    alias1: `The alias to use for the first ${docType('list')}.`,
    alias2: `The alias to use for the second ${docType('list')}.`,
    leftOuter: `Whether the output should include rows in the first ${docType(
      'list'
    )} that do not match any rows in the second ${docType('list')}.`,
    rightOuter: `Whether the output should include rows in the second ${docType(
      'list'
    )} that do not match any rows in the first ${docType('list')}.`,
  },
  returnValueDescription: `A ${docType('list')} of ${docType(
    'typedDict'
  )}. Each ${docType(
    'typedDict'
  )} has keys \`alias1\` and \`alias2\`. The values are the rows corresponding to the join.`,
  returnType: inputs => {
    const {arr1, arr2, alias1, alias2, join1Fn, join2Fn} = inputs;
    if (alias1.nodeType !== 'const' || alias2.nodeType !== 'const') {
      // TODO:
      //   this needs to be resolved. Need to refactor to allow async
      //   ops, while still retaining ability to one-shot entire graph.
      throw new Error('opJoin only supports const aliases');
    }
    const arr1ObjectType = listObjectType(arr1.type);
    const arr2ObjectType = listObjectType(arr2.type);
    return list(
      withJoinTag(
        typedDict({
          [alias1.val]: maybe(arr1ObjectType),
          [alias2.val]: maybe(arr2ObjectType),
        }),
        maybe(union([join1Fn.type.outputType, join2Fn.type.outputType]))
      )
    );
  },
  resolver: async (inputs, forwardGraph, forwardOp, context, engine) => {
    const {join1Fn, join2Fn, alias1, alias2, leftOuter, rightOuter} = inputs;
    let arr1 = getValueFromTaggedValue(inputs.arr1);
    let arr2 = getValueFromTaggedValue(inputs.arr2);
    const arr1RowType = listObjectType(
      forwardOp.op.inputs.arr1.type as ListType
    );
    const arr2RowType = listObjectType(
      forwardOp.op.inputs.arr1.type as ListType
    );

    if (arr1 == null) {
      arr1 = [];
    }
    if (arr2 == null) {
      arr2 = [];
    }

    let calls: Node[] = arr1.map((x: any) =>
      callFunction(join1Fn, {
        row: constNodeUnsafe(arr1RowType, x),
      })
    );
    calls = calls
      .concat(
        arr2.map((x: any) =>
          callFunction(join2Fn, {
            row: constNodeUnsafe(arr2RowType, x),
          })
        )
      )
      .map(toSafeCall);

    const joinKeys = (await engine().executeNodes(calls, true)).map(
      groupKeyObjToString
    );
    const arr1JoinKeys = joinKeys.slice(0, arr1.length);
    const arr2JoinKeys = joinKeys.slice(arr1.length);

    const arr1JoinKeyLookup = arr1JoinKeys.reduce(listToDict, {});
    const arr2JoinKeyLookup = arr2JoinKeys.reduce(listToDict, {});
    let allJoinKeys: any[];
    if (leftOuter && rightOuter) {
      allJoinKeys = _.union(arr1JoinKeys, arr2JoinKeys);
    } else if (leftOuter) {
      allJoinKeys = _.uniq(arr1JoinKeys);
    } else if (rightOuter) {
      allJoinKeys = _.uniq(arr2JoinKeys);
    } else {
      allJoinKeys = _.intersection(arr1JoinKeys, arr2JoinKeys);
    }
    const result: any[] = [];
    for (const jk of allJoinKeys) {
      let arr1Indexes: Array<number | null> = arr1JoinKeyLookup[jk];
      let arr2Indexes: Array<number | null> = arr2JoinKeyLookup[jk];
      if (rightOuter && !arr1Indexes) {
        arr1Indexes = [null];
      }
      if (leftOuter && !arr2Indexes) {
        arr2Indexes = [null];
      }
      for (const arr1Index of arr1Indexes) {
        for (const arr2Index of arr2Indexes) {
          result.push(
            concreteTaggedValue(
              {joinKey: jk},
              {
                [alias1]: arr1Index != null ? arr1[arr1Index] : null,
                [alias2]: arr2Index != null ? arr2[arr2Index] : null,
              }
            )
          );
        }
      }
    }
    return result;
  },
  resolveOutputType: async (node, executableNode, context, stack) => {
    const {arr1, arr2, alias1, alias2, join1Fn, join2Fn} = node.fromOp.inputs;
    if (
      alias1.nodeType !== 'const' ||
      alias2.nodeType !== 'const' ||
      join1Fn.nodeType !== 'const' ||
      join2Fn.nodeType !== 'const'
    ) {
      // TODO:
      //   this needs to be resolved. Need to refactor to allow async
      //   ops, while still retaining ability to one-shot entire graph.
      throw new Error('opJoin only supports const aliases & functions');
    }
    const arr1Refined = await HL.refineNode(context, arr1, []);
    const arr2Refined = await HL.refineNode(context, arr2, []);
    const join1FnValRefined = await HL.refineNode(
      context,
      join1Fn.val,
      pushFrame(stack, {
        row: opIndex({arr: arr1Refined, index: constNumber(0)}),
      })
    );
    const join2FnValRefined = await HL.refineNode(
      context,
      join2Fn.val,
      pushFrame(stack, {
        row: opIndex({arr: arr2Refined, index: constNumber(0)}),
      })
    );
    const arr1ObjectType = listObjectType(arr1Refined.type);
    const arr2ObjectType = listObjectType(arr2Refined.type);
    return {
      ...node,
      type: list(
        withJoinTag(
          typedDict({
            [alias1.val]: maybe(arr1ObjectType),
            [alias2.val]: maybe(arr2ObjectType),
          }),
          maybe(union([join1FnValRefined.type, join2FnValRefined.type]))
        )
      ),
    };
  },
});

// const typedDictWithLeafsAsLists = (
//   type: Types.Type,
//   maxLength: number | undefined,
//   tag?: Types.Type
// ): Types.Type => {
//   return OpDefHelpers.nullableSkipTaggable(type, (t, tagType) => {
//     if (!TypeHelpers.isTypedDictLike(t)) {
//       throw new Error(
//         'typedDictWithLeafsAsLists: expected type to be dict-like'
//       );
//     }
//     return TypeHelpers.typedDict(
//       _.mapValues(TypeHelpers.typedDictPropertyTypes(t), propType =>
//         TypeHelpers.isTypedDictLike(TypeHelpers.nullableTaggableValue(propType!))
//           ? typedDictWithLeafsAsLists(
//               propType!,
//               maxLength,
//               // If we unwrapped a tag
//               tagType != null
//                 ? tag != null
//                   ? // pass it down tagged with the current tag
//                     TypeHelpers.taggedValue(tag, tagType)
//                   : tagType
//                 : // otherwise just pass tag through
//                   tag
//             )
//           : TypeHelpers.list(
//               OpDefHelpers.nullableTaggable(
//                 propType!,
//                 unwrappedPropType => unwrappedPropType
//               ),
//               undefined,
//               maxLength
//             )
//       )
//     );
//   });
// };

const typedDictWithListProperties = (
  type: Type,
  maxLength: number | undefined,
  tag?: Type
): Type => {
  return skipTaggable(type, (t, tagType) => {
    if (!isTypedDictLike(t)) {
      throw new Error(
        'typedDictWithListProperties: expected type to be dict-like'
      );
    }
    return typedDict(
      _.mapValues(typedDictPropertyTypes(t), propType =>
        list(propType, undefined, maxLength)
      )
    );
  });
};

const objectPathWithTagsPushedToLeafs = (obj: any, path: string[]): any => {
  return nullableTaggableVal(obj, v =>
    path.length === 1
      ? v[path[0]]
      : objectPathWithTagsPushedToLeafs(v[path[0]], path.slice(1))
  );
};

const addItemAtPath = (
  obj: {[key: string]: any},
  path: string[],
  val: any
): any => {
  let writeTo = obj;
  for (const entry of path.slice(0, path.length - 1)) {
    if (writeTo[entry] == null) {
      writeTo[entry] = {};
    }
    writeTo = writeTo[entry];
  }
  const lastEntry = path[path.length - 1];
  if (writeTo[lastEntry] == null) {
    writeTo[lastEntry] = [];
  }
  if (!_.isArray(writeTo[lastEntry])) {
    // TODO: we need to handle this case (path collision). Need to handle
    // it at the type level as well
    throw new Error('uh-ohhhhhh');
  }
  writeTo[lastEntry].push(val);
};

// Lodash's cloneDeep is super slow, this is way better
const cloneDeepObj = (obj: {[key: string]: any}): any => {
  if (_.isArray(obj)) {
    return [...obj];
  }
  if (!_.isObject(obj)) {
    return obj;
  }
  return _.mapValues(obj, cloneDeepObj);
};

export const opJoinAll = makeOp({
  hidden: false,
  name: 'joinAll',
  argTypes: {
    arrs: {
      type: 'list',
      objectType: {
        type: 'union',
        members: [
          'none',
          {
            type: 'list',
            objectType: {type: 'typedDict', propertyTypes: {}},
          },
        ],
      },
    },
    joinFn: {
      type: 'function',
      inputTypes: {row: {type: 'typedDict', propertyTypes: {}}},
      outputType: 'any',
    },
    outer: 'boolean',
  },
  description: `Join all ${docType('list')} together`,
  argDescriptions: {
    arrs: `${docType('list')} to join`,
    joinFn: `Function to calculate join key`,
    outer: `Whether to include rows from ${docType(
      'list'
    )} which do not match others`,
  },
  returnValueDescription: `A ${docType('list')} of ${docType('typedDict', {
    plural: true,
  })}. Each dictionary contains keys 0 - N, where N is the count of ${docType(
    'list'
  )}.`,
  returnType: inputs => {
    const {arrs, joinFn} = inputs;

    if (!isFunction(joinFn.type)) {
      throw new Error('opJoinAll: expected joinFn to be a function');
    }
    return opJoinAllReturnType(arrs.type, joinFn.type);
  },
  resolver: async (inputs, forwardGraph, forwardOp, context, engine) => {
    const {arrs, joinFn, outer} = inputs;
    const arrsUntagged = getValueFromTaggedValue(arrs)
      .map(getValueFromTaggedValue)
      .filter((arr: any) => arr != null);
    const allColumns = allObjPaths(
      listObjectType(listObjectType(forwardOp.op.inputs.arrs.type)),
      0
    ).map(pt => pt.path);

    const joinFnCalls: Node[] = _.flatMap(
      arrsUntagged,
      (arr, ndx, collection) =>
        arr.map((x: any) =>
          callFunction(joinFn, {
            row: constNodeUnsafe({type: 'typedDict', propertyTypes: {}}, x),
          })
        )
    );
    const safeJoinFnCalls = joinFnCalls.map(toSafeCall);

    const localEngine = engine();

    const joinObjsMerged = await localEngine.executeNodes(joinFnCalls, false);

    const joinKeysMerged = (
      await localEngine.executeNodes(safeJoinFnCalls, true)
    ).map(groupKeyObjToString);

    const joinKeysToObjs = _.fromPairs(
      _.zip(joinKeysMerged, joinObjsMerged).filter(pair => pair[1] != null)
    );

    let pos = 0;
    const joinKeys: string[][] = arrsUntagged.map((val: any[]) => {
      const ret = joinKeysMerged.slice(pos, pos + val.length);
      pos += val.length;
      return ret;
    });

    const joinKeyLookups = joinKeys.map(jk => jk.reduce(listToDict, {}));

    const allJoinKeys = outer
      ? _.union(...joinKeys)
      : _.intersection(...joinKeys);

    const result: any[] = [];
    for (const jk of allJoinKeys) {
      // do not join null values
      if (jk !== '') {
        let newRows: Array<{[column: string]: any[]}> = [];

        joinKeyLookups.forEach((jkl, ndx) => {
          const arrIndexes = jkl[jk] ?? [];
          if (newRows.length === 0) {
            arrIndexes.forEach((arrIndex: number) => {
              const newRow: {[column: string]: any} = {};
              const arrItem = arrsUntagged[ndx][arrIndex];
              allColumns.forEach(colPath => {
                const val = objectPathWithTagsPushedToLeafs(arrItem, colPath);
                addItemAtPath(newRow, colPath, val);
              });
              newRows.push(newRow);
            });
            if (arrIndexes.length === 0 && outer) {
              const newRow: {[column: string]: any} = {};
              const arrItem = null;
              allColumns.forEach(colPath => {
                const val = objectPathWithTagsPushedToLeafs(arrItem, colPath);
                addItemAtPath(newRow, colPath, val);
              });
              newRows.push(newRow);
            }
          } else {
            const newRowsCopy: Array<{[column: string]: any[]}> = [];
            newRows.forEach(oldRow => {
              arrIndexes.forEach((arrIndex: number) => {
                const newRow: {[column: string]: any[]} = cloneDeepObj(oldRow);
                const arrItem = arrsUntagged[ndx][arrIndex];
                allColumns.forEach(colPath => {
                  const val = objectPathWithTagsPushedToLeafs(arrItem, colPath);
                  addItemAtPath(newRow, colPath, val);
                });
                newRowsCopy.push(newRow);
              });
              if (arrIndexes.length === 0 && outer) {
                const newRow: {[column: string]: any[]} = cloneDeepObj(oldRow);
                const arrItem = null;
                allColumns.forEach(colPath => {
                  const val = objectPathWithTagsPushedToLeafs(arrItem, colPath);
                  addItemAtPath(newRow, colPath, val);
                });
                newRowsCopy.push(newRow);
              }
            });
            newRows = newRowsCopy;
          }
        });
        newRows.forEach(row => {
          result.push(
            concreteTaggedValue({joinKey: jk, joinObj: joinKeysToObjs[jk]}, row)
          );
        });
      }
    }

    return result;
  },
  resolveOutputType: async (node, executableNode, client) => {
    // Same as returnType, except we get the length of input array
    // and set that as the maxLength of the arrays we return at
    // each key
    const count = await client.query(
      opCount({arr: executableNode.fromOp.inputs.arrs})
    );
    const inputs = node.fromOp.inputs;
    const type = opJoinAllReturnType(
      inputs.arrs.type as any,
      inputs.joinFn.type as any,
      count
    );
    return {...node, type};
  },
});

export const opGetJoinedJoinObj = makeTagGetterOp({
  hidden: true,
  name: 'tag-joinObj',
  tagName: 'joinObj',
  tagType: 'any',
});

// TODO: opConcat doesn't handle nullable taggable cases yet.
const opConcatArgs = {
  arr: {
    type: 'list' as const,
    objectType: {
      type: 'union' as const,
      members: [
        'none' as const,
        {type: 'list' as const, objectType: 'any' as const},
      ],
    },
  },
};

export const opConcat = makeBasicOp<typeof opConcatArgs>({
  name: 'concat',
  argTypes: opConcatArgs,
  description: `Concatenate all ${docType('list', {
    plural: true,
  })} together`,
  argDescriptions: {
    arr: `${docType('list')} of ${docType('list', {
      plural: true,
    })} to concatenate`,
  },
  returnValueDescription: `Concatenated ${docType('list')}`,
  returnType: ({arr}) => {
    const innerType = nonNullable(arr.objectType);
    // If you are concatenating lists of different types (eg. concat tables with
    // different columns), then the resulting list needs to be
    // a union of the inner types of those lists
    if (isUnion(innerType)) {
      if (!innerType.members.every(isListLike)) {
        throw new Error(
          'opConcat: expected all members of inner type to be list-like'
        );
      }
      return list(union(innerType.members.map(listObjectType)));
    } else if (isTaggedValue(innerType)) {
      const innerTypeValue = taggedValueValueType(innerType);
      const innerTypeTag = taggedValueTagType(innerType);
      const innerTypeValueInnerType = listObjectType(innerTypeValue);

      return list(taggedValue(innerTypeTag, innerTypeValueInnerType));
    }
    return innerType;
  },
  resolver: async inputs => {
    return _.concat(
      [],
      ...inputs.arr
        .map(val => {
          // Should we have a generic way to do this in situations where we
          // need to preserve the tag of the outer array?
          if (isConcreteTaggedValue(val) && _.isArray(val._value)) {
            return val._value.map(v => concreteTaggedValue(val._tag, v));
          }
          return val;
        })
        .filter((item: any) => item != null)
    );
  },
});

// Not yet public
// TODO: This doesn't properly handle tagged values in the types
export const opUnnest = makeOp({
  hidden: true,
  name: 'unnest',
  argTypes: {
    arr: maybe({
      type: 'list',
      objectType: {type: 'typedDict', propertyTypes: {}},
    }),
  },
  description: `Unnest a ${docType('list')} of ${docType(
    'typedDict'
  )} such that the result is a ${docType('list')} of ${docType(
    'typedDict'
  )} where each ${docType('typedDict')}'s properties are non-lists.`,
  argDescriptions: {
    arr: `${docType('list')} of ${docType('typedDict')} to unnest`,
  },
  returnValueDescription: `Unnested ${docType('list')}`,
  returnType: inputs => {
    const {arr} = inputs;
    const objType = listObjectType(arr.type);
    if (!isTypedDictLike(objType)) {
      throw new Error('opUnnest: expected arr object type to be typedDict');
    }
    const newPropertyTypes: {[key: string]: Type} = {};
    const propTypes = typedDictPropertyTypes(objType);
    for (const key of Object.keys(propTypes)) {
      const propertyType = propTypes[key];
      if (propertyType == null) {
        throw new Error('opUnnest: expected all property types to be non-null');
      }
      newPropertyTypes[key] = isListLike(propertyType)
        ? listObjectType(propertyType)
        : propertyType;
    }
    return maybe({
      type: 'list',
      objectType: {type: 'typedDict', propertyTypes: newPropertyTypes},
    });
  },
  resolver: async (inputs, forwardGraph, forwardOp, context) => {
    const arrNode = forwardOp.outputNode.node.fromOp.inputs.arr;
    const objType = listObjectType(arrNode.type);
    const keys: string[] = [];
    const propTypes = typedDictPropertyTypes(objType);
    for (const key of Object.keys(propTypes)) {
      const propertyType = propTypes[key];
      if (isListLike(propertyType)) {
        keys.push(key);
      }
    }

    // getValueFromTaggedValue is wrong, should retain tags
    // TODO
    const arr: Array<{[key: string]: any}> = getValueFromTaggedValue(
      inputs.arr
    );

    if (arr == null) {
      return null;
    }

    const result: Array<{[key: string]: any}> = [];
    for (const row of arr) {
      const distributedRow: {[key: string]: any} = {};
      for (const key of Object.keys(row)) {
        const val = row[key];
        if (!keys.includes(key)) {
          distributedRow[key] = val;
        }
      }
      if (keys.length > 0) {
        const arraysToUnnest: any[] = [];
        for (const key of keys) {
          const innerArr = row[key];
          // Distributed tags over array
          if (isConcreteTaggedValue(innerArr)) {
            arraysToUnnest.push(
              (innerArr._value as any)?.map((innerR: any) =>
                concreteTaggedValue(innerArr._tag, innerR)
              )
            );
          } else {
            arraysToUnnest.push(innerArr);
          }
        }
        for (const zipped of _.zip(...arraysToUnnest)) {
          const newRow = {...distributedRow};
          for (const [i, key] of keys.entries()) {
            newRow[key] = zipped[i];
          }
          result.push(newRow);
        }
      } else {
        result.push(distributedRow);
      }
    }
    return result;
  },
});

const comparableObjectType = union(['string', 'number', 'boolean']);
export const opContains = makeListOp({
  name: 'contains',
  argTypes: {
    arr: {type: 'list', objectType: comparableObjectType},
    element: comparableObjectType,
  },
  description: `Check if a ${docType('list')} contains a ${docType('string')}`,
  argDescriptions: {
    arr: `${docType('list')} to check`,
    element: `${docType('string')} to check for`,
  },
  returnValueDescription: `True if the ${docType('list')} contains <element>`,
  returnType: inputTypes => 'boolean',
  resolver: inputs => {
    const {arr} = inputs;
    let {element} = inputs;
    // TODO(np): Hack around element coming in as tagged value
    if (isConcreteTaggedValue(element)) {
      element = unwrapTaggedValues(element);
    }
    // TODO(np): Hack around arr coming in as array of tagged values
    if (arr.length > 0 && isConcreteTaggedValue(arr[0])) {
      return arr.some(e => unwrapTaggedValues(e) === element);
    }
    return arr.indexOf(element) !== -1;
  },
});

export const opUnique = makeListOp({
  hidden: true,
  name: 'unique',
  argTypes: {arr: {type: 'list', objectType: 'any'}},
  description: `Compute unique elements`,
  argDescriptions: {
    arr: `${docType('list')} to process`,
  },
  returnValueDescription: `Return unique elements of ${docType('list')}`,
  returnType: inputTypes => inputTypes.arr,
  resolver: inputs => {
    // console.log('OP UNIQUE', inputs.arr.map(JSON.stringify);
    return _.uniqWith(inputs.arr, _.isEqual);
  },
});

const concreteTagSafeFlatten = (arrOrObj: any, parentTag?: any): any => {
  if (isConcreteTaggedValue(arrOrObj)) {
    const arrOrObjTag = getTagFromTaggedValue(arrOrObj);
    if (parentTag != null && arrOrObjTag != null) {
      parentTag = concreteTaggedValue(parentTag, arrOrObjTag);
    } else if (arrOrObjTag != null) {
      parentTag = arrOrObjTag;
    }
    arrOrObj = getValueFromTaggedValue(arrOrObj);
  }

  if (!_.isArray(arrOrObj)) {
    if (parentTag != null) {
      return concreteTaggedValue(parentTag, arrOrObj);
    } else {
      return arrOrObj;
    }
  } else {
    return _.flatMap(arrOrObj, item => concreteTagSafeFlatten(item, parentTag));
  }
};

const tagSafeFlatten = (arrOrObj: Type, parentTag?: Type): Type => {
  if (isTaggedValue(arrOrObj)) {
    const arrOrObjTag = arrOrObj.tag;
    if (parentTag != null && arrOrObjTag != null) {
      parentTag = taggedValue(parentTag, arrOrObjTag);
    } else if (arrOrObjTag != null) {
      parentTag = arrOrObjTag;
    }
    arrOrObj = arrOrObj.value;
  }

  if (!isListLike(arrOrObj)) {
    if (parentTag != null) {
      return taggedValue(parentTag, arrOrObj);
    } else {
      return arrOrObj;
    }
  } else {
    return tagSafeFlatten(listObjectType(arrOrObj), parentTag);
  }
};

// TODO: convert to makeListOp
export const opFlatten = makeOp({
  hidden: true,
  name: 'flatten',
  argTypes: {arr: {type: 'list', objectType: 'any'}},
  description: `Flatten a ${docType('list')} of ${docType('list', {
    plural: true,
  })}`,
  argDescriptions: {
    arr: `${docType('list')} of ${docType('list', {
      plural: true,
    })} to flatten`,
  },
  returnValueDescription: `Flattened ${docType('list')}`,
  returnType: inputTypes => list(tagSafeFlatten(inputTypes.arr.type)),
  resolver: inputs => concreteTagSafeFlatten(inputs.arr),
});
export function opJoinAllReturnType(
  arrsType: {
    type: 'list';
    objectType: {
      type: 'union';
      members: Array<
        | 'none'
        | {type: 'list'; objectType: {type: 'typedDict'; propertyTypes: {}}}
      >;
    };
  },
  joinFnType: {
    type: 'function';
    inputTypes: {row: {type: 'typedDict'; propertyTypes: {}}};
    outputType: 'any';
  },
  count?: number
): Type {
  // This function uses very verbose names b/c it is hard to keep track of
  // what is what in this function.
  /* Worst Case Situation:
  Notation:
  Maybe<M#, TYPE> -> maybe ID and inner type (ID also indicates if it is nullable)
  Tagged<T#, TYPE> -> tag ID and inner type
  List<L#, TYPE> -> list ID and inner type - ID also indicates length of list
  Dict<D#, {...}> -> dict ID and inner type

  Maybe<M1,
    Tagged<T1,
      List<L1,
        Maybe<M2,
          Tagged<T2,
            List<L2,
              Maybe<M3,
                Tagged<T3,
                  Dict<D1,{
                    col_1: C1T,
                    ...
                  }>
                >
              >
            >
          >
        >
      >
    >
  >


  Becomes:
  Maybe<M1,
    Tagged<T1,
      List<LX,
        Tagged<JOIN_KEY,
          Dict<D1,{
            col_1: List<L1,
              Maybe<M2,
                Tagged<T2,
                  Maybe<M3,
                    Tagged<T3,
                      C1T
                    >
                  >
                >
              >
            >,
            ...
          }>
        >
      >
    >
  >

  Which reduces to:
  Maybe<M1,
    Tagged<T1,
      List<LX,
        Tagged<JOIN_KEY,
          Dict<D1,{
            col_1: List<L1,
              Maybe<M2 or M3,
                Tagged<Tagged<T2,T3>,
                  C1T
                >
              >
            >,
            ...
          }>
        >
      >
    >
  >

  Finally, business logic removes optionality of the inner keys:
  Maybe<M1,
    Tagged<T1,
      List<LX,
        Tagged<JOIN_KEY,
          Dict<D1,{
            col_1: List<L1,
              Tagged<Tagged<T2,T3>,
                C1T
              >
            >,
            ...
          }>
        >
      >
    >
  >
  */
  const listOfListsType = arrsType;
  const finalJoinAllType = nullableTaggable(
    listOfListsType,
    listOfListsStrippedType => {
      if (!isListLike(listOfListsStrippedType)) {
        throw new Error('opJoinAllReturnType: arrsType must be a list');
      }
      const innerListType = listObjectType(listOfListsStrippedType);
      const finalRowType = skipNullable(innerListType, innerListNonNullType => {
        const finalRowTypeLayer2 = skipTaggable(
          innerListNonNullType,
          (innerListNonNullValueType, innerListNonNullTagType) => {
            if (!isListLike(innerListNonNullValueType)) {
              throw new Error(
                'opJoinAllReturnType: innerListNonNullValueType must be a list, found ' +
                  typeToString(innerListNonNullValueType)
              );
            }
            const innerListRowType = listObjectType(innerListNonNullValueType);
            const finalRowTypeLayer3 = skipNullable(
              innerListRowType,
              innerListRowNonNullType =>
                skipTaggable(
                  innerListRowNonNullType,
                  (
                    innerListRowNonNullValueType,
                    innerListRowNonNullTagType
                  ) => {
                    if (!isTypedDictLike(innerListRowNonNullValueType)) {
                      throw new Error(
                        'opJoinAllReturnType: innerListRowNonNullValueType object type must be a typed dict, found ' +
                          typeToString(innerListRowNonNullValueType)
                      );
                    }

                    const keyTypeWrapper = (keyType: Type): Type => {
                      return taggedValue(
                        innerListNonNullTagType,
                        taggedValue(innerListRowNonNullTagType, keyType)
                      );
                    };

                    const innerListRowNonNullValueTypeProperties =
                      typedDictPropertyTypes(innerListRowNonNullValueType);

                    const wrappedInnerListRowNonNullValueTypeProperties =
                      _.mapValues(
                        innerListRowNonNullValueTypeProperties,
                        keyTypeWrapper
                      );

                    const typeOfEachRowWithTagsPushedToValues = typedDict(
                      wrappedInnerListRowNonNullValueTypeProperties
                    );
                    const typeOfEachJoinRowWithListsAsValues =
                      typedDictWithListProperties(
                        typeOfEachRowWithTagsPushedToValues,
                        count
                      );
                    return typeOfEachJoinRowWithListsAsValues;
                  }
                )
            );
            return finalRowTypeLayer3;
          }
        );
        return finalRowTypeLayer2;
      });
      const taggedListType = list(
        withJoinTag(finalRowType, joinFnType.outputType)
      );
      return taggedListType;
    }
  );
  return finalJoinAllType;
}

const projectableType = {
  type: 'list' as const,
  objectType: maybe({
    type: 'list' as const,
    objectType: maybe('number' as const),
  }),
};
const projectableToRawList = (input: any[]): any[][] => {
  return input.map(i =>
    i == null ? null : getValueFromTaggedValue(i).map(getValueFromTaggedValue)
  );
};

const ensureNDimensions = (
  input: any[][],
  n: number,
  nLimit: number
): any[][] => {
  n = Math.min(n, nLimit);
  return input.map(row => {
    if (row == null) {
      row = [];
    }
    if (row.length < n) {
      return row.concat(Array(n - row.length).fill(0));
    } else if (row.length === n) {
      return row;
    } else {
      return row.slice(0, nLimit);
    }
  });
};

const wrapConcreteNewListElementsWithOldListElementTags = (
  newArr: any[],
  oldArr: any[]
) => {
  if (newArr.length !== oldArr.length) {
    throw new Error('Expected both arrays to be of the same length');
  }
  return newArr.map((newElem, i) => {
    const oldElem = oldArr[i];
    if (isConcreteTaggedValue(oldElem)) {
      return concreteTaggedValue(getTagFromTaggedValue(oldElem), newElem);
    } else {
      return newElem;
    }
  });
};

const replaceListElementType = (
  newElementType: Type,
  sourceListType: ListType
): ListType => {
  const innerType = listObjectType(sourceListType);
  const minLength = listMinLength(sourceListType);
  const maxLength = listMaxLength(sourceListType);
  if (isTaggedValue(innerType)) {
    newElementType = taggedValue(taggedValueTagType(innerType), newElementType);
  }
  return list(newElementType, minLength, maxLength);
};

export const opListTSNE = makeConfigurableStandardOp({
  name: 'list-tSNE',
  hidden: true,
  argTypes: {
    arr: maybe(projectableType),
    dimensions: 'number',
    perplexity: 'number',
    learningRate: 'number',
    iterations: 'number',
  },
  typeConfig: {
    dims: 2,
  },
  description: `Run t-SNE on a ${docType('list')} of ${docType('list', {
    plural: true,
  })} of numbers (vectors)`,
  argDescriptions: {
    arr: `List of ${docType('list', {plural: true})} to run t-SNE on`,
    dimensions: 'Number of dimensions to reduce to',
    perplexity: 'Perplexity of the t-SNE algorithm',
    learningRate: 'Learning rate of the t-SNE algorithm',
    iterations: 'Number of iterations of the t-SNE algorithm',
  },
  returnValueDescription: `A t-SNE projected ${docType('list')} of ${docType(
    'list',
    {plural: true}
  )} of numbers (vectors).`,
  returnType: ({arr}) => {
    return replaceListElementType(list('number'), arr as ListType);
  },
  resolver: async ({arr, dimensions, perplexity, learningRate, iterations}) => {
    // This ensures that we do not continuously hog the main thread
    const deadline = Date.now() + 10000;
    const data = ensureNDimensions(
      projectableToRawList(arr),
      dimensions,
      MAX_PROJECTION_DIMENSIONS
    );
    const tsne = new tSNE({
      epsilon: learningRate,
      perplexity,
      dim: dimensions,
    });
    tsne.initDataRaw(data);
    for (let k = 0; k < iterations; k++) {
      if (Date.now() > deadline) {
        break;
      }
      tsne.step();
    }
    return wrapConcreteNewListElementsWithOldListElementTags(
      tsne.getSolution(),
      arr
    );
  },
});

export const opListUMAP = makeConfigurableStandardOp({
  name: 'list-UMAP',
  hidden: true,
  argTypes: {
    arr: maybe(projectableType),
    dimensions: 'number',
    neighbors: 'number',
    minDist: 'number',
    spread: 'number',
  },
  typeConfig: {
    dims: 2,
  },
  description: `Run UMAP on a ${docType('list')} of ${docType('list', {
    plural: true,
  })} of numbers (vectors)`,
  argDescriptions: {
    arr: `List of ${docType('list', {plural: true})} to run UMAP on`,
    dimensions: 'Number of dimensions to reduce to',
    neighbors: 'Number of neighbors to use',
    minDist: 'Minimum distance between neighbors',
    spread: 'Spread of the neighborhood',
  },
  returnValueDescription: `A UMAP projected ${docType('list')} of ${docType(
    'list',
    {plural: true}
  )} of numbers (vectors)`,
  returnType: ({arr}) => {
    return replaceListElementType(list('number'), arr as ListType);
  },
  resolver: async ({arr, dimensions, neighbors, minDist, spread}) => {
    const {UMAP} = await import('umap-js');
    const data = ensureNDimensions(
      projectableToRawList(arr),
      dimensions,
      MAX_PROJECTION_DIMENSIONS
    );
    const umap = new UMAP({
      nComponents: dimensions,
      // Just let the algorithm decide automatically
      // nEpochs: epochs,
      nNeighbors: Math.min(neighbors, data.length - 1),
      minDist,
      spread,
    });
    return wrapConcreteNewListElementsWithOldListElementTags(
      umap.fit(data),
      arr
    );
  },
});

// tslint:disable-next-line: ban-types
const withDisabledConsoleLog = <FT extends Function>(fn: FT) => {
  const log = console.log;
  console.log = () => {};
  const res = fn();
  console.log = log;
  return res;
};
export const opListPCA = makeConfigurableStandardOp({
  name: 'list-PCA',
  hidden: true,
  argTypes: {
    arr: maybe(projectableType),
    dimensions: 'number',
  },
  typeConfig: {
    dims: 2,
  },
  description: `Run PCA on a ${docType('list')} of ${docType('list', {
    plural: true,
  })} of numbers (vectors)`,
  argDescriptions: {
    arr: `List of ${docType('list', {plural: true})} to run PCA on`,
    dimensions: 'Number of dimensions to reduce to',
  },
  returnValueDescription: `A PCA projected ${docType('list')} of ${docType(
    'list',
    {plural: true}
  )} of numbers (vectors)`,
  returnType: ({arr}) => {
    return replaceListElementType(list('number'), arr as ListType);
  },
  resolver: async ({arr, dimensions}) => {
    const PCA = await import('pca-js');
    const data = ensureNDimensions(
      projectableToRawList(arr),
      dimensions,
      MAX_PROJECTION_DIMENSIONS
    );
    const vectors: any[] = withDisabledConsoleLog(() =>
      PCA.getEigenVectors(data)
    );
    return wrapConcreteNewListElementsWithOldListElementTags(
      PCA.transpose(
        PCA.computeAdjustedData(data, ...vectors.slice(0, dimensions))
          .adjustedData
      ),
      arr
    );
  },
});

// This is used by the projection converter. Should not be exposed. This is a good
// use case to understand the how we can work towards a more general approach to op
// configs as the arg types are purposely the same as the converter.

const MAX_PROJECTION_RECORDS = 1500;
const MAX_PROJECTION_DIMENSIONS = 50;
export const opTable2DProjection = makeConfigurableStandardOp({
  name: 'table-2DProjection',
  hidden: true,
  typeConfig: {
    dims: 1,
  },
  argTypes: {
    table: {
      type: 'list' as const,
      objectType: maybe({
        type: 'typedDict' as const,
        propertyTypes: {},
      }),
    },
    projectionAlgorithm: 'string',
    inputCardinality: 'string',
    inputColumnNames: {type: 'list' as const, objectType: 'string'},
    algorithmOptions: {
      type: 'typedDict',
      propertyTypes: {
        tsne: {
          type: 'typedDict' as const,
          propertyTypes: {
            perplexity: 'number',
            learningRate: 'number',
            iterations: 'number',
          },
        },
        pca: {type: 'typedDict' as const, propertyTypes: {}},
        umap: {
          type: 'typedDict' as const,
          propertyTypes: {
            neighbors: 'number',
            minDist: 'number',
            spread: 'number',
          },
        },
      },
    },
  },
  description: `Apply a 2D projection to a ${docType('list')} of ${docType(
    'typedDict',
    {plural: true}
  )}`,
  argDescriptions: {
    table: `${docType('list')} of ${docType('typedDict', {
      plural: true,
    })} to project`,
    projectionAlgorithm: 'Algorithm to use (pca, tsne, umap)',
    inputCardinality: 'Cardinality of the input data (single, multiple)',
    inputColumnNames: 'List of column names to project',
    algorithmOptions: 'Options for the algorithm',
  },
  returnValueDescription: `${docType('list')} of ${docType('typedDict', {
    plural: true,
  })} with projected columns`,
  returnType: ({table}) => {
    return replaceListElementType(
      typedDict({
        projection: typedDict({
          x: 'number',
          y: 'number',
        }),
        source: listObjectType(table),
      }),
      table as ListType
    );
  },
  resolver: async (
    {
      table,
      inputCardinality,
      inputColumnNames,
      algorithmOptions,
      projectionAlgorithm,
    },
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context,
    engine
  ) => {
    table = _.sampleSize(table, MAX_PROJECTION_RECORDS);

    if (inputColumnNames.length === 0 || table.length < 2) {
      return wrapConcreteNewListElementsWithOldListElementTags(
        table.map((row, ndx) => ({
          projection: {
            x: 0,
            y: 0,
          },
          source: table[ndx],
        })),
        table
      );
    }

    if (inputCardinality === 'single') {
      inputColumnNames = [inputColumnNames[0]];
    } else {
      // Artificially constrain the size of the projection to a reasonable number.
      // This can likely be lifted if/when use case demands it and we make a more performant
      // backend
      inputColumnNames = _.sampleSize(
        inputColumnNames,
        MAX_PROJECTION_DIMENSIONS
      );
    }

    const embeddings = table.map(row => {
      if (inputCardinality === 'single') {
        return typedDictPathVal(
          getValueFromTaggedValue(row),
          splitEscapedString(inputColumnNames[0])
        );
      } else {
        return inputColumnNames.map(col =>
          typedDictPathVal(
            getValueFromTaggedValue(row),
            splitEscapedString(col)
          )
        );
      }
    });

    const embeddingNode = constNode<typeof projectableType>(
      projectableType,
      embeddings
    );
    const castedAlgorithmOptions = algorithmOptions as any;
    let projectionOp: Node;
    if (projectionAlgorithm === 'pca') {
      projectionOp = opListPCA({
        arr: embeddingNode,
        dimensions: constNumber(2),
      });
    } else if (projectionAlgorithm === 'tsne') {
      projectionOp = opListTSNE({
        arr: embeddingNode,
        dimensions: constNumber(2),
        perplexity: constNumber(castedAlgorithmOptions.tsne.perplexity),
        learningRate: constNumber(castedAlgorithmOptions.tsne.learningRate),
        iterations: constNumber(castedAlgorithmOptions.tsne.iterations),
      });
    } else if (projectionAlgorithm === 'umap') {
      projectionOp = opListUMAP({
        arr: embeddingNode,
        dimensions: constNumber(2),
        neighbors: constNumber(castedAlgorithmOptions.umap.neighbors),
        minDist: constNumber(castedAlgorithmOptions.umap.minDist),
        spread: constNumber(castedAlgorithmOptions.umap.spread),
      });
    } else {
      throw new Error('Invalid projectionAlgorithm');
    }

    const projections = (await engine().executeNodes([projectionOp]))[0];
    const res = projections.map((p: number[], ndx: number) => ({
      projection: {
        x: p[0],
        y: p[1],
      },
      source: table[ndx],
    }));

    return wrapConcreteNewListElementsWithOldListElementTags(res, table);
  },
});

export const opTableProjection2D = makeConfigurableStandardOp({
  name: 'table-projection2D',
  hidden: true,
  typeConfig: {
    dims: 1,
  },
  argTypes: {
    table: {
      type: 'list' as const,
      objectType: maybe({
        type: 'typedDict' as const,
        propertyTypes: {},
      }),
    },
    projectionAlgorithm: 'string',
    inputCardinality: 'string',
    inputColumnNames: {type: 'list' as const, objectType: 'string'},
    algorithmOptions: {
      type: 'typedDict',
      propertyTypes: {
        tsne: {
          type: 'typedDict' as const,
          propertyTypes: {
            perplexity: 'number',
            learningRate: 'number',
            iterations: 'number',
          },
        },
        pca: {type: 'typedDict' as const, propertyTypes: {}},
        umap: {
          type: 'typedDict' as const,
          propertyTypes: {
            neighbors: 'number',
            minDist: 'number',
            spread: 'number',
          },
        },
      },
    },
  },
  description: `Apply a 2D projection to a ${docType('list')} of ${docType(
    'typedDict',
    {plural: true}
  )}`,
  argDescriptions: {
    table: `${docType('list')} of ${docType('typedDict', {
      plural: true,
    })} to project`,
    projectionAlgorithm: 'Algorithm to use (pca, tsne, umap)',
    inputCardinality: 'Cardinality of the input data (single, multiple)',
    inputColumnNames: 'List of column names to project',
    algorithmOptions: 'Options for the algorithm',
  },
  returnValueDescription: `${docType('list')} of ${docType('typedDict', {
    plural: true,
  })} with projected columns`,
  returnType: ({table}) => {
    return replaceListElementType(
      typedDict({
        projection: typedDict({
          x: 'number',
          y: 'number',
        }),
        source: listObjectType(table),
      }),
      table as ListType
    );
  },
  resolver: async (
    {
      table,
      inputCardinality,
      inputColumnNames,
      algorithmOptions,
      projectionAlgorithm,
    },
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context,
    engine
  ) => {
    throw new Error('not implemented in js');
  },
});

export const opRange = makeOp({
  // hidden: true,
  name: 'range',
  argTypes: {
    start: 'int',
    stop: 'int',
    step: 'int',
  },
  description:
    'Return a list of numbers from start to stop, incrementing by step.',
  renderInfo: {type: 'function'},
  argDescriptions: {
    start: 'Number to start at',
    stop: 'Number to stop at, not included in result',
    step: 'Amount to increment or decrement by on each iteration',
  },
  returnValueDescription: 'A list of numbers',
  returnType: inputsTypes => list('number'),
  resolver: ({start, stop, step}) => {
    const result: number[] = [];
    for (let i = start; i < stop; i += step) {
      result.push(i);
    }
    return result;
  },
});

export const opRandomlyDownsample = makeListOp({
  name: 'randomlyDownsample',
  hidden: true,
  argTypes: {
    arr: {type: 'list', objectType: 'any'},
    n: 'number',
  },
  description: `Randomly downsamples the ${docType(
    'list'
  )} to n elements, preserving order.`,
  argDescriptions: {
    arr: `The ${docType('list')} to sample.`,
    n: 'The number of elements to sample. Must be greater than 0 and less than the length of the list.',
  },
  returnValueDescription: `The sampled ${docType('list')}.`,
  returnType: ({arr}) => arr,
  resolver: ({arr, n}) => {
    return randomlyDownsample(arr, n);
  },
});

function gaussian(mean: number, std: number, n: number): number[] {
  const samples = [];
  for (let i = 0; i < n; i++) {
    let u = 0;
    let v = 0;
    while (u === 0) {
      u = Math.random();
    } // Converting [0,1) to (0,1)
    while (v === 0) {
      v = Math.random();
    }
    let sample = Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
    sample = sample * std + mean;
    samples.push(sample);
  }
  return samples;
}

// sample from a gaussian
export const opRandomGaussian = makeOp({
  name: 'gauss',
  argTypes: {
    mean: 'number',
    std: 'number',
    n: 'number',
  },
  description: `Sample from a gaussian distribution with mean and standard deviation.`,
  argDescriptions: {
    mean: 'The mean of the distribution.',
    std: 'The standard deviation of the distribution.',
  },
  returnValueDescription: `A sample from the gaussian distribution.`,
  returnType: () => ({type: 'list', objectType: 'number'}),
  resolver: ({mean, std, n}) => {
    return gaussian(mean, std, n);
  },
  renderInfo: {type: 'function'},
});
