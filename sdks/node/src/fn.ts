import { boundOp } from './op';
import { WeaveObject } from './weaveObject';

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
