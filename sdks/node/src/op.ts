import { getGlobalClient } from './clientApi';
import { TRACE_CALL_EMOJI } from './constants';
import { Op, OpOptions } from './opType';
import { warnOnce } from './utils/warnOnce';

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
 * // Basic usage
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
 */
export function op<T extends (...args: any[]) => any>(
  fn: T,
  options?: OpOptions<T>
): Op<(...args: Parameters<T>) => Promise<Awaited<ReturnType<T>>>> {
  const opWrapper = async function (...params: Parameters<T>): Promise<ReturnType<T>> {
    const client = getGlobalClient();

    if (!client) {
      warnOnce(
        'weave-not-initialized',
        'WARNING: Weave is not initialized, so calls wont be tracked.  Call `weave.init` to initialize before calling ops.  If this is intentional, you can safely ignore this warning.'
      );
      return await fn(...params);
    }

    const { currentCall, parentCall, newStack } = client.pushNewCall();
    const startTime = new Date();
    if (client.settings.shouldPrintCallLink && parentCall == null) {
      console.log(`${TRACE_CALL_EMOJI} https://${client.urls.domain}/${client.projectId}/r/call/${currentCall.callId}`);
    }
    const displayName = options?.callDisplayName ? options.callDisplayName(...params) : undefined;
    const thisArg = options?.bindThis;
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
        return await fn(...params);
      });

      if (options?.streamReducer && Symbol.asyncIterator in result) {
        const { initialState, reduceFn } = options.streamReducer;
        let state = initialState;

        const wrappedIterator = {
          [Symbol.asyncIterator]: async function* () {
            try {
              for await (const chunk of result as AsyncIterable<any>) {
                state = reduceFn(state, chunk);
                yield chunk;
              }
            } finally {
              if (client) {
                // Check if globalClient still exists
                const endTime = new Date();
                await client.finishCall(state, currentCall, parentCall, options?.summarize, endTime, startCallPromise);
              }
            }
          },
        };

        return wrappedIterator as unknown as ReturnType<T>;
      } else {
        const endTime = new Date();
        await client.finishCall(result, currentCall, parentCall, options?.summarize, endTime, startCallPromise);
        return result;
      }
    } catch (error) {
      // console.error(`Op ${actualOpName} failed:`, error);
      const endTime = new Date();
      await client.finishCallWithException(error, currentCall, parentCall, endTime, startCallPromise);
      await client.waitForBatchProcessing();
      throw error;
    }
  };

  const fnName = options?.originalFunction?.name || fn.name || 'anonymous';
  const className = options?.bindThis && Object.getPrototypeOf(options.bindThis).constructor.name;
  const actualOpName = options?.name || (className ? `${className}.${fnName}` : fnName);

  opWrapper.__name = actualOpName;
  opWrapper.__isOp = true as true;
  opWrapper.__wrappedFunction = options?.originalFunction ?? fn;
  opWrapper.__boundThis = options?.bindThis;

  return opWrapper as Op<T>;
}

export function isOp(fn: any): fn is Op<any> {
  return fn?.__isOp === true;
}

export function boundOp<T extends (...args: any[]) => any>(bindThis: any, fn: T, options?: OpOptions<T>) {
  const boundFn = fn.bind(bindThis) as T;
  return op(boundFn, { originalFunction: fn, bindThis, ...options });
}
