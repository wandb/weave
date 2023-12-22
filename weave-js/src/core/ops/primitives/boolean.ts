import {
  getValueFromTaggedValue,
  maybe,
  Node,
  skipTaggable,
  Type,
  typedDictPropertyTypes,
  union,
} from '../../model';
import {makeEqualOp, makeNotEqualOp, makeStandardOp} from '../opKinds';
import {opDict} from './literals';

const makeBooleanOp = makeStandardOp;

const booleanArgTypes = {
  lhs: 'boolean' as const,
  rhs: {
    type: 'union' as const,
    members: ['none' as const, 'boolean' as const],
  },
};

export const opAnd = makeBooleanOp({
  name: 'and',
  argTypes: booleanArgTypes,
  renderInfo: {
    type: 'binary',
    repr: 'and',
  },
  description: 'Returns the logical `and` of the two values',
  argDescriptions: {
    lhs: 'First binary value',
    rhs: 'Second binary value',
  },
  returnValueDescription: 'The logical `and` of the two values',
  returnType: inputTypes => skipTaggable(inputTypes.rhs, t => t),
  resolver: ({lhs, rhs}) => (rhs == null ? null : lhs && rhs),
});

export const opOr = makeBooleanOp({
  name: 'or',
  argTypes: booleanArgTypes,
  renderInfo: {
    type: 'binary',
    repr: 'or',
  },
  description: 'Returns the logical `or` of the two values',
  argDescriptions: {
    lhs: 'First binary value',
    rhs: 'Second binary value',
  },
  returnValueDescription: 'The logical `or` of the two values',
  returnType: inputTypes => skipTaggable(inputTypes.rhs, t => t),
  resolver: ({lhs, rhs}) => (rhs == null ? null : lhs || rhs),
});

export const opNot = makeBooleanOp({
  name: 'boolean-not',
  argTypes: {
    bool: 'boolean' as const,
  },
  renderInfo: {
    type: 'unary',
    repr: '!',
  },
  description: 'Returns the logical inverse of the value',
  argDescriptions: {
    bool: 'The boolean value',
  },
  returnValueDescription: 'The logical inverse of the value',
  returnType: inputTypes => 'boolean',
  resolver: ({bool}) => !bool,
});

export const opBooleanEqual = makeEqualOp({
  hidden: true,
  name: 'boolean-equal',
  argType: 'boolean',
});

export const opBooleanNotEqual = makeNotEqualOp({
  hidden: true,
  name: 'boolean-notEqual',
  argType: 'boolean',
});

// Low-level op for conditional logic. See Weave Python docs for an explanation
export const opCond = makeStandardOp({
  hidden: true,
  name: 'cond',
  argTypes: {
    cases: {
      type: 'dict' as const,
      objectType: {
        type: 'union' as const,
        members: ['none' as const, 'boolean' as const],
      },
    },
    results: {
      type: 'dict' as const,
      objectType: 'any' as const,
    },
  },
  description:
    'Return first Object.values(result)[i] for which Object.values(cases)[i] is True.',
  argDescriptions: {
    cases: 'Boolean conditions',
    results: 'Value options',
  },
  returnType: inputTypes =>
    maybe(union(Object.values(typedDictPropertyTypes(inputTypes.results)))),
  resolver: ({cases, results}) => {
    for (const k of Object.keys(cases)) {
      if (getValueFromTaggedValue(cases[k])) {
        return results[k];
      }
    }
    return null;
  },
});

interface Case {
  when: Node<'boolean'>;
  then: Node<'any'>;
}

// A switch-like statement in Weave. This is just a friendlier wrapper
// around the opCond call signature.
export const weaveCase = (cases: Case[]) => {
  const caseDict: {[key: string]: Node<'boolean'>} = {};
  const resultDict: {[key: string]: Node<'any'>} = {};
  cases.forEach((c, i) => {
    const key = i.toString();
    caseDict[key] = c.when;
    resultDict[key] = c.then;
  });
  return opCond({
    cases: opDict(caseDict as any),
    results: opDict(resultDict as any),
  });
};

// An if-like statement in Weave. Another friendly wrapper around opCond.
export const weaveIf = (
  condition: Node<Type>,
  whenTrue: Node<Type>,
  whenFalse: Node<Type>
) => {
  return opCond({
    cases: opDict({
      whenTrue: condition,
      whenFalse: opNot({bool: condition}),
    } as any),
    results: opDict({whenTrue, whenFalse} as any),
  });
};
