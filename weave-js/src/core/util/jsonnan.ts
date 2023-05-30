import * as _ from 'lodash';

import parseMore from './json_parseMore';

function fixupIndex(obj: any, i: any, v: any) {
  if (typeof v === 'string') {
    if (v === 'NaN' || v === 'nan') {
      obj[i] = NaN;
    } else if (v === 'Infinity' || v === 'Inf') {
      obj[i] = Infinity;
    } else if (v === '-Infinity' || v === '-Inf') {
      obj[i] = -Infinity;
    }
  } else if (_.isObject(v) || _.isArray(v)) {
    fixupNaN(v);
  }
}

// Replace strings that represent special floats with
// their float equivalents.  For allocation efficiency, we do this
// in place rather than create a new structure.
export function fixupNaN(obj: any) {
  if (_.isArray(obj)) {
    obj.forEach((v, i) => fixupIndex(obj, i, v));
  } else if (_.isObject(obj)) {
    for (const k of Object.keys(obj)) {
      fixupIndex(obj, k, (obj as any)[k]);
    }
  }
}

type ParsedResult = {error: true} | {error: false; result: any};

// Parse data returned by the server, we know this data is parseable
export function JSONparseNaN(str: string) {
  if (str == null) {
    return str;
  }
  const parsed = JSON.parse(str);
  fixupNaN(parsed);
  return parsed;
}

// Parse files that were saved by the python client. These could
// contain anything, we force the caller to check for a returned
// error
//
// Files saved by some versions of our Python client can contain
// nans and infinities, which javascript JSON.parse can't parse. So
// fallback to this custom parser, which is much slower. We're updating
// the Python client encode nans and infities as strings, so this case
// will stop occurring.
export function JSONparseUserFile(str: string): ParsedResult {
  if (str == null) {
    return {error: false, result: null};
  }
  let parsed: any;
  try {
    parsed = JSON.parse(str);
  } catch (e) {
    console.warn('CAUGHT error when JSON.parsing', e);
    try {
      // Fall back to custom json parser. This parser is an order of magnitude
      // slower than the browser built in parser (on Chrome). But it handles NaN
      // and Inf literals.
      return {error: false, result: parseMore(str)};
    } catch (e2) {
      console.warn('CAUGHT another error when JSON.parsing', e2);
      return {error: true};
    }
  }
  fixupNaN(parsed);
  return {error: false, result: parsed};
}
