import {Call} from './call';
import {getGlobalDomain} from './urls';
import {WeaveObject} from './weaveObject';

export type ParameterNamesOption = 'useParam0Object' | string[] | undefined;

export type Op<T extends (...args: any[]) => any> = {
  __isOp: true;
  __wrappedFunction: T;
  __boundThis?: WeaveObject;
  __name: string;
  __savedRef?: OpRef | Promise<OpRef>;
  __parameterNames?: ParameterNamesOption;
  invoke: CallMethod<T>;
} & T &
  ((
    ...args: Parameters<T>
  ) => ReturnType<T> extends AsyncIterable<infer U>
    ? AsyncIterable<Awaited<U>>
    : Promise<Awaited<ReturnType<T>>>);

export interface StreamReducer<T, R> {
  initialStateFn: () => R;
  reduceFn: (state: R, chunk: T) => R;
  finalizeFn: (state: R) => void;
}

/**
 * Helper type for decorators
 * This represents a decorator function that can be used with both legacy and Stage 3 decorators.
 *
 * For Stage 3 decorators:
 *   target: The function being decorated (T)
 *   context: MethodDecoratorContext
 *
 * For legacy decorators:
 *   target: The prototype (instance methods) or constructor (static methods)
 *   propertyKey: The method name
 *   descriptor: The property descriptor containing the method
 */
export type OpDecorator<T extends (...args: any[]) => any> = ((
  // Stage 3 signature
  value: T,
  context: ClassMethodDecoratorContext
) => T | void) &
  ((
    // Legacy signature
    target: Object,
    propertyKey: string | symbol,
    descriptor: TypedPropertyDescriptor<T>
  ) => TypedPropertyDescriptor<T> | void);

/**
 * Options that can be passed to the op wrapper
 */
export interface OpOptions<T extends (...args: any[]) => any> {
  name?: string;
  streamReducer?: StreamReducer<any, any>;
  originalFunction?: T;
  callDisplayName?: (...args: Parameters<T>) => string;
  summarize?: (result: Awaited<ReturnType<T>>) => Record<string, any>;
  bindThis?: WeaveObject;
  isDecorator?: boolean;
  // If true, the op will adopt the `this` value of the original function
  shouldAdoptThis?: boolean;
  parameterNames?: ParameterNamesOption;
  /** The kind of operation (e.g., 'llm', 'agent', 'tool', 'search') for UI categorization */
  opKind?: string;
  /** Custom color for the operation in the UI */
  opColor?: string;
}

type AsyncResult<F extends (...args: any[]) => any> = Promise<
  Awaited<ReturnType<F>>
>;

export interface OpWrapper<F extends (...args: any[]) => any> {
  (this: any, ...params: Parameters<F>): AsyncResult<F>;
}

export interface CallMethod<F extends (...args: any[]) => any> {
  (
    this: any,
    ...params: Parameters<F>
  ): Promise<[Awaited<ReturnType<F>>, Call]>;
}

export function isOp(value: any): value is Op<any> {
  return value && value.__isOp === true;
}

export function getOpWrappedFunction<T extends (...args: any[]) => any>(
  opValue: Op<T>
): T {
  return opValue.__wrappedFunction;
}

export function getOpName(opValue: Op<any>): string {
  return opValue.__name;
}

export function getOpParameterNames(opValue: Op<any>): ParameterNamesOption {
  return opValue.__parameterNames;
}

export class OpRef {
  constructor(
    public projectId: string,
    public objectId: string,
    public digest: string
  ) {}

  // TODO: Add extra

  public uri() {
    return `weave:///${this.projectId}/op/${this.objectId}:${this.digest}`;
  }

  public ui_url() {
    const domain = getGlobalDomain();
    return `https://${domain}/${this.projectId}/weave/ops/${this.objectId}/versions/${this.digest}`;
  }

  public async get() {
    throw new Error('Not implemented');
  }
}
