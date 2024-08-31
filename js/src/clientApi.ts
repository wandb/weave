import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { uuidv7 } from 'uuidv7';
import { Api as TraceServerApi } from './traceServerApi';
import { WandbServerApi } from './wandbServerApi';
import { packageVersion } from './userAgent';
import { InMemoryTraceServer } from './inMemoryTraceServer';
import { AsyncLocalStorage } from 'async_hooks';

// Create an AsyncLocalStorage instance
const asyncLocalStorage = new AsyncLocalStorage<{
    callStack: { callId: string; traceId: string; childSummary: Summary }[]
}>();

let traceServerApi: TraceServerApi<any>;
let wandbServerApi: WandbServerApi;
let globalProjectName: string;
let activeCallStack: { callId: string; traceId: string }[] = [];

// Queue for batching calls
let callQueue: Array<{ mode: 'start' | 'end', data: any }> = [];
let batchProcessTimeout: NodeJS.Timeout | null = null;
let isBatchProcessing = false;
const BATCH_INTERVAL = 200; // 200 milliseconds

function readApiKeyFromNetrc(host: string): string | undefined {
    const netrcPath = path.join(os.homedir(), '.netrc');
    if (!fs.existsSync(netrcPath)) {
        return undefined;
    }

    const netrcContent = fs.readFileSync(netrcPath, 'utf-8');
    const lines = netrcContent.split('\n');
    let foundMachine = false;
    for (const line of lines) {
        const trimmedLine = line.trim();
        if (trimmedLine.startsWith('machine') && trimmedLine.includes(host)) {
            foundMachine = true;
        } else if (foundMachine && trimmedLine.startsWith('password')) {
            return trimmedLine.split(' ')[1];
        }
    }
    return undefined;
}

async function init(projectName: string): Promise<void> {
    const host = 'https://api.wandb.ai';
    const apiKey = readApiKeyFromNetrc('api.wandb.ai');

    if (!apiKey) {
        throw new Error("API key not found in .netrc file");
    }

    const headers: Record<string, string> = {
        'User-Agent': `W&B Internal JS Client ${process.env.VERSION || 'unknown'}`,
        'Authorization': `Basic ${Buffer.from(`api:${apiKey}`).toString('base64')}`
    };

    try {
        // Initialize WandbApi
        wandbServerApi = new WandbServerApi(host, apiKey);

        // Get default entity name
        const defaultEntityName = await wandbServerApi.defaultEntityName();

        // Set global project name
        globalProjectName = `${defaultEntityName}/${projectName}`;

        traceServerApi = new TraceServerApi({
            baseUrl: 'https://trace.wandb.ai',
            baseApiParams: {
                headers: headers,
            },
        });

        console.log(`Initializing project: ${globalProjectName}`);
    } catch (error) {
        console.error("Error during initialization:", error);
        throw error;
    }
}

function scheduleBatchProcessing() {
    if (batchProcessTimeout || isBatchProcessing) return;
    batchProcessTimeout = setTimeout(processBatch, BATCH_INTERVAL);
}

async function processBatch() {
    if (isBatchProcessing || callQueue.length === 0) {
        batchProcessTimeout = null;
        return;
    }

    isBatchProcessing = true;

    const batchToProcess = [...callQueue];
    callQueue = [];

    const batchReq = {
        batch: batchToProcess.map(item => ({
            mode: item.mode,
            req: item.data
        }))
    };

    try {
        await traceServerApi.call.callStartBatchCallUpsertBatchPost(batchReq);
    } catch (error) {
        console.error('Error processing batch:', error);
    } finally {
        isBatchProcessing = false;
        batchProcessTimeout = null;
        if (callQueue.length > 0) {
            scheduleBatchProcessing();
        }
    }
}

interface OpOptions<T extends (...args: any[]) => any> {
    name?: string;
    streamReducer?: StreamReducer<any, any>;
    summarize?: (result: Awaited<ReturnType<T>>) => Record<string, any>;
}

// Add this new type and function
type Summary = Record<string, any>;

interface StreamReducer<T, R> {
    initialState: R;
    reduceFn: (state: R, chunk: T) => R;
}

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

function createEndReq(callId: string, endTime: string, output: any, summary: Summary, exception?: string) {
    return {
        end: {
            project_id: globalProjectName,
            id: callId,
            ended_at: endTime,
            output,
            summary,
            ...(exception && { exception }),
        }
    };
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

function op<T extends (...args: any[]) => any>(
    fn: T,
    options?: OpOptions<T>
): (...args: Parameters<T>) => Promise<ReturnType<T>> {
    const actualOpName = options?.name || fn.name || 'anonymous';

    return async function (...args: Parameters<T>): Promise<ReturnType<T>> {
        if (!globalProjectName) {
            throw new Error("Project not initialized. Call init() first.");
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
            console.log(`🍩 https://wandb.ai/${globalProjectName}/r/call/${callId}`);
        }

        const startReq = {
            start: {
                project_id: globalProjectName,
                id: callId,
                op_name: actualOpName,
                trace_id: traceId,
                parent_id: parentId,
                started_at: startTime,
                attributes: {
                    weave: {
                        client_version: packageVersion,
                        source: 'js-sdk'
                    }
                },
                inputs: args.reduce((acc, arg, index) => ({ ...acc, [`arg${index}`]: arg }), {}),
            }
        };

        callQueue.push({ mode: 'start', data: startReq });
        scheduleBatchProcessing();

        try {
            const result = await asyncLocalStorage.run(store, async () => {
                return await fn(...args);
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
                            const endTime = new Date().toISOString();
                            const mergedSummary = processSummary(state, options?.summarize, currentCall, parentCall);
                            const endReq = createEndReq(callId, endTime, state, mergedSummary);
                            callQueue.push({ mode: 'end', data: endReq });
                            scheduleBatchProcessing();
                        }
                    }
                };

                return wrappedIterator as unknown as ReturnType<T>;
            } else {
                const endTime = new Date().toISOString();
                const currentCall = store.callStack[store.callStack.length - 1];
                const parentCall = store.callStack.length > 1 ? store.callStack[store.callStack.length - 2] : undefined;
                const mergedSummary = processSummary(result, options?.summarize, currentCall, parentCall);
                const endReq = createEndReq(callId, endTime, result, mergedSummary);
                callQueue.push({ mode: 'end', data: endReq });
                scheduleBatchProcessing();
                return result;
            }
        } catch (error) {
            console.error(`Op ${actualOpName} failed:`, error);
            const endTime = new Date().toISOString();
            const endReq = createEndReq(
                callId,
                endTime,
                null,
                {},
                error instanceof Error ? error.message : String(error)
            );
            callQueue.push({ mode: 'end', data: endReq });
            scheduleBatchProcessing();
            throw error;
        } finally {
            store.callStack.pop();
        }
    };
}

function ref(uri: string) {
    console.log(`Ref: ${uri}`);
}

function generateTraceId(): string {
    return uuidv7();
}

function generateCallId(): string {
    return uuidv7();
}

export { init, op, ref };

export function initWithCustomTraceServer(projectName: string, customTraceServer: InMemoryTraceServer) {
    globalProjectName = projectName;
    traceServerApi = customTraceServer as unknown as TraceServerApi<any>;
}
