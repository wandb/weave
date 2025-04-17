import {getGlobalClient} from './clientApi';
import {TRACE_CALL_EMOJI} from './constants';
import {Op, OpOptions} from './opType';
import {getGlobalDomain} from './urls';
import {warnOnce} from './utils/warnOnce';

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
 *     // Get the original method and wrap it
 *     const descriptor = Object.getOwnPropertyDescriptor(MyModel.prototype, 'invoke')!;
 *     this.invoke = weave.op(this, descriptor.value);
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
 * // Decorator usage (requires experimentalDecorators: true in tsconfig.json)
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
 *   @weave.op({
 *     name: 'customName',
 *     callDisplayName: (...args) => `Processing: ${args[0]}`,
 *     parameterNames: ['input']
 *   })
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
): Op<(...args: Parameters<T>) => Promise<Awaited<ReturnType<T>>>>;
// Method binding: const op = weave.op(this, fn)
export function op<T extends (...args: any[]) => any>(
  thisArg: any,
  fn: T,
  options?: OpOptions<T>
): Op<(...args: Parameters<T>) => Promise<Awaited<ReturnType<T>>>>;
// Decorator usage: @weave.op
export function op(
  target: Object,
  propertyKey: string | symbol,
  descriptor: TypedPropertyDescriptor<any>
): void;
// Decorator factory usage: @weave.op({...})
export function op(options: Partial<OpOptions<any>>): MethodDecorator;
export function op(...args: any[]): any {
  // Case 1: Basic decorator - @op
  // args = [target (class/prototype), propertyKey (string), descriptor (PropertyDescriptor)]
  if (
    args.length === 3 &&
    (typeof args[0] === 'object' || typeof args[0] === 'function') &&
    typeof args[1] === 'string' &&
    typeof args[2] === 'object'
  ) {
    const [target, propertyKey, descriptor] = args;
    const originalFn = descriptor.value;
    if (typeof originalFn !== 'function') {
      throw new Error('@weave.op can only be used to decorate methods');
    }

    const isStatic = typeof target === 'function';
    const className = isStatic ? target.name : target.constructor?.name ?? 'anonymous';
    const name = `${className}.${String(propertyKey)}`;

    // Recursively call op() to create the wrapper, passing the function and options
    const wrapped = op(originalFn, {
      name,
      isDecorator: true,
      originalFunction: originalFn
    }) as Op<typeof originalFn>;

    // Update the descriptor
    descriptor.value = wrapped;

    return descriptor;
  }

  // Case 2: Decorator factory - @op({...options})
  // args = [{...options}]
  if (
    args.length === 1 &&
    typeof args[0] === 'object' &&
    !('prototype' in args[0]) &&
    !('bind' in args[0]) &&
    !Array.isArray(args[0])
  ) {
    const options = args[0];
    // Return a decorator function that will be called with (target, propertyKey, descriptor)
    return function (
      target: Object,
      propertyKey: string | symbol,
      descriptor: TypedPropertyDescriptor<any>
    ) {
      const originalFn = descriptor.value;
      if (typeof originalFn !== 'function') {
        throw new Error('@weave.op can only be used to decorate methods');
      }

      const isStatic = typeof target === 'function';
      const className = isStatic ? target.name : target.constructor?.name ?? 'anonymous';
      const name = options?.name || `${className}.${String(propertyKey)}`;

      // Recursively call op() to create the wrapper, passing the function and merged options
      const wrapped = op(originalFn, {
        ...options,
        name,
        isDecorator: true,
        originalFunction: originalFn
      });

      // Update the descriptor
      descriptor.value = wrapped;

      return descriptor;
    };
  }

  // Case 3: Function wrapping with binding - op(this, fn, options)
  // args = [thisArg, function, options?]
  if (args.length >= 2 && typeof args[1] === 'function') {
    const [bindThis, fn, options] = args;
    const boundFn = fn.bind(bindThis);
    return op(boundFn, {
      originalFunction: fn,
      bindThis,
      ...options
    });
  }

  // Case 4: Direct function wrapping - op(fn, options?)
  // args = [function, options?]
  // This is our base case that actually creates the wrapper
  const fn = args[0];
  const options = args[1] || {};
  type T = typeof fn;

  // Create the wrapper function that handles call tracking
  const opWrapper = async function (this: any, ...params: Parameters<T>): Promise<ReturnType<T>> {
    const client = getGlobalClient();
    const thisArg = options?.isDecorator ? this : options?.bindThis;

    if (!client) {
      warnOnce(
        'weave-not-initialized',
        'WARNING: Weave is not initialized, so calls wont be tracked. Call `weave.init` to initialize before calling ops. If this is intentional, you can safely ignore this warning.'
      );
      return await fn.apply(thisArg, params);
    }

    const {currentCall, parentCall, newStack} = client.pushNewCall();
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
        const {initialStateFn, reduceFn} = options.streamReducer;
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
      // console.error(`Op ${actualOpName} failed:`, error);
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

  // Set the name based on the context
  const fnName = options?.originalFunction?.name || fn.name || 'anonymous';
  const className = options?.bindThis
    ? Object.getPrototypeOf(options.bindThis).constructor.name
    : undefined;
  const actualOpName = options?.name || (className ? `${className}.${fnName}` : fnName);

  // Set properties on the wrapper function
  opWrapper.__name = actualOpName;
  opWrapper.__isOp = true;
  opWrapper.__wrappedFunction = options?.originalFunction ?? fn;
  opWrapper.__boundThis = options?.bindThis;

  return opWrapper as Op<T>;
}

export function isOp(fn: any): fn is Op<any> {
  return fn?.__isOp === true;
}
