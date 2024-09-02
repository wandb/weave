import { uuidv7 } from 'uuidv7';
import { globalClient, processWeaveValues } from "./clientApi";
import { packageVersion } from "./userAgent";

import { WeaveClient } from "./clientApi";
import { WeaveObject, getClassChain } from './weaveObject';
import { OpOptions, Op, isOp, getOpName, getOpWrappedFunction, OpRef } from './opType';
import { CallStackEntry, CallStack } from './clientApi';

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

        const opRef = await globalClient.saveOp(opWrapper);

        // Process WeaveImage in inputs
        const processedArgs = await Promise.all(params.map(processWeaveValues));
        // @ts-ignore
        const initialInputs = thisArg instanceof WeaveObject ? {
            this: thisArg
        } : {};
        const inputs = processedArgs.reduce((acc, arg, index) => ({ ...acc, [`arg${index}`]: arg }), initialInputs);
        const savedInputs = await globalClient.saveObjectAndOps(inputs);

        const { newStack, currentCall, parentCall } = globalClient.pushNewCall();
        const callId = currentCall.callId;
        const traceId = currentCall.traceId;
        const parentId = parentCall?.callId;

        const startTime = new Date().toISOString();

        const startReq = {
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

        globalClient.saveCallStart(startReq);

        try {
            let result = await globalClient.runWithCallStack(newStack, async () => {
                return await fn(...processedArgs);
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
                                state = await processWeaveValues(state);
                                const endTime = new Date().toISOString();
                                const mergedSummary = processSummary(state, options?.summarize, currentCall, parentCall);
                                const endReq = globalClient.createEndReq(callId, endTime, state, mergedSummary);
                                globalClient.saveCallEnd(endReq);
                            }
                            // If globalClient is null, we do nothing, as requested
                        }
                    }
                };

                return wrappedIterator as unknown as ReturnType<T>;
            } else {
                result = await processWeaveValues(result);
                const endTime = new Date().toISOString();
                const mergedSummary = processSummary(result, options?.summarize, currentCall, parentCall);
                const endReq = globalClient.createEndReq(callId, endTime, result, mergedSummary);
                globalClient.saveCallEnd(endReq);
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
            globalClient.saveCallEnd(endReq);
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

/**
 * Represents a summary object with string keys and any type of values.
 */
type Summary = Record<string, any>;

/**
 * Merges two summary objects, combining their values.
 * 
 * @param left - The first summary object to merge.
 * @param right - The second summary object to merge.
 * @returns A new summary object containing the merged values.
 * 
 * This function performs a deep merge of two summary objects:
 * - For numeric values, it adds them together.
 * - For nested objects, it recursively merges them.
 * - For other types, the left value "wins".
 */
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
    currentCall: CallStackEntry,
    parentCall: CallStackEntry | undefined
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
