import levenshtein from 'js-levenshtein';

import {nullableSkipTaggable} from '../../model';
import {docType} from '../../util/docs';
import {
  makeBinaryStandardOp,
  makeEqualOp,
  makeNotEqualOp,
  makeStandardOp,
} from '../opKinds';

export const opStringEqual = makeEqualOp({
  name: 'string-equal',
  argType: 'string',
});

export const opStringNotEqual = makeNotEqualOp({
  name: 'string-notEqual',
  argType: 'string',
});

const makeStringOp = makeStandardOp;

export const opStringIn = makeStringOp({
  hidden: true,
  name: 'string-in',
  argTypes: {
    lhs: {type: 'union', members: ['none', 'string']},
    rhs: {
      type: 'union',
      members: ['none', {type: 'list', objectType: 'string'}],
    },
  },
  description: `Checks if a ${docType('string')} is in a ${docType(
    'list'
  )} of ${docType('string', {plural: true})}`,
  argDescriptions: {
    lhs: `The ${docType('string')} to check`,
    rhs: `The ${docType('list')} of ${docType('string', {
      plural: true,
    })} to check against`,
  },
  returnValueDescription: `Whether the ${docType('string')} is in the ${docType(
    'list'
  )}`,
  returnType: inputTypes =>
    nullableSkipTaggable(inputTypes.rhs, _ => 'boolean'),
  resolver: ({lhs, rhs}) => (rhs == null ? false : rhs.includes(lhs ?? '')),
});

export const opStringLen = makeStringOp({
  name: 'string-len',
  argTypes: {
    str: {type: 'union', members: ['none', 'string']},
  },
  description: `Returns the length of a ${docType('string')}`,
  argDescriptions: {
    str: `The ${docType('string')} to check`,
  },
  returnValueDescription: `The length of the ${docType('string')}`,
  returnType: inputTypes => 'number',
  resolver: ({str}) => {
    // Don't use str.length because this does not correctly handle unicode
    return [...(str ?? '')].length;
  },
});

export const opStringAdd = makeBinaryStandardOp('+', {
  name: 'string-add',
  argTypes: {
    lhs: {type: 'union', members: ['none', 'string']},
    rhs: {type: 'union', members: ['none', 'string']},
  },
  description: `Concatenates two ${docType('string', {plural: true})}`,
  argDescriptions: {
    lhs: `The first ${docType('string')}`,
    rhs: `The second ${docType('string')}`,
  },
  returnValueDescription: `The concatenated ${docType('string')}`,
  returnType: inputTypes => 'string',
  resolver: ({lhs, rhs}) => {
    return '' + (lhs ?? '') + (rhs ?? '');
  },
});

export const opStringAppend = makeStringOp({
  name: 'string-append',
  argTypes: {
    str: {type: 'union', members: ['none', 'string']},
    suffix: {type: 'union', members: ['none', 'string']},
  },
  description: `Appends a suffix to a ${docType('string')}`,
  argDescriptions: {
    str: `The ${docType('string')} to append to`,
    suffix: 'The suffix to append',
  },
  returnValueDescription: `The ${docType('string')} with the suffix appended`,
  returnType: inputTypes => 'string',
  resolver: ({str, suffix}) => (str ?? '') + (suffix ?? ''),
});
export const opStringPrepend = makeStringOp({
  name: 'string-prepend',
  argTypes: {
    str: {type: 'union', members: ['none', 'string']},
    prefix: {type: 'union', members: ['none', 'string']},
  },
  description: `Prepends a prefix to a ${docType('string')}`,
  argDescriptions: {
    str: `The ${docType('string')} to prepend to`,
    prefix: 'The prefix to prepend',
  },
  returnValueDescription: `The ${docType('string')} with the prefix prepended`,
  returnType: inputTypes => 'string',
  resolver: ({str, prefix}) => '' + (prefix ?? '') + (str ?? ''),
});

export const opStringSplit = makeStringOp({
  name: 'string-split',
  argTypes: {
    str: {type: 'union', members: ['none', 'string']},
    sep: {type: 'union', members: ['none', 'string']},
  },
  description: `Splits a ${docType('string')} into a ${docType(
    'list'
  )} of ${docType('string', {plural: true})}`,
  argDescriptions: {
    str: `The ${docType('string')} to split`,
    sep: 'The separator to split on',
  },
  returnValueDescription: `The ${docType('list')} of ${docType('string', {
    plural: true,
  })}`,
  returnType: inputTypes => ({type: 'list', objectType: 'string'}),
  resolver: ({str, sep}) => str?.split(sep ?? '') ?? [],
});

export const opStringPartition = makeStringOp({
  name: 'string-partition',
  argTypes: {
    str: {type: 'union', members: ['none', 'string']},
    sep: {type: 'union', members: ['none', 'string']},
  },
  description: `Partitions a ${docType('string')} into a ${docType(
    'list'
  )} of the ${docType('string', {plural: true})}`,
  argDescriptions: {
    str: `The ${docType('string')} to split`,
    sep: 'The separator to split on',
  },
  returnValueDescription: `A ${docType('list')} of ${docType('string', {
    plural: true,
  })}: the ${docType(
    'string'
  )} before the separator, the separator, and the ${docType(
    'string'
  )} after the separator`,
  returnType: inputTypes => ({type: 'list', objectType: 'string'}),
  resolver: ({str, sep}) => {
    let result;
    const split = str?.split(sep ?? '') ?? [];
    if (split.length === 1) {
      result = [split[0], null, null];
    }
    result = [split[0], sep, split.slice(1).join(sep ?? '')];
    return result;
  },
});

// TODO(np): rPartition?

export const opStringStartsWith = makeStringOp({
  name: 'string-startsWith',
  argTypes: {
    str: {type: 'union', members: ['none', 'string']},
    prefix: {type: 'union', members: ['none', 'string']},
  },
  description: `Checks if a ${docType('string')} starts with a prefix`,
  argDescriptions: {
    str: `The ${docType('string')} to check`,
    prefix: 'The prefix to check for',
  },
  returnValueDescription: `Whether the ${docType(
    'string'
  )} starts with the prefix`,
  returnType: inputTypes => 'boolean',
  resolver: ({str, prefix}) =>
    prefix ? str?.startsWith(prefix) ?? false : true,
});

export const opStringEndsWith = makeStringOp({
  name: 'string-endsWith',
  argTypes: {
    str: {type: 'union', members: ['none', 'string']},
    suffix: {type: 'union', members: ['none', 'string']},
  },
  description: `Checks if a ${docType('string')} ends with a suffix`,
  argDescriptions: {
    str: `The ${docType('string')} to check`,
    suffix: 'The suffix to check for',
  },
  returnValueDescription: `Whether the ${docType(
    'string'
  )} ends with the suffix`,
  returnType: inputTypes => 'boolean',
  resolver: ({str, suffix}) => (suffix ? str?.endsWith(suffix) ?? false : true),
});

export const opStringIsAlpha = makeStringOp({
  name: 'string-isAlpha',
  argTypes: {
    str: {type: 'union', members: ['none', 'string']},
  },
  description: `Checks if a ${docType('string')} is alphabetic`,
  argDescriptions: {
    str: `The ${docType('string')} to check`,
  },
  returnValueDescription: `Whether the ${docType('string')} is alphabetic`,
  returnType: inputTypes => 'boolean',
  resolver: ({str}) => str?.match(/^[a-z]+$/i) !== null,
});

export const opStringIsNumeric = makeStringOp({
  name: 'string-isNumeric',
  argTypes: {
    str: {type: 'union', members: ['none', 'string']},
  },
  description: `Checks if a ${docType('string')} is numeric`,
  argDescriptions: {
    str: `The ${docType('string')} to check`,
  },
  returnValueDescription: `Whether the ${docType('string')} is numeric`,
  returnType: inputTypes => 'boolean',
  resolver: ({str}) =>
    (str?.length ?? 0) > 0 && str?.match(/^-?\d*(\.\d+)?$/i) !== null,
});

export const opStringIsAlnum = makeStringOp({
  name: 'string-isAlnum',
  argTypes: {
    str: {type: 'union', members: ['none', 'string']},
  },
  description: `Checks if a ${docType('string')} is alphanumeric`,
  argDescriptions: {
    str: `The ${docType('string')} to check`,
  },
  returnValueDescription: `Whether the ${docType('string')} is alphanumeric`,
  returnType: inputTypes => 'boolean',
  resolver: ({str}) => str?.match(/^[a-z0-9]+$/i) !== null,
});

// TODO(np): Other isX... isDigit, isUpper, isLower

export const opStringLower = makeStringOp({
  name: 'string-lower',
  argTypes: {
    str: {type: 'union', members: ['none', 'string']},
  },
  description: `Converts a ${docType('string')} to lowercase`,
  argDescriptions: {
    str: `The ${docType('string')} to convert to lowercase`,
  },
  returnValueDescription: `The lowercase ${docType('string')}`,
  returnType: inputTypes => 'string',
  resolver: ({str}) => str?.toLocaleLowerCase() ?? '',
});
export const opStringUpper = makeStringOp({
  name: 'string-upper',
  argTypes: {
    str: {type: 'union', members: ['none', 'string']},
  },
  description: `Converts a ${docType('string')} to uppercase`,
  argDescriptions: {
    str: `The ${docType('string')} to convert to uppercase`,
  },
  returnValueDescription: `The uppercase ${docType('string')}`,
  returnType: inputTypes => 'string',
  resolver: ({str}) => str?.toLocaleUpperCase() ?? '',
});

export const opStringSlice = makeStringOp({
  name: 'string-slice',
  argTypes: {
    str: {type: 'union', members: ['none', 'string']},
    begin: {type: 'union', members: ['none', 'number']},
    end: {type: 'union', members: ['none', 'number']},
  },
  description: `Slices a ${docType(
    'string'
  )} into a substring based on beginning and end indices`,
  argDescriptions: {
    str: `The ${docType('string')} to slice`,
    begin: 'The beginning index of the substring',
    end: 'The ending index of the substring',
  },
  returnValueDescription: `The substring`,
  returnType: inputTypes => 'string',
  resolver: ({str, begin, end}) => {
    if (begin == null && end != null) {
      return str?.slice(0, end) ?? '';
    }
    return str?.slice(begin ?? undefined, end ?? undefined) ?? '';
  },
});

export const opStringReplace = makeStringOp({
  name: 'string-replace',
  argTypes: {
    str: {type: 'union', members: ['none', 'string']},
    sub: {type: 'union', members: ['none', 'string']},
    newSub: {type: 'union', members: ['none', 'string']},
  },
  description: `Replaces all occurrences of a substring in a ${docType(
    'string'
  )}`,
  argDescriptions: {
    str: `The ${docType('string')} to replace contents of`,
    sub: 'The substring to replace',
    newSub: 'The substring to replace the old substring with',
  },
  returnValueDescription: `The ${docType('string')} with the replacements`,
  returnType: inputTypes => 'string',
  resolver: ({str, sub, newSub}) =>
    str?.replace(new RegExp(sub ?? '', 'g'), newSub ?? ''),
});

export const opStringFindAll = makeStringOp({
  name: 'string-findAll',
  argTypes: {
    str: {type: 'union', members: ['none', 'string']},
    sub: {type: 'union', members: ['none', 'string']},
  },
  description: `Finds all occurrences of a substring in a ${docType('string')}`,
  argDescriptions: {
    str: `The ${docType('string')} to find occurrences of the substring in`,
    sub: 'The substring to find',
  },
  returnValueDescription: `The ${docType(
    'list'
  )} of indices of the substring in the ${docType('string')}`,
  returnType: inputTypes => ({type: 'list', objectType: 'string'}),
  resolver: ({str, sub}) =>
    Array.from(str?.match(new RegExp(sub ?? '', 'g')) || []),
});

export const opStringContains = makeStringOp({
  name: 'string-contains',
  argTypes: {
    str: {type: 'union', members: ['none', 'string']},
    sub: {type: 'union', members: ['none', 'string']},
  },
  description: `Checks if a ${docType('string')} contains a substring`,
  argDescriptions: {
    str: `The ${docType('string')} to check`,
    sub: 'The substring to check for',
  },
  returnValueDescription: `Whether the ${docType(
    'string'
  )} contains the substring`,
  returnType: inputTypes => 'boolean',
  resolver: ({str, sub}) => str?.match(new RegExp(sub ?? '', 'g')) != null,
});
export const opStringStrip = makeStringOp({
  name: 'string-strip',
  argTypes: {
    str: {type: 'union', members: ['none', 'string']},
  },
  description: `Strip whitespace from both ends of a ${docType('string')}.`,
  argDescriptions: {
    str: `The ${docType('string')} to strip.`,
  },
  returnValueDescription: `The stripped ${docType('string')}.`,
  returnType: inputTypes => 'string',
  resolver: ({str}) => str?.trim() ?? '',
});

export const opStringLeftStrip = makeStringOp({
  name: 'string-lStrip',
  argTypes: {
    str: {type: 'union', members: ['none', 'string']},
  },
  description: `Strip leading whitespace`,
  argDescriptions: {
    str: `The ${docType('string')} to strip.`,
  },
  returnValueDescription: `The stripped ${docType('string')}.`,
  returnType: inputTypes => 'string',
  resolver: ({str}) => str?.trimStart() ?? '',
});

export const opStringRightStrip = makeStringOp({
  name: 'string-rStrip',
  argTypes: {
    str: {type: 'union', members: ['none', 'string']},
  },
  description: `Strip trailing whitespace`,
  argDescriptions: {
    str: `The ${docType('string')} to strip.`,
  },
  returnValueDescription: `The stripped ${docType('string')}.`,
  returnType: inputTypes => 'string',
  resolver: ({str}) => str?.trimEnd() ?? '',
});

// Levenshtein distance is the minimum number of single-character
// edits it would take to go from one string to another
export const opStringLevenshtein = makeStringOp({
  name: 'string-levenshtein',
  renderInfo: {type: 'function'},
  argTypes: {
    str1: {type: 'union', members: ['none', 'string']},
    str2: {type: 'union', members: ['none', 'string']},
  },
  description: `Calculates the Levenshtein distance between two ${docType(
    'string',
    {plural: true}
  )}.`,
  argDescriptions: {
    str1: `The first ${docType('string')}.`,
    str2: `The second ${docType('string')}.`,
  },
  returnValueDescription: `The Levenshtein distance between the two ${docType(
    'string',
    {plural: true}
  )}.`,
  returnType: inputTypes => 'number',
  resolver: ({str1, str2}) => {
    return levenshtein(str1 ?? '', str2 ?? '');
  },
});
