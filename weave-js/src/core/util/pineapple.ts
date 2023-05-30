import {defaults} from 'lodash';

import {invertRemap} from './invertRemap';

export interface Options {
  // Custom key to use (default 🍍)
  key: string;
}

export const PINEAPPLE = '🍍';

const defaultOptions: Options = {
  key: PINEAPPLE,
};

type SerializedRef = number;

type NormObjectMap = Map<object | any[], SerializedRef>;

class ObjectNormalizer {
  private nextId: SerializedRef = 0;
  private normObjects: NormObjectMap = new Map();

  public normalize(value: any): NormObjectMap {
    this.reset();
    this.visitValue(null, value);
    return this.normObjects;
  }

  private reset() {
    this.nextId = 0;
    this.normObjects = new Map();
  }

  private newId() {
    return this.nextId++;
  }

  private visitValue(k: string | null, v: any) {
    switch (typeof v) {
      case 'number':
      case 'string':
      case 'boolean':
        return;
      case 'object': // array, obj or null
        if (v === null) {
          return;
        }

        if (this.normObjects.has(v)) {
          return;
        }

        this.normObjects.set(v, this.newId());

        if (Array.isArray(v)) {
          v.forEach(aVal => this.visitValue(null, aVal));
        } else {
          Object.entries(v).forEach(([oKey, oVal]) =>
            this.visitValue(oKey, oVal)
          );
        }
        return;
    }

    throw new Error(`invalid: ${k}: ${v}`);
  }
}

export function pineapple(food: any, optsIn: Partial<Options> = {}): any {
  const opts: Options = defaults({}, optsIn, defaultOptions);

  if (
    opts.key == null ||
    opts.key.length === 0 ||
    typeof opts.key !== 'string' ||
    !isNaN(Number(opts.key))
  ) {
    throw new TypeError('key must be non-empty, non-numeric string');
  }

  if (typeof food === 'undefined') {
    return {
      [opts.key]: `${opts.key + opts.key}_undef_`,
    };
  } else if (typeof food !== 'object') {
    return {
      [opts.key]: food,
    };
  } else if (food === null) {
    return {
      [opts.key]: null,
    };
  }

  if (food.constructor !== Object && food.constructor !== Array) {
    throw new Error(
      `Cannot pineapple non-JSON compatible object: ${food.constructor.name}`
    );
  }

  // Make a flat map of objects, may still be nested
  const objNormalizer = new ObjectNormalizer();
  const norm = objNormalizer.normalize(food);

  // Return a raw value or reference
  const localLookup = (v: any) => {
    if (typeof v === 'object' && v !== null) {
      const ref = norm.get(v);
      return {
        [opts.key]: ref,
      };
    }
    return v;
  };

  const numWrapper = (n: number): any => ({
    [opts.key + opts.key]: n,
  });

  const dateWrapper = (d: Date): any => ({
    [opts.key + opts.key]: {date: d.valueOf()},
  });

  // Invert the map, so we have a map of SerializedRef -> Value
  const inverse = Object.fromEntries(
    invertRemap(norm, (key, id) => {
      if (Array.isArray(key)) {
        return key.map(aVal => localLookup(aVal));
      }

      return Object.fromEntries(
        Object.entries(key).map(([oKey, oVal]) => {
          if (oKey === opts.key && typeof oVal === 'number') {
            return [oKey, numWrapper(oVal)];
          } else if (
            oVal != null &&
            typeof oVal === 'object' &&
            oVal.constructor === Date
          ) {
            return [oKey, dateWrapper(oVal)];
          } else if (oKey === opts.key + opts.key) {
            throw new Error(
              `Cannot encode object containing doubled key ("${
                opts.key + opts.key
              }")`
            );
          }
          return [oKey, localLookup(oVal)];
        })
      );
    })
  );

  return {
    [opts.key]: {
      [opts.key]: 0,
    },
    refs: Object.entries(inverse).map(([idx, obj]) => obj),
  };
}

export function unpineapple(encoded: any, optsIn: Partial<Options> = {}): any {
  const opts: Options = defaults({}, optsIn, defaultOptions);

  const valCache = new Map<any, any>();
  const cached = (serializedVal: any, val: any): any => {
    valCache.set(serializedVal, val);
    return val;
  };

  const doUnpineapple = (encodedInternal: any, can: any[]): any => {
    const val = valCache.get(encodedInternal);
    if (val !== undefined) {
      return val;
    }
    switch (typeof encodedInternal) {
      case 'number':
      case 'boolean':
        return encodedInternal;
      case 'string':
        if (encodedInternal === `${opts.key + opts.key}_undef_`) {
          return undefined;
        }
        return encodedInternal;
      case 'object':
        if (encodedInternal == null) {
          return null;
        }
        if (Object.keys(encodedInternal).length === 0) {
          return encodedInternal;
        }

        const raw: any = encodedInternal[opts.key + opts.key];
        if (typeof raw !== 'undefined') {
          if (raw.date !== undefined) {
            return new Date(raw.date);
          }
          return raw;
        }

        const ref: any = encodedInternal[opts.key];
        if (typeof ref === 'number') {
          const slice = can[ref];
          if (typeof slice === 'undefined') {
            // Ref doesn't exist
            throw new Error('Not a pineapple');
          }
          // Pineapple! trade for the ref
          return cached(encodedInternal, doUnpineapple(slice, can));
        }

        if (Array.isArray(encodedInternal)) {
          return cached(
            encodedInternal,
            encodedInternal.map(f => doUnpineapple(f, can))
          );
        }

        return cached(
          encodedInternal,
          Object.fromEntries(
            Object.entries(encodedInternal).map(([objKey, value]) => [
              objKey,
              doUnpineapple(value, can),
            ])
          )
        );
      default:
        throw new Error(`Not a pineapple: ${encodedInternal}`);
    }
  };

  if (typeof encoded[opts.key] === 'undefined') {
    throw new Error(`Pineapple key not found: ${opts.key}`);
  }
  return doUnpineapple(encoded[opts.key], encoded.refs);
}
