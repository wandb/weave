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
    summarize?: (result: Awaited<ReturnType<T>>) => Record<string, any>;
    aggregateStream?: (stream: AsyncIterable<any>) => Promise<Awaited<ReturnType<T>>>;
}

// Add this new type and function
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

            let aggregatedResult: Awaited<ReturnType<T>> = result;
            let outputToLog = result;

            if (options?.aggregateStream && Symbol.asyncIterator in result) {
                aggregatedResult = await options.aggregateStream(result as unknown as AsyncIterable<any>);
                outputToLog = aggregatedResult;  // Use the aggregated result for logging
            }

            const endTime = new Date().toISOString();
            let ownSummary = options?.summarize ? options.summarize(aggregatedResult) : {};

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

            const currentCall = store.callStack[store.callStack.length - 1];
            const mergedSummary = mergeSummaries(ownSummary, currentCall.childSummary);

            if (store.callStack.length > 1) {
                const parentCall = store.callStack[store.callStack.length - 2];
                parentCall.childSummary = mergeSummaries(mergedSummary, parentCall.childSummary);
            }

            const endReq = {
                end: {
                    project_id: globalProjectName,
                    id: callId,
                    ended_at: endTime,
                    output: outputToLog,  // Use the aggregated result for streaming responses
                    summary: mergedSummary,
                }
            };

            callQueue.push({ mode: 'end', data: endReq });
            scheduleBatchProcessing();

            return result;  // Return the original result to maintain the same behavior for the user
        } catch (error) {
            console.error(`Op ${actualOpName} failed:`, error);  // Debug log
            const endTime = new Date().toISOString();
            const endReq = {
                end: {
                    project_id: globalProjectName,
                    id: callId,
                    ended_at: endTime,
                    exception: error instanceof Error ? error.message : String(error),
                    summary: {},
                }
            };

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
    console.log(`Initializing custom trace server for project: ${projectName}`);  // Debug log
    globalProjectName = projectName;
    traceServerApi = customTraceServer as unknown as TraceServerApi<any>;
}
