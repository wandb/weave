import { WeaveObject, WeaveObjectParameters } from './weaveObject';

export type ColumnMapping = { [key: string]: string };
export type ArgsObject = { [key: string]: any };
export type Row = { [key: string]: any };

export interface Callable<I, O> {
  run: (input: I) => Promise<O>;
}
export type FnInputs<T extends Callable<any, any>> = T extends Callable<infer I, any> ? I : never;
export type FnOutput<T extends Callable<any, any>> = T extends Callable<any, infer O> ? O : never;

// or "Function"
export abstract class CallableObject<I, O> extends WeaveObject implements Callable<I, O> {
  abstract run(input: I): Promise<O>;
}

// userland
interface MyFuncOptions extends WeaveObjectParameters {
  magicNumber?: number;
}

class MyFunc extends CallableObject<number, number> {
  private magicNumber: number;

  constructor(options: MyFuncOptions = {}) {
    super(options);
    this.magicNumber = options.magicNumber ?? 42;
  }

  async run(input: number): Promise<number> {
    return input + this.magicNumber;
  }
}

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
