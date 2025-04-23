import {getGlobalClient} from './clientApi';
import {TRACE_CALL_EMOJI} from './constants';
import {Op, OpOptions } from './opType';
import {getGlobalDomain} from './urls';
import {warnOnce} from './utils/warnOnce';

export interface MethodDecoratorContext {
  kind: 'method';
  name: string | symbol;
  static?: boolean;
  class?: Function;
  addInitializer?(initializer: () => void): void;
  private?: boolean;
  access?: {
    has(object: object): boolean;
    get(object: object): Function;
  };
  metadata?: any;
}

/**
 * Check if the arguments are for a Stage 3 decorator.
 * New-style decorators are called with 2 arguments:
 *   [value, context]
 *   where context is an object with a "kind" property (among others).
 * @param args - The arguments passed to the decorator.
 * @returns boolean
 */
function isOfficiallDecorator(args: any[]) {
  if (args.length === 2 && args[1] && typeof args[1] === 'object' && 'kind' in args[1]) {
    return true;
  }
  return false;
}

/**
 * Helper function to extract the class name from a function and optional
 * context.  When a context is provided the name is set via the addInitializer
 * hook.  When no context is provided the name is extracted from the target.
 * @param target The original method being decorated or class prototype
 * @param context The optionalcontext of the decorator
 * @returns The class name or 'anonymous' if it cannot be determined
 */
function extractClassName(target: any, context?: MethodDecoratorContext): string {
  // Use addInitializer to set the name after class definition/instantiation
  if (context && context.addInitializer && target.__name === "__pending__") {
    context.addInitializer(function(this: any) {
      const actualClassName = context.static ? this.name : this.constructor.name;
      target.__name = `${actualClassName}.${String(context.name)}`;
    });
    return '__pending__';
  }

  // For legacy decorators
  if (target) {
    // For static methods, target is the class constructor
    if (target.constructor === Function) {
      return target.name || 'anonymous';
    }
    // For instance methods, target is the prototype
    return target.constructor?.name || 'anonymous';
  }

  return 'anonymous';
}

/**
 * A wrapper to weave op-ify a function or method that works on sync and async functions.
 *
 * Wrapped functions:
 *  1. Take the same inputs and return the same outputs as the original function.
 *  2. Will automatically track calls in the Weave UI.
 *
 * If you don't call `weave.init` then the function will behave as if it were not wrapped.
 *
 * @param fn The function to wrap
 * @param options Optional configs like call and param naming
 * @returns The wrapped function
 *
 * @example
 * // Basic function wrapping
 * import OpenAI from 'openai';
 * import * as weave from 'weave';
 *
 * const client = await weave.init({ project: 'my-project' });
 * const oaiClient = weave.wrapOpenAI(new OpenAI());
 *
 * const extract = weave.op(async function extract() {
 *   return await oaiClient.chat.completions.create({
 *     model: 'gpt-4-turbo',
 *     messages: [{ role: 'user', content: 'Create a user as JSON' }],
 *   });
 * });
 *
 * await extract();
 *
 * // Method binding using getOwnPropertyDescriptor
 * class MyModel {
 *   private oaiClient: OpenAI;
 *   public invoke: Op<(prompt: string) => Promise<string>>;
 *
 *   constructor() {
 *     this.oaiClient = weave.wrapOpenAI(new OpenAI());
 *     this.invoke = weave.op(this, this.invoke);
 *   }
 *
 *   async invoke(prompt: string) {
 *     return await this.oaiClient.chat.completions.create({
 *       model: 'gpt-4-turbo',
 *       messages: [{ role: 'user', content: prompt }],
 *     });
 *   }
 * }
 *
 * // Decorator usage (requires TS 5.0+ or legacy TS with experimentalDecorators: true in tsconfig.json)
 * class DecoratedModel {
 *   // Basic decorator
 *   @weave.op
 *   async invoke() {
 *     return await this.oaiClient.chat.completions.create({
 *       model: 'gpt-4-turbo',
 *       messages: [{ role: 'user', content: 'Create a user as JSON' }],
 *     });
 *   }
 *
 *   // Decorator with options
 *   @(weave.op({
 *     name: 'customName',
 *     callDisplayName: (...args) => `Processing: ${args[0]}`,
 *     parameterNames: ['input']
 *   }) as any)
 *   static async process(input: string) {
 *     return `Processed ${input}`;
 *   }
 * }
 *
 */
// Function wrapping: const op = weave.op(fn)
export function op<T extends (...args: any[]) => any>(
  fn: T,
  options?: OpOptions<T>
): Op<T>;
// Method binding: const op = weave.op(this, fn)
export function op<T extends (...args: any[]) => any>(
  thisArg: any,
  fn: T,
  options?: OpOptions<T>
): Op<T>;
// Legacy decorator usage (experimentalDecorators in tsconfig.json): @weave.op
export function op(
  target: Object,
  propertyKey: string | symbol,
  descriptor: TypedPropertyDescriptor<any>
): void;
// Stage 3 method decorator usage (decorators in tsconfig.json): @weave.op
export function op<T extends (...args: any[]) => any>(
  value: T,
  context: MethodDecoratorContext
): Op<T>;
// Decorator factory usage: @weave.op({ ... })
export function op(options: Partial<OpOptions<any>>): MethodDecorator;
export function op(...args: any[]): any {
  // ─────────────────────────────
  // Stage 3 decorators support
  if (isOfficiallDecorator(args)) {
    // Destructure the decorated value and the context
    const [originalMethod, context] = args;
    // We only support methods with Stage 3 for now
    if (context.kind === 'method') {
      // Call our base function-wrapping version of op without a name yet
      const wrapped = op(originalMethod, {
        name: "__pending__",
        isDecorator: true,
        originalFunction: originalMethod,
      }) as Op<typeof originalMethod>;
      // Set our name via the addInitializer hook
      extractClassName(wrapped, context);

      // Return the replacement method (as expected by Stage 3 decorators)
      return wrapped;
    } else {
      throw new Error('@weave.op currently only supports method decorators (Stage 3)');
    }
  }

  // ─────────────────────────────
  // Legacy decorator branch: called with (target, propertyKey, descriptor)
  if (
    args.length === 3 &&
    (typeof args[0] === 'object' || typeof args[0] === 'function') &&
    (typeof args[1] === 'string' || typeof args[1] === 'symbol') &&
    typeof args[2] === 'object'
  ) {
    const [target, propertyKey, descriptor] = args;
    const originalFn = descriptor.value;
    if (typeof originalFn !== 'function') {
      throw new Error('@weave.op can only be used to decorate methods');
    }
    const className = extractClassName(target);
    const name = `${className}.${String(propertyKey)}`;

    const wrapped = op(originalFn, {
      name,
      isDecorator: true,
      originalFunction: originalFn,
    }) as Op<typeof originalFn>;
    descriptor.value = wrapped;
    return descriptor;
  }

  // ─────────────────────────────
  // Decorator factory branch: @weave.op({...})
  if (
    args.length === 1 &&
    typeof args[0] === 'object' &&
    !('prototype' in args[0]) &&
    !('bind' in args[0]) &&
    !Array.isArray(args[0])
  ) {
    const options = args[0];
    return function (...factoryArgs: any[]) {
      // Detect Stage 3 form in the returned decorator
      if (isOfficiallDecorator(factoryArgs)) {
        const [originalMethod, context] = factoryArgs;
        if (context.kind === 'method') {
          const wrapped = op(originalMethod, {
            ...options,
            name: options.name || "__pending__",
            isDecorator: true,
            originalFunction: originalMethod
          });
          extractClassName(wrapped, context);
          return wrapped;
        }
        throw new Error('@weave.op currently supports factory usage only on methods (Stage 3).');
      }

      // Legacy usage branch within the factory
      const [target, propertyKey, descriptor] = factoryArgs;
      const originalMethod = descriptor.value;
      if (typeof originalMethod !== 'function') {
        throw new Error('@weave.op can only be used to decorate methods');
      }
      const className = extractClassName(target);
      const name = options?.name || `${className}.${String(propertyKey)}`;

      const wrapped = op(originalMethod, {
        ...options,
        name,
        isDecorator: true,
        originalFunction: originalMethod,
      });

      descriptor.value = wrapped;
      return descriptor;
    };
  }

  // ─────────────────────────────
  // Function binding branch: op(this, fn, options)
  if (args.length >= 2 && typeof args[1] === 'function') {
    const [bindThis, fn, options] = args;
    const boundFn = fn.bind(bindThis);
    return op(boundFn, {
      originalFunction: fn,
      bindThis,
      ...options,
    });
  }

  // ─────────────────────────────
  // Base case: Direct function wrapping: op(fn, options?)
  const fn = args[0];
  const options = args[1] || {};
  type T = typeof fn;

  // Create the wrapper function that tracks calls
  const opWrapper = async function (
    this: any,
    ...params: Parameters<T>
  ): Promise<ReturnType<T>> {
    const client = getGlobalClient();
    const thisArg = options?.isDecorator ? this : options?.bindThis;

    if (!client) {
      warnOnce(
        'weave-not-initialized',
        'WARNING: Weave is not initialized, so calls won\'t be tracked. Call `weave.init` to initialize before calling ops. If this is intentional, you can safely ignore this warning.'
      );
      return await fn.apply(thisArg, params);
    }

    const { currentCall, parentCall, newStack } = client.pushNewCall();
    const startTime = new Date();
    if (client.settings.shouldPrintCallLink && parentCall == null) {
      const domain = getGlobalDomain();
      console.log(
        `${TRACE_CALL_EMOJI} https://${domain}/${client.projectId}/r/call/${currentCall.callId}`
      );
    }
    const displayName = options?.callDisplayName
      ? options.callDisplayName(...params)
      : undefined;
    const startCallPromise = client.createCall(
      opWrapper,
      params,
      options?.parameterNames,
      thisArg,
      currentCall,
      parentCall,
      startTime,
      displayName
    );

    try {
      let result = await client.runWithCallStack(newStack, async () => {
        return await fn.apply(thisArg, params);
      });

      if (options?.streamReducer && Symbol.asyncIterator in result) {
        const { initialStateFn, reduceFn } = options.streamReducer;
        let state = initialStateFn();

        const wrappedIterator = {
          [Symbol.asyncIterator]: async function* () {
            try {
              for await (const chunk of result as AsyncIterable<any>) {
                state = reduceFn(state, chunk);
                yield chunk;
              }
            } finally {
              if (client) {
                const endTime = new Date();
                await client.finishCall(
                  state,
                  currentCall,
                  parentCall,
                  options?.summarize,
                  endTime,
                  startCallPromise
                );
              }
            }
          },
        };

        return wrappedIterator as unknown as ReturnType<T>;
      } else {
        const endTime = new Date();
        await client.finishCall(
          result,
          currentCall,
          parentCall,
          options?.summarize,
          endTime,
          startCallPromise
        );
        return result;
      }
    } catch (error) {
      const endTime = new Date();
      await client.finishCallWithException(
        error,
        currentCall,
        parentCall,
        endTime,
        startCallPromise
      );
      await client.waitForBatchProcessing();
      throw error;
    }
  };

  const fnName = options?.originalFunction?.name || fn.name || 'anonymous';
  const className = options?.bindThis
    ? Object.getPrototypeOf(options.bindThis).constructor.name
    : undefined;
  const actualOpName = options?.name || (className ? `${className}.${fnName}` : fnName);

  // Set properties on the wrapper function
  opWrapper.__name = actualOpName;
  opWrapper.__isOp = true as const;
  opWrapper.__wrappedFunction = options?.originalFunction ?? fn;
  opWrapper.__boundThis = options?.bindThis;

  return opWrapper as Op<T>;
}

export function isOp(fn: any): fn is Op<any> {
  return fn?.__isOp === true;
}
