import {skipTaggable} from '../../model';
import {makeEqualOp, makeNotEqualOp, makeStandardOp} from '../opKinds';

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
