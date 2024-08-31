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

class WeaveClient {
    traceServerApi: TraceServerApi<any>;
    wandbServerApi: WandbServerApi;
    projectName: string;
    callQueue: Array<{ mode: 'start' | 'end', data: any }> = [];
    batchProcessTimeout: NodeJS.Timeout | null = null;
    isBatchProcessing: boolean = false;
    readonly BATCH_INTERVAL: number = 200;

    constructor(traceServerApi: TraceServerApi<any>, wandbServerApi: WandbServerApi, projectName: string) {
        this.traceServerApi = traceServerApi;
        this.wandbServerApi = wandbServerApi;
        this.projectName = projectName;
    }

    scheduleBatchProcessing() {
        if (this.batchProcessTimeout || this.isBatchProcessing) return;
        this.batchProcessTimeout = setTimeout(() => this.processBatch(), this.BATCH_INTERVAL);
    }

    async processBatch() {
        if (this.isBatchProcessing || this.callQueue.length === 0) {
            this.batchProcessTimeout = null;
            return;
        }

        this.isBatchProcessing = true;

        const batchToProcess = [...this.callQueue];
        this.callQueue = [];

        const batchReq = {
            batch: batchToProcess.map(item => ({
                mode: item.mode,
                req: item.data
            }))
        };

        try {
            await this.traceServerApi.call.callStartBatchCallUpsertBatchPost(batchReq);
        } catch (error) {
            console.error('Error processing batch:', error);
        } finally {
            this.isBatchProcessing = false;
            this.batchProcessTimeout = null;
            if (this.callQueue.length > 0) {
                this.scheduleBatchProcessing();
            }
        }
    }
}

// Global client instance
let globalClient: WeaveClient | null = null;

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

async function init(projectName: string): Promise<WeaveClient> {
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
        const wandbServerApi = new WandbServerApi(host, apiKey);
        const defaultEntityName = await wandbServerApi.defaultEntityName();
        const fullProjectName = `${defaultEntityName}/${projectName}`;

        const traceServerApi = new TraceServerApi({
            baseUrl: 'https://trace.wandb.ai',
            baseApiParams: {
                headers: headers,
            },
        });

        globalClient = new WeaveClient(traceServerApi, wandbServerApi, fullProjectName);
        console.log(`Initializing project: ${fullProjectName}`);
        return globalClient;
    } catch (error) {
        console.error("Error during initialization:", error);
        throw error;
    }
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

function createEndReq(client: WeaveClient, callId: string, endTime: string, output: any, summary: Summary, exception?: string) {
    return {
        end: {
            project_id: client.projectName,
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

interface OpOptions<T extends (...args: any[]) => any> {
    name?: string;
    streamReducer?: StreamReducer<any, any>;
    summarize?: (result: Awaited<ReturnType<T>>) => Record<string, any>;
}

// Define WeaveImage type
interface WeaveImage {
    _type: 'WeaveImage';
    data: Buffer;
    imageType: 'png';
}

export function weaveImage({ data, imageType }: { data: Buffer, imageType: 'png' }): WeaveImage {
    return {
        _type: 'WeaveImage',
        data,
        imageType
    };
}

// Function to check if a value is a WeaveImage
function isWeaveImage(value: any): value is WeaveImage {
    return value && value._type === 'WeaveImage' && Buffer.isBuffer(value.data) && value.imageType === 'png';
}

// Function to process WeaveImage in inputs or output
async function processWeaveValues(value: any): Promise<any> {
    if (isWeaveImage(value)) {
        return await saveImage(value.data, value.imageType);
    } else if (Array.isArray(value)) {
        return Promise.all(value.map(processWeaveValues));
    } else if (typeof value === 'object' && value !== null) {
        const processed: Record<string, any> = {};
        for (const [key, val] of Object.entries(value)) {
            processed[key] = await processWeaveValues(val);
        }
        return processed;
    }
    return value;
}

// Modify the op function
function op<T extends (...args: any[]) => any>(
    fn: T,
    options?: OpOptions<T>
): (...args: Parameters<T>) => Promise<ReturnType<T>> {
    const actualOpName = options?.name || fn.name || 'anonymous';

    return async function (...args: Parameters<T>): Promise<ReturnType<T>> {
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
            console.log(`🍩 https://wandb.ai/${globalClient.projectName}/r/call/${callId}`);
        }

        // Process WeaveImage in inputs
        const processedArgs = await Promise.all(args.map(processWeaveValues));

        const startReq = {
            start: {
                project_id: globalClient.projectName,
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
                inputs: processedArgs.reduce((acc, arg, index) => ({ ...acc, [`arg${index}`]: arg }), {}),
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
                            if (globalClient) {  // Check if globalClient still exists
                                state = await processWeaveValues(state);
                                const endTime = new Date().toISOString();
                                const mergedSummary = processSummary(state, options?.summarize, currentCall, parentCall);
                                const endReq = createEndReq(globalClient, callId, endTime, state, mergedSummary);
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
                const endReq = createEndReq(globalClient, callId, endTime, result, mergedSummary);
                globalClient.callQueue.push({ mode: 'end', data: endReq });
                globalClient.scheduleBatchProcessing();
                return result;
            }
        } catch (error) {
            console.error(`Op ${actualOpName} failed:`, error);
            const endTime = new Date().toISOString();
            const endReq = createEndReq(
                globalClient,
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

export { init, op, ref, WeaveClient as Client };

export function initWithCustomTraceServer(projectName: string, customTraceServer: InMemoryTraceServer) {
    globalClient = new WeaveClient(
        customTraceServer as unknown as TraceServerApi<any>,
        {} as WandbServerApi, // Placeholder, as we don't use WandbServerApi in this case
        projectName
    );
}
/**
 * Saves a file blob to the trace server and returns a CustomWeaveType object.
 * 
 * The frontend will interpret the CustomWeaveType and display the file.
 * 
 * @param typeName - The type name, must match python serializer.
 * @param fileName - The saved file name, must match python serializer.
 * @param fileContent - The content of the file as a Blob.
 * @returns A Promise that resolves to a CustomWeaveType object representing the saved file.
 */
async function saveFileBlob(typeName: string, fileName: string, fileContent: Blob) {
    const client = globalClient!;

    const fileCreateRes = await client.traceServerApi.file.fileCreateFileCreatePost({
        project_id: client.projectName,
        // @ts-ignore
        file: fileContent
    });

    return {
        _type: 'CustomWeaveType',
        weave_type: { type: typeName },
        files: {
            [fileName]: fileCreateRes.data.digest
        },
        // TODO: Have to hack this because the frontend requires it at the moment.
        load_op: 'NO_LOAD_OP'
    }
}

export async function saveImage(imageData: Buffer, imageType: 'png') {
    const blob = new Blob([imageData], { type: `image/${imageType}` });

    return saveFileBlob('PIL.Image.Image', 'image.png', blob)
}