import * as _ from 'lodash';

import {
  concreteTaggedValue,
  isConcreteTaggedValue,
  isDict,
  isSimpleTypeShape,
  isTaggedValue,
  isTypedDict,
  isTypedDictLike,
  isUnion,
  list,
  mappableNullableTaggable,
  mappableNullableTaggableVal,
  maybe,
  oneOrMany,
  taggedValue,
  typedDict,
  typedDictPropertyTypes,
  union,
} from '../../model';
import {typedDictPathType, typedDictPathVal} from '../../model/helpers2';
import type {TaggedValueType, Type, TypedDictType} from '../../model/types';
import {makeOp} from '../../opStore';
import {docType} from '../../util/docs';
import {notEmpty} from '../../util/obj';
import {makeStandardOp} from '../opKinds';
import {splitEscapedString} from './splitEscapedString';
export const escapeDots = (s: string) => {
  return s.replace(new RegExp('\\.', 'g'), '\\.');
};

export const unEscapeDots = (s: string) => {
  return s.replace(/\\\./g, '.');
};

const makeObjectOp = makeStandardOp;

const objectArgTypes = {
  obj: typedDict({}),
  key: {
    type: 'union' as const,
    members: ['none' as const, 'string' as const],
  },
};

const opPickArgs: Parameters<typeof makeObjectOp>['0'] = {
  name: 'pick',
  argTypes: objectArgTypes,
  renderInfo: {type: 'brackets'},
  returnType: (inputTypes, inputs) => {
    const {obj: objType} = inputTypes;
    const {key} = inputs;

    if (key.nodeType !== 'const') {
      // Should probably use unknown for cases like this.
      if (isDict(objType)) {
        return maybe(
          (objType as any) /* weird because we already think its a typedDict*/
            .objectType
        );
      } else if (isTypedDictLike(objType)) {
        return maybe(
          union(Object.values(typedDictPropertyTypes(objType)).filter(notEmpty))
        );
      }
      throw new Error('opPick: expected dict-like object');
    }

    // TODO(sl): Hacky way to handle when key is a union>..
    // Disallowed per input types but this is to support the equivalent of a keyof op
    // against a typedDict.
    if (isUnion(key.type)) {
      const keys = [];
      for (const mem of key.type.members) {
        if (isSimpleTypeShape(mem) || mem.type !== 'const') {
          throw new Error(
            'cannot handle non-const members of union type for key arg'
          );
        }
        keys.push(mem.val);
      }
      if (!isTypedDictLike(objType)) {
        throw new Error('cannot calculate keyof type for non-typedDict');
      }
      const propertyTypes = typedDictPropertyTypes(objType);
      const valTypes = keys.map(k => propertyTypes[k] ?? 'none');
      return union(valTypes);
    }
    const keyValue = key.val;

    const subKeys = splitEscapedString(keyValue);

    return typedDictPathType(objType, subKeys);
  },
  description: `Selects a value from a ${docType('typedDict')} by key`,
  argDescriptions: {
    obj: `The input ${docType('typedDict')}`,
    key: `The key for the value to select`,
  },
  returnValueDescription: `Value at the given key`,
  resolverIsSync: true,
  resolver: inputs => {
    if (inputs.key == null) {
      // This shouldn't happen because we're a standardOp, but we have an
      // incorrect type here.
      return null;
    }
    const subKeys = splitEscapedString(inputs.key);
    return typedDictPathVal(inputs.obj, subKeys);
  },
};
export const opPick = makeObjectOp(opPickArgs);
export const opDictPick = makeObjectOp({
  // check arg names
  ...opPickArgs,
  name: 'dict-pick',
  hidden: true,
});

export const opValues = makeOp({
  hidden: true,
  name: 'typedDict-values',
  argTypes: {
    obj: maybe(oneOrMany(maybe(typedDict({})))),
  },
  returnType: inputs => {
    const {obj} = inputs;
    const objType = obj.type;

    return mappableNullableTaggable(objType, t => {
      const propertyTypes = Object.values(typedDictPropertyTypes(t));
      if (propertyTypes.length === 0) {
        return list('invalid');
      }
      return list(union(propertyTypes));
    });
  },
  description: `Returns the values of all the keys in a ${docType(
    'typedDict'
  )}`,
  argDescriptions: {
    obj: `The input ${docType('typedDict')}`,
  },
  returnValueDescription: `List of the ${docType('typedDict')} values`,
  resolver: async inputs => {
    return mappableNullableTaggableVal(inputs.obj, t => {
      return Object.values(t);
    });
  },
});

// Not yet public, needs generic implementation
export const opObjectKeyTypes = makeObjectOp({
  hidden: true,
  name: 'object-keytypes',
  argTypes: {
    obj: {type: 'typedDict', propertyTypes: {}},
  },
  returnType: ({obj}) => list(typedDict({key: 'string', type: 'type'})),
  description: `Returns a ${docType(
    'typedDict'
  )} of the key types of the input ${docType('typedDict')}`,
  argDescriptions: {
    obj: `The input ${docType('typedDict')}`,
  },
  returnValueDescription: `${docType(
    'typedDict'
  )} with same keys as the input, and values corresponding to the ${docType(
    'type'
  )}.`,
  resolver: async (
    {obj},
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context
  ) => {
    const objType = forwardOp.outputNode.node.fromOp.inputs.obj.type;
    return _.map(typedDictPropertyTypes(objType), (type, key) => ({
      key,
      type,
    }));
  },
});

const extractTaggedPropertyTypes = (
  type: TaggedValueType<TypedDictType> | TypedDictType
): TypedDictType['propertyTypes'] => {
  let pTypes: TypedDictType['propertyTypes'] = {};
  if (isTaggedValue(type)) {
    const dict = type.value as TypedDictType;
    const propTypes = typedDictPropertyTypes(dict);
    pTypes = _.fromPairs(
      Object.keys(propTypes).map(k => {
        return [k, taggedValue(type.tag, propTypes[k] as Type)];
      })
    );
  } else if (isTypedDict(type)) {
    pTypes = typedDictPropertyTypes(type);
  }
  return pTypes;
};

const extractConcreteProperties = (obj: any): any => {
  if (isConcreteTaggedValue(obj)) {
    const dict = obj._value as any;
    const tag = obj._tag as any;
    obj = _.fromPairs(
      Object.keys(dict).map(k => {
        return [k, concreteTaggedValue(tag, dict[k])];
      })
    );
  }
  return obj;
};

// Not yet public, needs generic implementation
// We call this from tableState.ts but only in the code path
// used by PanelPlot, which is not yet exposed
export const opMerge = makeOp({
  description: `Merges two ${docType('typedDict', {plural: true})}`,
  argDescriptions: {
    lhs: `The base ${docType('typedDict')}`,
    rhs: `The ${docType('typedDict')} to merge into the base`,
  },
  returnValueDescription: `A new ${docType(
    'typedDict'
  )} with the values from both inputs`,
  hidden: true,
  name: 'merge',
  argTypes: {
    lhs: {type: 'typedDict', propertyTypes: {}},
    rhs: {type: 'typedDict', propertyTypes: {}},
  },
  returnType: inputs => {
    return {
      type: 'typedDict',
      propertyTypes: {
        ...extractTaggedPropertyTypes(inputs.lhs.type),
        ...extractTaggedPropertyTypes(inputs.rhs.type),
      },
    };
  },
  resolver: inputs => {
    return {
      ...extractConcreteProperties(inputs.lhs),
      ...extractConcreteProperties(inputs.rhs),
    };
  },
});
