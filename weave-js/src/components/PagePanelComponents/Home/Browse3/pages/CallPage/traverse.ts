/**
 * There are are a number of JavaScript/TypeScript libraries for traversing
 * objects, but none of the ones I looked at were quite what I wanted.
 */

// String indicates object key access, number indicates array index access
// This structure allows us to handle corner cases like periods or brackets
// in object keys.
type PathElement = string | number;
type Path = PathElement[];

const escapeKey = (key: string): string => {
  return key.replace(/\./g, '\\.').replace(/\[/g, '\\[').replace(/\]/g, '\\]');
};

export class ObjectPath {
  static parseString(pathString: string): Path {
    const path = [];
    let key = '';
    const n = pathString.length;
    for (let i = 0; i < n; i++) {
      const char = pathString[i];
      if (char === '\\') {
        if (i === n - 1) {
          throw new Error('Invalid escape sequence');
        }
        key += pathString[i + 1];
        i++;
      } else if (char === '.') {
        if (i === 0 || i === n - 1) {
          throw new Error('Invalid object access');
        }
        const prev = pathString[i - 1];
        const next = pathString[i + 1];
        if (!/^[a-z0-9]$/i.test(next) || !/^[a-z0-9\]]$/i.test(prev)) {
          throw new Error('Invalid object access');
        }
        if (key) {
          path.push(key);
          key = '';
        }
      } else if (char === '[') {
        if (key) {
          path.push(key);
          key = '';
        }
        let j = i + 1;
        while (j < n && pathString[j] !== ']') {
          j++;
        }
        const indexStr = pathString.slice(i + 1, j);
        if (j === n) {
          throw new Error(`Invalid array index: '${indexStr}'`);
        }
        if (!/^\d+$/.test(indexStr)) {
          throw new Error(`Invalid array index: '${indexStr}'`);
        }
        path.push(parseInt(indexStr, 10));
        i = j;
      } else {
        key += char;
      }
    }
    if (key) {
      path.push(key);
    }
    return path;
  }

  private path: Path;

  constructor(path: PathElement | Path = []) {
    if (typeof path === 'string') {
      this.path = ObjectPath.parseString(path);
    } else if (typeof path === 'number') {
      this.path = [path];
    } else {
      this.path = path;
    }
  }

  plus(element: PathElement): ObjectPath {
    return new ObjectPath([...this.path, element]);
  }

  tail(): PathElement | undefined {
    return this.path[this.path.length - 1];
  }

  endsWith(element: PathElement): boolean {
    return this.path[this.path.length - 1] === element;
  }

  hasHiddenKey(): boolean {
    const t = this.tail();
    return typeof t === 'string' && (t.startsWith('_') || t === 'name');
  }

  length(): number {
    return this.path.length;
  }

  ancestor(depth: number): ObjectPath {
    return new ObjectPath(this.path.slice(0, depth));
  }

  toPath(): Path {
    return [...this.path];
  }

  toStringArray(): string[] {
    return this.path.map(e => (typeof e === 'string' ? e : e.toString()));
  }

  toString(): string {
    let result = '';
    for (const element of this.path) {
      if (typeof element === 'string') {
        const escaped = escapeKey(element);
        if (result) {
          result += '.';
        }
        result += escaped;
      } else {
        result += '[' + element + ']';
      }
    }
    return result;
  }

  // Given an object, return what this path points to.
  apply(obj: any): any {
    let result = obj;
    for (const element of this.path) {
      if (result === undefined) {
        return undefined;
      }
      result = result[element];
    }
    return result;
  }

  // Given an object and value, update the value for the path.
  set(obj: any, value: any) {
    let target = obj;
    const n = this.path.length;
    for (let i = 0; i < n - 1; i++) {
      const element = this.path[i];
      if (!(element in target)) {
        target[element] = typeof element === 'number' ? [] : {};
      }
      target = target[element];
    }
    target[this.path[n - 1]] = value;
  }
}

type ValueType =
  | 'null'
  | 'undefined'
  | 'boolean'
  | 'number'
  | 'string'
  | 'object'
  | 'array';

export const getValueType = (value: any): ValueType => {
  if (value === null) {
    return 'null';
  }
  if (value === undefined) {
    return 'undefined';
  }
  if (typeof value === 'boolean') {
    return 'boolean';
  }
  if (typeof value === 'number') {
    return 'number';
  }
  if (typeof value === 'string') {
    return 'string';
  }
  if (Array.isArray(value)) {
    return 'array';
  }
  return 'object';
};

const isLeafType = (valueType: ValueType): boolean => {
  return valueType !== 'object' && valueType !== 'array';
};

export type TraverseContext = {
  path: ObjectPath;
  value: any;
  valueType: ValueType;
  isLeaf: boolean;
  depth: number;
};

type CallbackResult = void | boolean | 'skip';

type Callback = (context: TraverseContext) => CallbackResult;

// For debugging purposes we have a default callback that just prints
// a line for each visited node in the object.
const DEFAULT_CALLBACK: Callback = context => {
  const {value, path, depth} = context;
  const prefix = depth.toString().padStart(2, '0') + '  ';
  let valueStr = '';
  if (value === null) {
    valueStr = '<null>';
  } else {
    valueStr = value.toString();
    try {
      valueStr = JSON.stringify(value);
    } catch (e) {
      // Ignore
    }
  }
  console.log(`${prefix}${path} ${valueStr}`);
};

export const traverse = (
  data: any,
  callback?: (context: TraverseContext) => CallbackResult
) => {
  callback = callback ?? DEFAULT_CALLBACK;
  const path: ObjectPath = new ObjectPath();
  const valueType = getValueType(data);
  const start: TraverseContext = {
    value: data,
    valueType,
    isLeaf: isLeafType(valueType),
    path,
    depth: 0,
  };
  const stack = [start];
  while (stack.length) {
    const context = stack.pop();
    if (!context) {
      continue;
    }
    const action = callback(context);
    if (action === 'skip') {
      continue;
    } else if (action === false) {
      break;
    }
    if (context.valueType === 'array') {
      const n = context.value.length;
      for (let i = n - 1; i >= 0; i--) {
        const value = context.value[i];
        const itemValueType = getValueType(value);
        stack.push({
          value,
          valueType: itemValueType,
          isLeaf: isLeafType(itemValueType),
          path: context.path.plus(i),
          depth: context.depth + 1,
        });
      }
    } else if (context.valueType === 'object') {
      // Reverse so we pop them in the original order
      const keys = Object.keys(context.value).reverse();
      for (const key of keys) {
        const value = context.value[key];
        const itemValueType = getValueType(value);
        stack.push({
          value,
          valueType: itemValueType,
          isLeaf: isLeafType(itemValueType),
          path: context.path.plus(key),
          depth: context.depth + 1,
        });
      }
    }
  }
};

const UNFILTERED = () => true;

// Convenience wrapper around traverse returning an optionally
// filtered list of context objects.
export const traversed = (
  data: any,
  filter?: (context: TraverseContext) => boolean
): TraverseContext[] => {
  const matches: TraverseContext[] = [];
  const f = filter ?? UNFILTERED;
  traverse(data, context => {
    const result = f(context);
    if (result) {
      matches.push(context);
    }
  });
  return matches;
};

export const mapObject = (
  data: any,
  transform: (context: TraverseContext) => any
) => {
  const result = {};
  traverse(data, context => {
    if (context.depth === 0) {
      return;
    }
    const newValue = transform(context);
    // TODO: Maybe support a special value to indicate deletion?
    context.path.set(result, newValue);
  });
  return result;
};
