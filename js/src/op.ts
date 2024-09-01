import { uuidv7 } from 'uuidv7';
import { globalClient, processWeaveValues } from "./clientApi";
import { packageVersion } from "./userAgent";

import { WeaveClient, asyncLocalStorage } from "./clientApi";
import { WeaveObject, getClassChain } from './weaveObject';
import { OpOptions, Op, isOp, getOpName, getOpWrappedFunction, OpRef } from './opType';

export function op<T extends (...args: any[]) => any>(
    fn: T,
    options?: OpOptions<T>
): Op<(...args: Parameters<T>) => Promise<ReturnType<T>>> {
    const fnName = options?.originalFunction?.name || fn.name || 'anonymous';
    let actualOpName = fnName;
    if (options?.bindThis) {
        actualOpName = `${options.bindThis.className()}.${fnName}`;
    }
    if (options?.name) {
        actualOpName = options.name;
    }

    const opWrapper = async function (...args: Parameters<T>): Promise<ReturnType<T>> {
        // Use the bound 'this' if available, otherwise use the current 'this'
        const thisArg = options?.bindThis;

        // @ts-ignore
        if (!globalClient) {
            return await fn(...args);
        }

        const store = asyncLocalStorage.getStore() || { callStack: [] };
        const startTime = new Date().toISOString();
        const callId = generateCallId();
        let traceId: string;
        let parentId: string | null = null;

        if (store.callStack.length === 0) {
            traceId = generateTraceId();
        } else {
            const parentCall = store.callStack[store.callStack.length - 1];
            traceId = parentCall.traceId;
            parentId = parentCall.callId;
        }

        store.callStack.push({ callId, traceId, childSummary: {} });

        if (store.callStack.length === 1) {
            console.log(`🍩 https://wandb.ai/${globalClient.projectId}/r/call/${callId}`);
        }

        // Process WeaveImage in inputs
        const processedArgs = await Promise.all(args.map(processWeaveValues));
        // @ts-ignore
        const initialInputs = thisArg instanceof WeaveObject ? {
            this: thisArg
        } : {};
        const inputs = processedArgs.reduce((acc, arg, index) => ({ ...acc, [`arg${index}`]: arg }), initialInputs);
        const savedInputs = await globalClient.saveObjectAndOps(inputs);
        console.log('savedInputs', savedInputs);
        // const savedInputs: { [key: string]: any } = {};
        // for (const [key, value] of Object.entries(inputs)) {
        //     if (value instanceof WeaveObject) {
        //         savedInputs[key] = (await globalClient.saveObject(value)).uri();
        //     } else if (isOp(value)) {
        //         savedInputs[key] = (await saveOp(globalClient, value)).uri();
        //     } else {
        //         savedInputs[key] = value;
        //     }
        // }

        const opRef = await globalClient.saveOp(opWrapper);

        const startReq = {
            start: {
                project_id: globalClient.projectId,
                id: callId,
                op_name: opRef.uri(),
                trace_id: traceId,
                parent_id: parentId,
                started_at: startTime,
                attributes: {
                    weave: {
                        client_version: packageVersion,
                        source: 'js-sdk'
                    }
                },
                inputs: savedInputs
            }
        };

        globalClient.callQueue.push({ mode: 'start', data: startReq });
        globalClient.scheduleBatchProcessing();

        try {
            let result = await asyncLocalStorage.run(store, async () => {
                return await fn(...processedArgs);
            });

            if (options?.streamReducer && Symbol.asyncIterator in result) {
                const { initialState, reduceFn } = options.streamReducer;
                let state = initialState;
                const currentCall = store.callStack[store.callStack.length - 1];
                const parentCall = store.callStack.length > 1 ? store.callStack[store.callStack.length - 2] : undefined;

                const wrappedIterator = {
                    [Symbol.asyncIterator]: async function* () {
                        try {
                            for await (const chunk of result as AsyncIterable<any>) {
                                state = reduceFn(state, chunk);
                                yield chunk;
                            }
                        } finally {
                            if (globalClient) { // Check if globalClient still exists
                                state = await processWeaveValues(state);
                                const endTime = new Date().toISOString();
                                const mergedSummary = processSummary(state, options?.summarize, currentCall, parentCall);
                                const endReq = globalClient.createEndReq(callId, endTime, state, mergedSummary);
                                globalClient.callQueue.push({ mode: 'end', data: endReq });
                                globalClient.scheduleBatchProcessing();
                            }
                            // If globalClient is null, we do nothing, as requested
                        }
                    }
                };

                return wrappedIterator as unknown as ReturnType<T>;
            } else {
                result = await processWeaveValues(result);
                const endTime = new Date().toISOString();
                const currentCall = store.callStack[store.callStack.length - 1];
                const parentCall = store.callStack.length > 1 ? store.callStack[store.callStack.length - 2] : undefined;
                const mergedSummary = processSummary(result, options?.summarize, currentCall, parentCall);
                const endReq = globalClient.createEndReq(callId, endTime, result, mergedSummary);
                globalClient.callQueue.push({ mode: 'end', data: endReq });
                globalClient.scheduleBatchProcessing();
                return result;
            }
        } catch (error) {
            console.error(`Op ${actualOpName} failed:`, error);
            const endTime = new Date().toISOString();
            const endReq = globalClient.createEndReq(
                callId,
                endTime,
                null,
                {},
                error instanceof Error ? error.message : String(error)
            );
            globalClient.callQueue.push({ mode: 'end', data: endReq });
            globalClient.scheduleBatchProcessing();
            throw error;
        } finally {
            store.callStack.pop();
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
    const thisClass = getClassChain(bindThis)[0];
    // return op(fn, { originalFunction: fn, name: `${thisClass}.${fn.name}`, bindThis });
    return op(fn.bind(bindThis), { originalFunction: fn, bindThis });
}

function generateTraceId(): string {
    return uuidv7();
}

function generateCallId(): string {
    return uuidv7();
}

type Summary = Record<string, any>;
function mergeSummaries(left: Summary, right: Summary): Summary {
    const result: Summary = { ...right };
    for (const [key, leftValue] of Object.entries(left)) {
        if (key in result) {
            if (typeof leftValue === 'number' && typeof result[key] === 'number') {
                result[key] = leftValue + result[key];
            } else if (typeof leftValue === 'object' && typeof result[key] === 'object') {
                result[key] = mergeSummaries(leftValue, result[key]);
            } else {
                result[key] = leftValue;
            }
        } else {
            result[key] = leftValue;
        }
    }
    return result;
}

function processSummary(
    result: any,
    summarize: ((result: any) => Record<string, any>) | undefined,
    currentCall: { childSummary: Summary },
    parentCall: { childSummary: Summary } | undefined
) {
    let ownSummary = summarize ? summarize(result) : {};

    if (ownSummary.usage) {
        for (const model in ownSummary.usage) {
            if (typeof ownSummary.usage[model] === 'object') {
                ownSummary.usage[model] = {
                    requests: 1,
                    ...ownSummary.usage[model],
                };
            }
        }
    }

    const mergedSummary = mergeSummaries(ownSummary, currentCall.childSummary);

    if (parentCall) {
        parentCall.childSummary = mergeSummaries(mergedSummary, parentCall.childSummary);
    }

    return mergedSummary;
}
