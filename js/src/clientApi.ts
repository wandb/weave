import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import * as crypto from 'crypto';
import { uuidv7 } from 'uuidv7';
import { AsyncLocalStorage } from 'async_hooks';

import { Api as TraceServerApi, StartedCallSchemaForInsert, EndedCallSchemaForInsert } from './traceServerApi';
import { WandbServerApi } from './wandbServerApi';
import { InMemoryTraceServer } from './inMemoryTraceServer';
import { WeaveObject, getClassChain } from './weaveObject';
import { Op, getOpName, getOpWrappedFunction, isOp, OpRef } from './opType';

export type CallStackEntry = {
    callId: string;
    traceId: string;
    childSummary: Record<string, any>;
};

function generateTraceId(): string {
    return uuidv7();
}

function generateCallId(): string {
    return uuidv7();
}

export class CallStack {
    private stack: CallStackEntry[] = [];

    constructor(stack: CallStackEntry[] = []) {
        this.stack = stack;
    }

    pushNewCall(): { currentCall: CallStackEntry, parentCall: CallStackEntry | undefined, newStack: CallStack } {
        const parentCall = this.stack[this.stack.length - 1];

        const callId = generateCallId();
        let traceId: string;
        let parentId: string | null = null;
        if (!parentCall) {
            traceId = generateTraceId();
        } else {
            traceId = parentCall.traceId;
            parentId = parentCall.callId;
        }

        const newCall: CallStackEntry = { callId, traceId, childSummary: {} };

        const newStack = new CallStack([...this.stack, newCall]);
        return {
            currentCall: newCall,
            parentCall,
            newStack
        }
    }

}

class ObjectRef {
    constructor(public projectId: string, public objectId: string, public digest: string) { }

    public uri() {
        return `weave:///${this.projectId}/object/${this.objectId}:${this.digest}`;
    }

    public ui_url() {
        return `https://wandb.ai/${this.projectId}/weave/objects/${this.objectId}/versions/${this.digest}`;
    }
}

type CallStartParams = StartedCallSchemaForInsert;
type CallEndParams = EndedCallSchemaForInsert;

export class WeaveClient {
    private stackContext = new AsyncLocalStorage<CallStack>();
    traceServerApi: TraceServerApi<any>;
    wandbServerApi: WandbServerApi;
    projectId: string;
    callQueue: Array<{ mode: 'start' | 'end', data: any }> = [];
    batchProcessTimeout: NodeJS.Timeout | null = null;
    isBatchProcessing: boolean = false;
    quiet: boolean = false;
    readonly BATCH_INTERVAL: number = 200;

    private fileQueue: Array<{ fileContent: Blob }> = [];
    private isProcessingFiles: boolean = false;

    constructor(traceServerApi: TraceServerApi<any>, wandbServerApi: WandbServerApi, projectId: string, quiet: boolean = false) {
        this.traceServerApi = traceServerApi;
        this.wandbServerApi = wandbServerApi;
        this.projectId = projectId;
        this.quiet = quiet;
    }

    private scheduleBatchProcessing() {
        if (this.batchProcessTimeout || this.isBatchProcessing) return;
        this.batchProcessTimeout = setTimeout(() => this.processBatch(), this.BATCH_INTERVAL);
    }

    private async processBatch() {
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

    private computeDigest(data: Buffer): string {
        // Must match python server algorithm in clickhouse_trace_server_batched.py
        const hasher = crypto.createHash('sha256');
        hasher.update(data);
        const hashBytes = hasher.digest();
        const base64EncodedHash = hashBytes.toString('base64url');
        return base64EncodedHash.replace(/-/g, 'X').replace(/_/g, 'Y').replace(/=/g, '');
    }

    async saveFileBlob(typeName: string, fileName: string, fileContent: Blob): Promise<any> {
        const buffer = await fileContent.arrayBuffer().then(Buffer.from);
        const digest = this.computeDigest(buffer);

        const placeholder = {
            _type: 'CustomWeaveType',
            weave_type: { type: typeName },
            files: {
                [fileName]: digest
            },
            load_op: 'NO_LOAD_OP'
        };

        this.fileQueue.push({ fileContent });
        this.processFileQueue();

        return placeholder;
    }

    async saveImage(imageData: Buffer, imageType: 'png'): Promise<any> {
        const blob = new Blob([imageData], { type: `image/${imageType}` });
        return this.saveFileBlob('PIL.Image.Image', 'image.png', blob);
    }


    async saveObject(obj: WeaveObject, objId?: string): Promise<any> {
        const classChain = getClassChain(obj);
        const className = classChain[0];
        if (!objId) {
            objId = obj.id() ?? className
        }

        let saveAttrs = obj.saveAttrs();
        saveAttrs = await this.saveObjectAndOps(saveAttrs);
        const saveValue = {
            _type: classChain[0],
            _bases: classChain.slice(1),
            ...saveAttrs
        }
        console.log("SAVE VALUE", JSON.stringify(saveValue, undefined, 2))
        const response = await this.traceServerApi.obj.objCreateObjCreatePost({
            obj: {
                project_id: this.projectId,
                object_id: objId,
                val: saveValue
            }
        });
        // TODO: work in batch, return immediately
        const ref = new ObjectRef(this.projectId, objId, response.data.digest);
        console.log(`Saved object: ${ref.ui_url()}`);
        return ref;
    }

    async saveOp(op: Op<(...args: any[]) => any>): Promise<any> {
        const objId = getOpName(op);
        const opFn = getOpWrappedFunction(op);
        const saveValue = await this.saveFileBlob('Op', 'obj.py', new Blob([opFn.toString()]))
        const response = await this.traceServerApi.obj.objCreateObjCreatePost({
            obj: {
                project_id: this.projectId,
                object_id: objId,
                val: saveValue
            }
        });
        // TODO: work in batch, return immediately
        return new OpRef(this.projectId, objId, response.data.digest);
    }

    async saveObjectAndOps(val: any): Promise<any> {
        if (Array.isArray(val)) {
            return Promise.all(val.map(item => this.saveObjectAndOps(item)));
        } else if (val instanceof WeaveObject) {
            return (await this.saveObject(val)).uri();
        } else if (isOp(val)) {
            return (await this.saveOp(val)).uri();
        } else if (typeof val === 'object' && val !== null) {
            const result: { [key: string]: any } = {};
            for (const [key, value] of Object.entries(val)) {
                result[key] = await this.saveObjectAndOps(value);
            }
            return result;
        } else {
            return val;
        }
    }

    public saveCallStart(callStart: CallStartParams) {
        this.callQueue.push({ mode: 'start', data: { start: callStart } });
        this.scheduleBatchProcessing();
    }

    public saveCallEnd(callEnd: CallEndParams) {
        this.callQueue.push({ mode: 'end', data: { end: callEnd } });
        this.scheduleBatchProcessing();
    }

    public createEndReq(callId: string, endTime: string, output: any, summary: Record<string, any>, exception?: string) {
        return {
            project_id: this.projectId,
            id: callId,
            ended_at: endTime,
            output,
            summary,
            ...(exception && { exception }),
        };
    }

    private async processFileQueue() {
        if (this.isProcessingFiles || this.fileQueue.length === 0) return;

        this.isProcessingFiles = true;

        while (this.fileQueue.length > 0) {
            const { fileContent } = this.fileQueue.shift()!;

            try {
                const fileCreateRes = await this.traceServerApi.file.fileCreateFileCreatePost({
                    project_id: this.projectId,
                    // @ts-ignore
                    file: fileContent
                });
            } catch (error) {
                console.error('Error saving file:', error);
            }
        }

        this.isProcessingFiles = false;
    }

    // Add these new methods
    private getCallStack(): CallStack {
        return this.stackContext.getStore() || new CallStack();
    }

    pushNewCall() {
        return this.getCallStack().pushNewCall();
    }

    runWithCallStack<T>(callStack: CallStack, fn: () => T): T {
        return this.stackContext.run(callStack, fn);
    }
}

// Global client instance
export let globalClient: WeaveClient | null = null;

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

export async function init(projectName: string): Promise<WeaveClient> {
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
        const projectId = `${defaultEntityName}/${projectName}`;

        const traceServerApi = new TraceServerApi({
            baseUrl: 'https://trace.wandb.ai',
            baseApiParams: {
                headers: headers,
            },
        });

        globalClient = new WeaveClient(traceServerApi, wandbServerApi, projectId);
        console.log(`Initializing project: ${projectId}`);
        return globalClient;
    } catch (error) {
        console.error("Error during initialization:", error);
        throw error;
    }
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
export async function processWeaveValues(value: any): Promise<any> {
    if (!globalClient) return value;

    if (isWeaveImage(value)) {
        return await globalClient.saveImage(value.data, value.imageType);
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

function ref(uri: string) {
    console.log(`Ref: ${uri}`);
}

export function initWithCustomTraceServer(projectName: string, customTraceServer: InMemoryTraceServer) {
    globalClient = new WeaveClient(
        customTraceServer as unknown as TraceServerApi<any>,
        {} as WandbServerApi, // Placeholder, as we don't use WandbServerApi in this case
        projectName,
        true
    );
}