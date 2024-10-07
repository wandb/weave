import {globalClient} from './client-api';
import {TRACE_CALL_EMOJI, WANDB_URL} from './constants';
import {Op, OpOptions} from './op-type';

export function op<T extends (...args: any[]) => any>(
  fn: T,
  options?: OpOptions<T>
): Op<(...args: Parameters<T>) => Promise<Awaited<ReturnType<T>>>> {
  // Step 1: Determine the operation name
  const fnName = options?.originalFunction?.name || fn.name || 'anonymous';
  const thisArg = options?.bindThis;

  let actualOpName = fnName;
  if (options?.bindThis) {
    const className = Object.getPrototypeOf(options.bindThis).constructor.name;
    actualOpName = `${className}.${fnName}`;
  }
  if (options?.name) {
    actualOpName = options.name;
  }

  // Step 2: Define the wrapper function
  const opWrapper = async function (...params: Parameters<T>): Promise<ReturnType<T>> {
    // Step 2.1: Check if globalClient exists
    if (!globalClient) {
      return await fn(...params);
    }

    // Step 2.2: Set up call context
    const {newStack, currentCall, parentCall} = globalClient.pushNewCall();
    const startTime = new Date();
    if (!globalClient.settings.quiet && parentCall == null) {
      console.log(`${TRACE_CALL_EMOJI} ${WANDB_URL}/${globalClient.projectId}/r/call/${currentCall.callId}`);
    }
    const displayName = options?.callDisplayName ? options.callDisplayName(...params) : undefined;
    const startCallPromise = globalClient.startCall(
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
      // Step 2.3: Execute the wrapped function
      let result = await globalClient.runWithCallStack(newStack, async () => {
        return await fn(...params);
      });

      // Step 2.4: Handle stream reducer if applicable
      if (options?.streamReducer && Symbol.asyncIterator in result) {
        const {initialState, reduceFn} = options.streamReducer;
        let state = initialState;

        const wrappedIterator = {
          [Symbol.asyncIterator]: async function* () {
            try {
              for await (const chunk of result as AsyncIterable<any>) {
                state = reduceFn(state, chunk);
                yield chunk;
              }
            } finally {
              if (globalClient) {
                // Check if globalClient still exists
                const endTime = new Date();
                await globalClient.finishCall(
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
        // Step 2.5: Finish the call and return the result
        const endTime = new Date();
        globalClient.finishCall(result, currentCall, parentCall, options?.summarize, endTime, startCallPromise);
        return result;
      }
    } catch (error) {
      // Step 2.6: Handle errors
      const endTime = new Date();
      globalClient.finishCallWithException(error, currentCall, parentCall, endTime, startCallPromise);
      throw error;
    } finally {
      // No need to do anything here.
    }
  };

  // Step 3: Set metadata on the wrapper function
  opWrapper.__name = actualOpName;
  opWrapper.__isOp = true as true;
  opWrapper.__wrappedFunction = options?.originalFunction ?? fn;
  opWrapper.__boundThis = options?.bindThis;

  // Step 4: Return the wrapped function
  return opWrapper as Op<T>;
}

export function isOp(fn: any): fn is Op<any> {
  if (fn == null) {
    return false;
  }
  return fn.__isOp === true;
}

export function boundOp<T extends (...args: any[]) => any>(bindThis: any, fn: T, options?: OpOptions<T>) {
  const boundFn = fn.bind(bindThis) as T;
  return op(boundFn, {originalFunction: fn, bindThis, ...options});
}
