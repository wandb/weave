import { WeaveObject } from './weaveObject';

export type ColumnMapping<I, O> = {
  [K in keyof O]: keyof I;
};
export type ArgsObject = { [key: string]: any };
export type Row = { [key: string]: any };

export interface Callable<I, O> {
  run: (input: I) => Promise<O>;
}
export type FnInputs<T extends Callable<any, any>> = T extends Callable<infer I, any> ? I : never;
export type FnOutput<T extends Callable<any, any>> = T extends Callable<any, infer O> ? O : never;

export abstract class CallableObject<I, O> extends WeaveObject implements Callable<I, O> {
  abstract run(input: I): Promise<O>;
}

export function mapArgs<I extends Record<string, any>, O extends Record<string, any>>(
  input: I,
  mapping: ColumnMapping<I, O>
): O {
  const output: Partial<O> = {};
  for (const [inputKey, outputKey] of Object.entries(mapping) as [keyof I, keyof O][]) {
    if (inputKey in input) {
      output[outputKey] = input[inputKey];
    }
  }
  return output as O;
}
