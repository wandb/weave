import * as _ from 'lodash';

export interface Row {
  [key: string | number]: any;
}

export function fixColNameForVega(name: string | number) {
  // custom charts can feed in numbers as column names
  // https://weightsandbiases.slack.com/archives/C01KQ5KTDC3/p1691760054418779
  const safeName = typeof name === 'number' ? String(name) : name;
  return safeName.replace(/\.\//g, '_');
}

export function flattenNested(rows: Row[]): Row[] {
  const result: Row[] = [];
  for (const row of rows) {
    // Flatten only nested objects (preserving nested arrays and basic values)
    // const flatObj = flattenNestedObjects(row);

    // Create a base Row from any non-array keys
    const baseRow: Row = {};
    const arrays: Row[][] = [];
    _.forEach(row, (v, k) => {
      if (_.isArray(v)) {
        arrays.push(v);
      } else if (_.isObject(v)) {
        Object.assign(baseRow, flattenNestedObjects(v));
      } else {
        baseRow[fixColNameForVega(k)] = v;
      }
    });

    // For each key with nested arrays, add a row for each unnested result,
    // including the keys from our base row.
    let added = false;
    for (const v of arrays) {
      for (const ir of flattenNested(v)) {
        result.push(Object.assign(ir, baseRow));
      }
      added = true;
    }
    if (added === false) {
      result.push(baseRow);
    }
  }
  return result;
}

// Given an object, flatten all sub-objects (not including arrays). Leave
// all other keys the same.
export function flattenNestedObjects(obj: Row): Row {
  const result: Row = {};
  _.forEach(obj, (v, k) => {
    if (_.isArray(v)) {
      // drop arrays here for now
    } else if (_.isObject(v)) {
      Object.assign(result, flattenNestedObjects(v));
    } else {
      result[fixColNameForVega(k)] = v;
    }
  });
  return result;
}

///// flattenNestedOld implements the old tableWithFullPathColNames transform

function concatPolicyFixKey(s: string) {
  // We probably don't need to remove the colon, but this policy
  // is only used for legacy panels so I left it.
  return s.replace(/:/g, '.').replace(/\./g, '_');
}

export function colNamePolicyConcat(parentKey: string, key: string) {
  return concatPolicyFixKey(parentKey) + '_' + concatPolicyFixKey(key);
}

export function flattenNestedOld(rows: Row[]): Row[] {
  const result: Row[] = [];
  for (const row of rows) {
    const baseRow: Row = {};

    // Flatten only nested objects (preserving nested arrays and basic values)
    const flatObj = flattenNestedObjectsOld(row);

    // Create a base Row from any non-array keys
    _.forEach(flatObj, (v, k) => {
      // k = fixKey(k);
      if (!_.isArray(v)) {
        baseRow[k] = v;
      }
    });

    // For each key with nested arrays, add a row for each unnested result,
    // including the keys from our base row.
    let added = false;
    _.forEach(flatObj, (v, k) => {
      // k = fixKey(k);
      if (_.isArray(v)) {
        for (const ir of flattenNestedOld(v)) {
          result.push({
            ...baseRow,
            ..._.mapKeys(ir, (innerV, innerK) =>
              colNamePolicyConcat(k, innerK)
            ),
          });
        }
        added = true;
      }
    });
    if (added === false) {
      result.push(baseRow);
    }
  }
  return result;
}

// Given an object, flatten all sub-objects (not including arrays). Leave
// all other keys the same.
export function flattenNestedObjectsOld(obj: Row): Row {
  const result: Row = {};
  _.forEach(obj, (v, k) => {
    // k = fixKey(k);
    if (_.isObject(v) && !_.isArray(v)) {
      _.forEach(flattenNestedObjectsOld(v), (sv, sk) => {
        // sk = fixKey(sk);
        result[colNamePolicyConcat(k, sk)] = sv;
      });
    } else {
      result[k] = v;
    }
  });
  return result;
}
