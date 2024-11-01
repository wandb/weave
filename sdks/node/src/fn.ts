import {WeaveObject} from './weaveObject';

export type ColumnMapping<I, O> = {
  [K in keyof O]: keyof I;
};
export type ArgsObject = {[key: string]: any};
export type Row = {[key: string]: any};

export interface Callable<I, O> {
  run: (input: I) => Promise<O>;
}
export type FnInputs<T extends Callable<any, any>> =
  T extends Callable<infer I, any> ? I : never;
export type FnOutput<T extends Callable<any, any>> =
  T extends Callable<any, infer O> ? O : never;

export abstract class CallableObject<I, O>
  extends WeaveObject
  implements Callable<I, O>
{
  abstract run(input: I): Promise<O>;
}

export function mapArgs<
  T extends Record<string, any>,
  M extends Record<string, keyof T>,
>(input: T, mapping: M): {[K in keyof M]: T[M[K]]} {
  const result: Partial<{[K in keyof M]: T[M[K]]}> = {};

  for (const [newKey, oldKey] of Object.entries(mapping)) {
    if (oldKey in input) {
      result[newKey as keyof M] = input[oldKey];
    }
  }
  return result as {[K in keyof M]: T[M[K]]};
}
