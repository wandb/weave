import * as _ from 'lodash';
import numeral from 'numeral';

import callFunction from '../../callers';
import {
  constNumber,
  getValueFromTaggedValue,
  list,
  maybe,
  nullableSkipTaggable,
  numberBin,
  skipTaggable,
  varNode,
} from '../../model';
import {docType} from '../../util/docs';
import {notEmpty} from '../../util/obj';
import * as OpKinds from '../opKinds';
import {opDict} from './literals';

// Dimension reducing

const makeNumbersOp = OpKinds.makeBasicDimDownOp;

const numbersArgTypes = {
  numbers: {
    type: 'list' as const,
    objectType: {
      type: 'union' as const,
      members: ['none' as const, 'number' as const],
    },
  },
};

export const opNumbersSum = makeNumbersOp({
  name: 'numbers-sum',
  argTypes: numbersArgTypes,
  description: `Sum of ${docType('number', {plural: true})}`,
  argDescriptions: {
    numbers: `${docType('list')} of ${docType('number', {
      plural: true,
    })} to sum`,
  },
  returnValueDescription: `Sum of ${docType('number', {plural: true})}`,
  returnType: inputTypes => 'number',
  resolver: ({numbers}) => _.sum(numbers.filter(num => num != null)),
});

export const opNumbersAvg = makeNumbersOp({
  name: 'numbers-avg',
  argTypes: numbersArgTypes,
  description: `Average of ${docType('number', {plural: true})}`,
  argDescriptions: {
    numbers: `${docType('list')} of ${docType('number', {
      plural: true,
    })} to average`,
  },
  returnValueDescription: `Average of ${docType('number', {
    plural: true,
  })}`,
  returnType: inputTypes => 'number',
  resolver: ({numbers}) => {
    const nonNull = numbers.filter(num => num != null);
    return _.sum(nonNull) / nonNull.length;
  },
});

export const opNumbersArgMax = makeNumbersOp({
  name: 'numbers-argmax',
  argTypes: numbersArgTypes,
  description: `Finds the index of maximum ${docType('number')}`,
  argDescriptions: {
    numbers: `${docType('list')} of ${docType('number', {
      plural: true,
    })} to find the index of maximum ${docType('number')}`,
  },
  returnValueDescription: `Index of maximum ${docType('number')}`,
  returnType: inputTypes => 'number',
  resolver: ({numbers}) => {
    return _.indexOf(numbers, _.max(numbers));
  },
});

export const opNumbersArgMin = makeNumbersOp({
  name: 'numbers-argmin',
  argTypes: numbersArgTypes,
  description: `Finds the index of minimum ${docType('number')}`,
  argDescriptions: {
    numbers: `${docType('list')} of ${docType('number', {
      plural: true,
    })} to find the index of minimum ${docType('number')}`,
  },
  returnValueDescription: `Index of minimum ${docType('number')}`,
  returnType: inputTypes => 'number',
  resolver: ({numbers}) => {
    return _.indexOf(numbers, _.min(numbers));
  },
});

export const opNumbersStddev = makeNumbersOp({
  name: 'numbers-stddev',
  argTypes: numbersArgTypes,
  description: `Standard deviation of ${docType('number', {
    plural: true,
  })}`,
  argDescriptions: {
    numbers: `${docType('list')} of ${docType('number', {
      plural: true,
    })} to calculate the standard deviation`,
  },
  returnValueDescription: `Standard deviation of ${docType('number', {
    plural: true,
  })}`,
  returnType: inputTypes => 'number',
  resolver: ({numbers}) => {
    const nonNull = numbers.filter(notEmpty);
    const avg = _.sum(nonNull) / nonNull.length;
    return Math.sqrt(
      _.sum(nonNull.map(v => (v - avg) * (v - avg))) / nonNull.length
    );
  },
});

export const opNumbersMin = makeNumbersOp({
  name: 'numbers-min',
  argTypes: numbersArgTypes,
  description: `Minimum number`,
  argDescriptions: {
    numbers: `${docType('list')} of ${docType('number', {
      plural: true,
    })} to find the minimum ${docType('number')}`,
  },
  returnValueDescription: `Minimum ${docType('number')}`,
  returnType: inputTypes => 'number',
  resolver: ({numbers}) => _.min(numbers.filter(num => num != null)),
});

export const opNumbersMax = makeNumbersOp({
  name: 'numbers-max',
  argTypes: numbersArgTypes,
  description: `Maximum number`,
  argDescriptions: {
    numbers: `${docType('list')} of ${docType('number', {
      plural: true,
    })} to find the maximum ${docType('number')}`,
  },
  returnValueDescription: `Maximum ${docType('number')}`,
  returnType: inputTypes => 'number',
  resolver: ({numbers}) => _.max(numbers.filter(num => num != null)),
});

// Dimension preserving

const makeNumberOp = OpKinds.makeBinaryStandardOp;

const numberArgTypes = {
  lhs: 'number' as const,
  rhs: {
    type: 'union' as const,
    members: ['none' as const, 'number' as const],
  },
};

export const opNumberAdd = makeNumberOp('+', {
  name: 'number-add',
  argTypes: numberArgTypes,
  description: `Add two ${docType('number', {plural: true})}`,
  argDescriptions: {
    lhs: `First ${docType('number')}`,
    rhs: `Second ${docType('number')}`,
  },
  returnValueDescription: `Sum of two ${docType('number', {
    plural: true,
  })}`,
  returnType: inputTypes => skipTaggable(inputTypes.rhs, t => t),
  resolver: ({lhs, rhs}) => (rhs == null ? null : lhs + rhs),
});

export const opNumberSub = makeNumberOp('-', {
  name: 'number-sub',
  argTypes: numberArgTypes,
  description: `Subtract a ${docType('number')} from another`,
  argDescriptions: {
    lhs: `${docType('number')} to subtract from`,
    rhs: `${docType('number')} to subtract`,
  },
  returnValueDescription: `Difference of two ${docType('number', {
    plural: true,
  })}`,
  returnType: inputTypes => skipTaggable(inputTypes.rhs, t => t),
  resolver: ({lhs, rhs}) => (rhs == null ? null : lhs - rhs),
});

export const opNumberMult = makeNumberOp('*', {
  name: 'number-mult',
  argTypes: numberArgTypes,
  description: `Multiply two ${docType('number', {plural: true})}`,
  argDescriptions: {
    lhs: `First ${docType('number')}`,
    rhs: `Second ${docType('number')}`,
  },
  returnValueDescription: `Product of two ${docType('number', {
    plural: true,
  })}`,
  returnType: inputTypes => skipTaggable(inputTypes.rhs, t => t),
  resolver: ({lhs, rhs}) => (rhs == null ? null : lhs * rhs),
});

export const opNumberDiv = makeNumberOp('/', {
  name: 'number-div',
  argTypes: numberArgTypes,
  description: `Divide a ${docType('number')} by another`,
  argDescriptions: {
    lhs: `${docType('number')} to divide`,
    rhs: `${docType('number')} to divide by`,
  },
  returnValueDescription: `Quotient of two ${docType('number', {
    plural: true,
  })}`,
  returnType: inputTypes => skipTaggable(inputTypes.rhs, t => t),
  resolver: ({lhs, rhs}) => (rhs == null ? null : lhs / rhs),
});

export const opNumberFloorDiv = makeNumberOp('//', {
  name: 'number-floorDiv',
  argTypes: numberArgTypes,
  description: `Divide a ${docType(
    'number'
  )} by another then rounds down to the nearest whole number`,
  argDescriptions: {
    lhs: `${docType('number')} to divide`,
    rhs: `${docType('number')} to divide by`,
  },
  returnValueDescription: `Truncated quotient of two ${docType('number', {
    plural: true,
  })}`,
  returnType: inputTypes => skipTaggable(inputTypes.rhs, t => t),
  resolver: ({lhs, rhs}) => (rhs == null ? null : Math.floor(lhs / rhs)),
});

export const opNumberModulo = makeNumberOp('%', {
  name: 'number-modulo',
  argTypes: numberArgTypes,
  description: `Divide a ${docType('number')} by another and return remainder`,
  argDescriptions: {
    lhs: `${docType('number')} to divide`,
    rhs: `${docType('number')} to divide by`,
  },
  returnValueDescription: `Modulo of two ${docType('number', {
    plural: true,
  })}`,
  returnType: inputTypes => skipTaggable(inputTypes.rhs, t => t),
  resolver: ({lhs, rhs}) => (rhs == null ? null : lhs % rhs),
});

export const opNumberPowBinary = makeNumberOp('**', {
  name: 'number-powBinary',
  argTypes: numberArgTypes,
  description: `Raise a ${docType('number')} to an exponent`,
  argDescriptions: {
    lhs: `Base ${docType('number')}`,
    rhs: `Exponent ${docType('number')}`,
  },
  returnValueDescription: `The base ${docType('number', {
    plural: true,
  })} raised to nth power`,
  returnType: inputTypes => skipTaggable(inputTypes.rhs, t => t),
  resolver: ({lhs, rhs}) => (rhs == null ? null : Math.pow(lhs, rhs)),
});

// Hidden so binary form is preferred
export const opNumberPow = OpKinds.makeStandardOp({
  hidden: true,
  name: 'number-pow',
  argTypes: numberArgTypes,
  description: `Raise a base ${docType('number')} by an exponent ${docType(
    'number'
  )}`,
  argDescriptions: {
    base: `Base ${docType('number')}`,
    exp: `Exponent ${docType('number')}`,
  },
  renderInfo: {
    type: 'function',
  },
  returnValueDescription: `The base ${docType('number', {
    plural: true,
  })} raised to nth power`,
  returnType: inputTypes => skipTaggable(inputTypes.rhs, t => t),
  resolver: ({lhs, rhs}) => (rhs == null ? null : Math.pow(lhs, rhs)),
});

// Comparison

export const opNumberEqual = OpKinds.makeEqualOp({
  name: 'number-equal',
  argType: 'number',
});

export const opNumberNotEqual = OpKinds.makeNotEqualOp({
  name: 'number-notEqual',
  argType: 'number',
});

export const opNumberLess = makeNumberOp('<', {
  name: 'number-less',
  argTypes: numberArgTypes,
  description: `Check if a ${docType('number')} is less than another`,
  argDescriptions: {
    lhs: `${docType('number')} to compare`,
    rhs: `${docType('number')} to compare to`,
  },
  returnValueDescription: `Whether the first ${docType(
    'number'
  )} is less than the second`,
  returnType: inputTypes =>
    nullableSkipTaggable(inputTypes.rhs, t => 'boolean'),
  resolver: ({lhs, rhs}) => (rhs == null ? null : lhs < rhs),
});

export const opNumberGreater = makeNumberOp('>', {
  name: 'number-greater',
  argTypes: numberArgTypes,
  description: `Check if a ${docType('number')} is greater than another`,
  argDescriptions: {
    lhs: `${docType('number')} to compare`,
    rhs: `${docType('number')} to compare to`,
  },
  returnValueDescription: `Whether the first ${docType(
    'number'
  )} is greater than the second`,
  returnType: inputTypes =>
    nullableSkipTaggable(inputTypes.rhs, t => 'boolean'),
  resolver: ({lhs, rhs}) => (rhs == null ? null : lhs > rhs),
});

export const opNumberLessEqual = makeNumberOp('<=', {
  name: 'number-lessEqual',
  argTypes: numberArgTypes,
  description: `Check if a ${docType(
    'number'
  )} is less than or equal to another`,
  argDescriptions: {
    lhs: `${docType('number')} to compare`,
    rhs: `${docType('number')} to compare to`,
  },
  returnValueDescription: `Whether the first ${docType(
    'number'
  )} is less than or equal to the second`,
  returnType: inputTypes =>
    nullableSkipTaggable(inputTypes.rhs, t => 'boolean'),
  resolver: ({lhs, rhs}) => (rhs == null ? null : lhs <= rhs),
});

export const opNumberGreaterEqual = makeNumberOp('>=', {
  name: 'number-greaterEqual',
  argTypes: numberArgTypes,
  description: `Check if a ${docType(
    'number'
  )} is greater than or equal to another`,
  argDescriptions: {
    lhs: `${docType('number')} to compare`,
    rhs: `${docType('number')} to compare to`,
  },
  returnValueDescription: `Whether the first ${docType(
    'number'
  )} is greater than or equal to the second`,
  returnType: inputTypes =>
    nullableSkipTaggable(inputTypes.rhs, t => 'boolean'),
  resolver: ({lhs, rhs}) => (rhs == null ? null : lhs >= rhs),
});

/// // Not yet ready for production
// These will need to be refactored to use opTypes style functions (as above).
// Also we don't want all of them. Ex we should probably have a single round()
// that takes a second argument. And the bins functions are definitely not ready.

export const opNumberFloor = OpKinds.makeStandardOp({
  hidden: true,
  name: 'number-floor',
  argTypes: {in: 'number'},
  description: `Round a ${docType('number')} down to the nearest integer`,
  argDescriptions: {in: `${docType('number')} to round`},
  returnValueDescription: `Rounded ${docType('number')}`,
  returnType: inputTypes => 'number',
  resolver: inputs => {
    return Math.floor(inputs.in);
  },
});

export const opNumberRoundThousand = OpKinds.makeStandardOp({
  hidden: true,
  name: 'number-roundthousand',
  argTypes: {in: 'number'},
  description: `Round a ${docType('number')} to the nearest thousand`,
  argDescriptions: {in: `${docType('number')} to round`},
  returnValueDescription: `Rounded ${docType('number')}`,
  returnType: inputTypes => 'number',
  resolver: inputs => {
    return Math.round(inputs.in / 1000) * 1000;
  },
});

export const opNumberRoundHundredth = OpKinds.makeStandardOp({
  hidden: true,
  name: 'number-roundHundredth',
  argTypes: {in: 'number'},
  description: `Round a number to the nearest hundredth`,
  argDescriptions: {in: 'Number to round'},
  returnValueDescription: `Rounded number`,
  returnType: inputTypes => 'number',
  resolver: inputs => {
    return Math.round(inputs.in * 100) / 100;
  },
});

export const opNumberRoundTenth = OpKinds.makeStandardOp({
  hidden: true,
  name: 'number-roundtenth',
  argTypes: {in: 'number'},
  description: `Round a ${docType('number')} to the nearest tenth`,
  argDescriptions: {in: `${docType('number')} to round`},
  returnValueDescription: `Rounded ${docType('number')}`,
  returnType: inputTypes => 'number',
  resolver: inputs => {
    return Math.round(inputs.in * 10) / 10;
  },
});

export const opNumberToFixed = OpKinds.makeStandardOp({
  hidden: true,
  name: 'number-toFixed',
  argTypes: {in: 'number', digits: 'number'},
  description: `Round a ${docType('number')} to a fixed ${docType(
    'number'
  )} of digits`,
  argDescriptions: {
    in: `${docType('number')} to round`,
    digits: `${docType('number')} of digits to round to`,
  },
  returnValueDescription: `Rounded ${docType('number')}`,
  returnType: inputTypes => 'number',
  resolver: inputs => Number(inputs.in.toFixed(inputs.digits)),
});

export const opNumberToString = OpKinds.makeStandardOp({
  name: 'number-toString',
  argTypes: {in: 'number'},
  description: `Convert a ${docType('number')} to a string`,
  argDescriptions: {in: 'Number to convert'},
  returnValueDescription: `String representation of the ${docType('number')}`,
  returnType: inputTypes => 'string',
  resolver: inputs => String(inputs.in),
});

export const opNumberToByteString = OpKinds.makeStandardOp({
  hidden: true,
  name: 'number-toByteString',
  argTypes: {in: 'number'},
  description: `Convert a ${docType('number')} to a byte string`,
  argDescriptions: {in: 'Number to convert'},
  returnValueDescription: `String representation of the ${docType(
    'number'
  )} interpreted as bytes.`,
  returnType: inputTypes => 'string',
  resolver: inputs => String(numeral(inputs.in).format('0.00b')),
});

export const opNumberBinsFixed = OpKinds.makeStandardOp({
  hidden: true,
  name: 'root_number-binsfixed',
  renderInfo: {type: 'function'},
  argTypes: {step: 'number'},
  description: '', // TODO: Add description if unhidden
  argDescriptions: {
    step: '', // TODO: Add description if unhidden
  },
  returnValueDescription: '', // TODO: Add description if unhidden
  returnType: inputTypes => ({
    type: 'function',
    inputTypes: {row: maybe('number')},
    outputType: numberBin,
  }),
  resolver: inputs => {
    const mult = 1 / inputs.step;
    return opDict({
      start: opNumberDiv({
        lhs: opNumberFloor({
          in: opNumberMult({
            lhs: varNode('number', 'row'),
            rhs: constNumber(mult),
          }) as any,
        }),
        rhs: constNumber(mult),
      }),
      stop: opNumberAdd({
        lhs: opNumberDiv({
          lhs: opNumberFloor({
            in: opNumberMult({
              lhs: varNode('number', 'row'),
              rhs: constNumber(mult),
            }) as any,
          }),
          rhs: constNumber(mult),
        }),
        rhs: constNumber(inputs.step),
      }),
    } as any);
  },
});

export const opNumbersBinEqual = OpKinds.makeBasicOp({
  hidden: true,
  name: 'numbers-binsequal',
  argTypes: {
    arr: {
      type: 'list',
      objectType: {type: 'union', members: ['none', 'number']},
    },
    bins: 'number',
  },
  description: '', // TODO: Add description if unhidden
  argDescriptions: {
    arr: '', // TODO: Add description if unhidden
    bins: '', // TODO: Add description if unhidden
  },
  returnValueDescription: '', // TODO: Add description if unhidden
  returnType: inputTypes => ({
    type: 'function',
    inputTypes: {row: 'number'},
    outputType: numberBin,
  }),
  resolver: async (
    inputs,
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context,
    engine
  ) => {
    // What do we do? Do we min max here? But we should
    // be doing that with ops.... :(
    const bins = inputs.bins;
    const arrMin = _.min(inputs.arr as number[]) ?? 0;
    const arrMax = _.max(inputs.arr as number[]) ?? 0;
    const step = (arrMax - arrMin) / bins;

    const binOp = opNumberBinsFixed({step: constNumber(step)});
    const result = (await engine().executeNodes([binOp], true))[0];
    return result;
  },
});

export const opNumberBin = OpKinds.makeStandardOp({
  hidden: true,
  name: 'number-bin',
  argTypes: {
    in: maybe('number'),
    binFn: {
      type: 'function',
      inputTypes: {row: 'number'},
      outputType: numberBin,
    },
  },
  description: '', // TODO: Add description if unhidden
  argDescriptions: {
    in: '', // TODO: Add description if unhidden
    binFn: '', // TODO: Add description if unhidden
  },
  returnValueDescription: '', // TODO: Add description if unhidden
  returnType: inputTypes => numberBin,
  resolver: async (
    inputs,
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context,
    engine
  ) => {
    const input = getValueFromTaggedValue(inputs.in);
    const binFn = inputs.binFn;
    // console.time('opGroupBy-construct-calls');
    const frame = {
      ...context.frame,
      row: constNumber(input),
    };
    const call = callFunction(binFn, frame);

    const result = (await engine().executeNodes([call], true))[0];
    return result;
  },
});

// Not yet exposed
export const opNumberRange = OpKinds.makeStandardOp({
  hidden: true,
  name: 'root_number-range',
  argTypes: {
    // start: 'number',
    stop: 'number',
  },
  description: `Create a range of ${docType('number', {
    plural: true,
  })} from 0 to stop`,
  argDescriptions: {
    stop: 'Max value',
  },
  returnValueDescription: `Range of ${docType('number', {
    plural: true,
  })} from 0 to stop`,
  returnType: inputTypes => list('number'),
  resolver: inputs => {
    return _.range(0, inputs.stop);
  },
});

export const opNumberAbs = OpKinds.makeStandardOp({
  name: 'number-abs',
  renderInfo: {
    type: 'function',
  },
  argTypes: {n: 'number'},
  description: `Calculates the absolute value of a ${docType('number')}`,
  argDescriptions: {n: `A ${docType('number')}`},
  returnValueDescription: `The absolute value of the ${docType('number')}`,
  returnType: inputTypes => 'number',
  resolver: ({n}) => Math.abs(n),
});

// Not yet exposed
export const opNumberSin = OpKinds.makeStandardOp({
  name: 'number-sin',
  renderInfo: {
    type: 'function',
  },
  argTypes: {n: 'number'},
  description: `Calculates the sine of a ${docType('number')} in radians`,
  argDescriptions: {n: 'Radians to calculate the sine of'},
  returnValueDescription: `Sine of the ${docType('number')}`,
  returnType: inputTypes => 'number',
  resolver: ({n}) => Math.sin(n),
});

export const opNumberCos = OpKinds.makeStandardOp({
  name: 'number-cos',
  renderInfo: {
    type: 'function',
  },
  argTypes: {n: 'number'},
  description: `Calculates the cosine of a ${docType('number')} in radians`,
  argDescriptions: {n: 'Radians to calculate the cosine of'},
  returnValueDescription: `Sine of the ${docType('number')}`,
  returnType: inputTypes => 'number',
  resolver: ({n}) => Math.cos(n),
});

const timestampSecondUpperBound = 60 * 60 * 24 * 365 * 1000; // first 1000 years
const timestampMilliSecondUpperBound = timestampSecondUpperBound * 1000;
const timestampMicroSecondUpperBound = timestampMilliSecondUpperBound * 1000;
const timestampNanoSecondUpperBound = timestampMicroSecondUpperBound * 1000;

// we will start by making this a simple millisecond converter, but
// in the future we can make the unit customizable.
export const opNumberToTimestamp = OpKinds.makeStandardOp({
  name: 'number-toTimestamp',
  argTypes: {val: 'number'},
  description: `Converts a ${docType('number')} to a ${docType(
    'timestamp'
  )}. Values less than ${timestampSecondUpperBound} will be converted to seconds, values less than ${timestampMilliSecondUpperBound} will be converted to milliseconds, values less than ${timestampMicroSecondUpperBound} will be converted to microseconds, and values less than ${timestampNanoSecondUpperBound} will be converted to nanoseconds.`,
  argDescriptions: {val: 'Number to convert to a timestamp'},
  returnValueDescription: `Timestamp`,
  returnType: inputTypes => ({
    type: 'timestamp',
    unit: 'ms',
  }),
  resolver: ({val}) => {
    if (val < timestampSecondUpperBound) {
      return Math.floor(val * 1000);
    } else if (val < timestampMilliSecondUpperBound) {
      return Math.floor(val);
    } else if (val < timestampMicroSecondUpperBound) {
      return Math.floor(val / 1000);
    } else if (val < timestampNanoSecondUpperBound) {
      return Math.floor(val / 1000 / 1000);
    } else {
      return null;
    }
  },
});

export const opNumberNegate = OpKinds.makeStandardOp({
  name: 'number-negate',
  argTypes: {
    val: 'number',
  },
  renderInfo: {
    type: 'unary',
    repr: '-',
  },
  description: `Negate a ${docType('number')}`,
  argDescriptions: {val: 'Number to negate'},
  returnValueDescription: `A ${docType('number')}`,
  returnType: inputTypes => 'number',
  resolver: ({val}) => val * -1,
});

// Helpful for debugging
export const opThrowError = OpKinds.makeStandardOp({
  hidden: true,
  name: 'throwError',
  argTypes: {obj: 'any'},
  description: `Throw an error`,
  argDescriptions: {obj: 'any'},
  returnValueDescription: `Returns nothing; always throws an error`,
  returnType: inputTypes => 'string',
  resolver: inputs => {
    throw new Error('Weave Error');
  },
});
