import { boundOp } from './op';
import { WeaveObject } from './weaveObject';

export type ColumnMapping = { [key: string]: string };
export type ArgsObject = { [key: string]: any };
export type Row = { [key: string]: any };

export interface Fn<I, O> {
  id: string;
  description: string;
  invoke: (input: I) => Promise<O>;
  trials: (n: number, input: I) => Promise<O[]>;
  // map: (over: I[]) => O[]
}
export type FnInputs<T extends Fn<any, any>> = T extends Fn<infer I, any> ? I : never;
export type FnOutput<T extends Fn<any, any>> = T extends Fn<any, infer O> ? O : never;

// In python this is currently called `Model`
export abstract class BaseFn<I, O> extends WeaveObject implements Fn<I, O> {
  constructor({ id, description }: { id?: string; description?: string } = {}) {
    super({ id, description });
    this.trials = boundOp(this, this.trials, {
      parameterNames: ['n', 'input'],
    });
    this.invoke = boundOp(this, this.invoke, { parameterNames: ['input'] });
  }

  get description() {
    return this._baseParameters.description ?? '';
  }

  abstract invoke(input: I): Promise<O>;
  abstract trials(n: number, input: I): Promise<O[]>;
}

export function invoke(fn: Function, args: ArgsObject, mapping: ColumnMapping | null) {
  if (mapping) {
    args = mapArgs(args, mapping);
  }
  const orderedArgs = prepareArgsForFn(args, fn);
  return fn(...Object.values(orderedArgs));
}

export function prepareArgsForFn(args: ArgsObject, fn: Function): ArgsObject {
  const fnArgs = getFunctionArguments(fn);
  const preparedArgs: ArgsObject = {};

  for (const [argName, defaultValue] of Object.entries(fnArgs)) {
    if (argName in args) {
      preparedArgs[argName] = args[argName];
    } else if (defaultValue != null) {
      preparedArgs[argName] = defaultValue;
    } else {
      throw new Error(`Missing required argument: ${argName}`);
    }
  }
  return preparedArgs;
}

export function mapArgs(row: Row, mapping: ColumnMapping): Row {
  return Object.fromEntries(Object.entries(row).map(([k, v]) => [mapping[k] || k, v]));
}

export function getFunctionArguments(fn: Function): ArgsObject {
  // This naive impl works for basic funcs, arrows, and methods.  It doesn't work yet for
  // destructuring or rest params
  const match = fn.toString().match(/\(([^)]*)\)/); // Find the function signature
  if (!match) {
    return {};
  }

  const argsString = match[1].replace(/\/\*[\s\S]*?\*\/|\/\/.*/g, ''); // Strip out comments
  const args = argsString
    .split(',')
    .map(arg => arg.trim())
    .filter(arg => arg !== '');

  return args.reduce(
    (acc, v) => {
      if (v.startsWith('...')) {
        acc[v.slice(3)] = '...rest';
      } else {
        const [name, defaultValue] = v.split('=').map(s => s.trim());
        acc[name] = defaultValue;
      }
      return acc;
    },
    {} as Record<string, string | undefined>
  );
}
