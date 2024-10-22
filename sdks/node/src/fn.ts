import { WeaveObject } from './weaveObject';

export type ColumnMapping = { [key: string]: string };
export type ArgsObject = { [key: string]: any };
export type Row = { [key: string]: any };

export interface Callable<I, O> {
  run: (input: I) => Promise<O>;
}
export type FnInputs<T extends Callable<any, any>> = T extends Callable<infer I, any> ? I : never;
export type FnOutput<T extends Callable<any, any>> = T extends Callable<any, infer O> ? O : never;

export interface FuncOptions {
  id?: string;
  description?: string;
  parameterNames?: { [funcName: string]: string[] };
}

// or "Function"
export abstract class CallableObject<I, O> extends WeaveObject implements Callable<I, O> {
  abstract run(input: I): Promise<O>;
}

// userland
class MyFunc extends CallableObject<number, number> {
  async run(input: number): Promise<number> {
    return input + 1;
  }
}

// In python this is currently called `Model`
// export abstract class Func<I, O> extends WeaveObject implements Callable<I, O> {
//   constructor({ id, description, parameterNames }: FuncOptions = {}) {
//     super({ id, description });

//     const trialsParams = parameterNames?.trials ?? Object.keys(inferFunctionArguments(this.trials));
//     this.trials = boundOp(this, this.trials, { parameterNames: trialsParams });

//     const invokeParams = parameterNames?.invoke ?? Object.keys(inferFunctionArguments(this.invoke));
//     this.invoke = boundOp(this, this.invoke, { parameterNames: invokeParams });
//   }

//   get description() {
//     return this._baseParameters.description ?? '';
//   }

//   // default impl, there may be better impls depending on the fn
//   trials(n: number, input: I): Promise<O[]> {
//     return Promise.all(
//       Array(n)
//         .fill(null)
//         .map(() => this.invoke(input))
//     );
//   }

//   abstract invoke(input: I): Promise<O>;
// }

export function invoke(fn: Function, args: ArgsObject, mapping?: ColumnMapping) {
  if (mapping) {
    args = mapArgs(args, mapping);
  }
  const orderedArgs = prepareArgsForFn(args, fn);
  return fn(...Object.values(orderedArgs));
}

export function prepareArgsForFn(args: ArgsObject, fn: Function): ArgsObject {
  const fnArgs = inferFunctionArguments(fn);
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

export function inferFunctionArguments(fn: Function): ArgsObject {
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
