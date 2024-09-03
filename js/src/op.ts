import { globalClient } from './clientApi';
import { OpOptions, Op } from './opType';

export function op<T extends (...args: any[]) => any>(
    fn: T,
    options?: OpOptions<T>
): Op<(...args: Parameters<T>) => Promise<ReturnType<T>>> {
    const fnName = options?.originalFunction?.name || fn.name || 'anonymous';
    let actualOpName = fnName;
    const thisArg = options?.bindThis;
    if (options?.bindThis) {
        actualOpName = `${options.bindThis.className()}.${fnName}`;
    }
    if (options?.name) {
        actualOpName = options.name;
    }

    const opWrapper = async function (...params: Parameters<T>): Promise<ReturnType<T>> {
        if (!globalClient) {
            return await fn(...params);
        }

        const { newStack, currentCall, parentCall } = globalClient.pushNewCall();
        const startTime = new Date();
        if (!globalClient.quiet && parentCall == null) {
            console.log(`🍩 https://wandb.ai/${globalClient.projectId}/r/call/${currentCall.callId}`);
        }
        const startCallPromise = globalClient.startCall(opWrapper, params, thisArg, currentCall, parentCall, startTime);

        try {
            let result = await globalClient.runWithCallStack(newStack, async () => {
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
                            if (globalClient) { // Check if globalClient still exists
                                const endTime = new Date();
                                await globalClient.finishCall(state, currentCall, parentCall, options?.summarize, endTime, startCallPromise);
                            }
                        }
                    }
                };

                return wrappedIterator as unknown as ReturnType<T>;
            } else {
                const endTime = new Date();
                globalClient.finishCall(result, currentCall, parentCall, options?.summarize, endTime, startCallPromise);
                return result;
            }
        } catch (error) {
            // console.error(`Op ${actualOpName} failed:`, error);
            const endTime = new Date();
            globalClient.finishCallWithException(error, currentCall, endTime, startCallPromise);
            throw error;
        } finally {
            // No need to do anything here.
        }
    };

    opWrapper.__name = actualOpName;
    opWrapper.__isOp = true as true;
    if (options?.originalFunction) {
        opWrapper.wrappedFunction = options.originalFunction;
    } else {
        opWrapper.wrappedFunction = fn;
    }

    if (options?.bindThis !== undefined) {
        opWrapper.__boundThis = options.bindThis;
    }

    return opWrapper as Op<T>;
}

export function boundOp(bindThis: any, fn: (...args: any[]) => any) {
    return op(fn.bind(bindThis), { originalFunction: fn, bindThis });
}