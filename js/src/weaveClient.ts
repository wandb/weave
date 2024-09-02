import * as crypto from 'crypto';
import { uuidv7 } from 'uuidv7';
import { AsyncLocalStorage } from 'async_hooks';

import { packageVersion } from "./userAgent";
import { Api as TraceServerApi, StartedCallSchemaForInsert, EndedCallSchemaForInsert } from './traceServerApi';
import { WandbServerApi } from './wandbServerApi';
import { WeaveObject, ObjectRef, getClassChain } from './weaveObject';
import { Op, getOpName, getOpWrappedFunction, isOp, OpRef } from './opType';
import { isWeaveImage } from './media';

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

class CallStack {
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

type CallStartParams = StartedCallSchemaForInsert;
type CallEndParams = EndedCallSchemaForInsert;

export class WeaveClient {
    private stackContext = new AsyncLocalStorage<CallStack>();
    private traceServerApi: TraceServerApi<any>;
    private wandbServerApi: WandbServerApi;
    private projectId: string;
    private callQueue: Array<{ mode: 'start' | 'end', data: any }> = [];
    private batchProcessTimeout: NodeJS.Timeout | null = null;
    private isBatchProcessing: boolean = false;
    private quiet: boolean = false;
    private readonly BATCH_INTERVAL: number = 200;

    private fileQueue: Array<{ fileContent: Blob }> = [];
    private isProcessingFiles: boolean = false;

    constructor(traceServerApi: TraceServerApi<any>, wandbServerApi: WandbServerApi, projectId: string, quiet: boolean = false) {
        this.traceServerApi = traceServerApi;
        this.wandbServerApi = wandbServerApi;
        this.projectId = projectId;
        this.quiet = quiet;
        this.saveMedia = this.saveMedia.bind(this);
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


    private computeDigest(data: Buffer): string {
        // Must match python server algorithm in clickhouse_trace_server_batched.py
        const hasher = crypto.createHash('sha256');
        hasher.update(data);
        const hashBytes = hasher.digest();
        const base64EncodedHash = hashBytes.toString('base64url');
        return base64EncodedHash.replace(/-/g, 'X').replace(/_/g, 'Y').replace(/=/g, '');
    }

    private async saveFileBlob(typeName: string, fileName: string, fileContent: Blob): Promise<any> {
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

    private async saveImage(imageData: Buffer, imageType: 'png'): Promise<any> {
        const blob = new Blob([imageData], { type: `image/${imageType}` });
        return this.saveFileBlob('PIL.Image.Image', 'image.png', blob);
    }


    private async saveObject(obj: WeaveObject, objId?: string): Promise<any> {
        if (obj.__savedRef) {
            return obj.__savedRef;
        }

        obj.__savedRef = (async () => {
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
            const response = await this.traceServerApi.obj.objCreateObjCreatePost({
                obj: {
                    project_id: this.projectId,
                    object_id: objId,
                    val: saveValue
                }
            });
            const ref = new ObjectRef(this.projectId, objId, response.data.digest);
            console.log(`Saved object: ${ref.ui_url()}`);
            return ref;
        })();

        return obj.__savedRef;
    }

    private async saveObjectAndOps(val: any): Promise<any> {
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

    private saveMedia = async (value: any): Promise<any> => {
        if (isWeaveImage(value)) {
            return await this.saveImage(value.data, value.imageType);
        } else if (Array.isArray(value)) {
            return Promise.all(value.map(this.saveMedia));
        } else if (typeof value === 'object' && value !== null) {
            const processed: Record<string, any> = {};
            for (const [key, val] of Object.entries(value)) {
                processed[key] = await this.saveMedia(val);
            }
            return processed;
        }
        return value;
    }

    private saveCallStart(callStart: CallStartParams) {
        this.callQueue.push({ mode: 'start', data: { start: callStart } });
        this.scheduleBatchProcessing();
    }

    private saveCallEnd(callEnd: CallEndParams) {
        this.callQueue.push({ mode: 'end', data: { end: callEnd } });
        this.scheduleBatchProcessing();
    }

    private getCallStack(): CallStack {
        return this.stackContext.getStore() || new CallStack();
    }

    public pushNewCall() {
        return this.getCallStack().pushNewCall();
    }

    public runWithCallStack<T>(callStack: CallStack, fn: () => T): T {
        return this.stackContext.run(callStack, fn);
    }

    private async paramsToCallInputs(params: any[], thisArg: any) {
        // Process WeaveImage in inputs
        const processedArgs = await Promise.all(params.map(this.saveMedia));

        let inputs: Record<string, any> = {};

        // Add 'self' first if thisArg is a WeaveObject
        if (thisArg instanceof WeaveObject) {
            inputs['self'] = thisArg;
        }

        // Handle the special case for the first parameter
        if (processedArgs.length > 0 &&
            typeof processedArgs[0] === 'object' &&
            processedArgs[0] !== null &&
            !(processedArgs[0] instanceof WeaveObject)) {
            inputs = { ...inputs, ...processedArgs[0] };
            for (let i = 1; i < processedArgs.length; i++) {
                inputs[`arg${i - 1}`] = processedArgs[i];
            }
        } else {
            // If the first parameter is not an object or is a WeaveObject, use the original logic
            processedArgs.forEach((arg, index) => {
                inputs[`arg${index}`] = arg;
            });
        }

        const savedInputs = await this.saveObjectAndOps(inputs);
        return savedInputs;
    }

    public async saveOp(op: Op<(...args: any[]) => any>): Promise<any> {
        if (op.__savedRef) {
            return op.__savedRef;
        }
        op.__savedRef = (async () => {
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
            const ref = new OpRef(this.projectId, objId, response.data.digest);

            console.log('Saved op: ', ref.ui_url());
            return ref;
        })();
        return op.__savedRef;
    }


    public async startCall(opRef: OpRef | Op<any>, params: any[], thisArg: any, currentCall: CallStackEntry, parentCall: CallStackEntry | undefined, startTime: Date) {
        if (isOp(opRef)) {
            opRef = await this.saveOp(opRef);
        }
        if (!this.quiet && parentCall == null) {
            console.log(`🍩 https://wandb.ai/${this.projectId}/r/call/${currentCall.callId}`);
        }
        const inputs = await this.paramsToCallInputs(params, thisArg);
        const startReq = {
            project_id: this.projectId,
            id: currentCall.callId,
            op_name: opRef.uri(),
            trace_id: currentCall.traceId,
            parent_id: parentCall?.callId,
            started_at: startTime.toISOString(),
            attributes: {
                weave: {
                    client_version: packageVersion,
                    source: 'js-sdk'
                }
            },
            inputs
        }
        return this.saveCallStart(startReq);
    }

    public async finishCall(result: any, currentCall: CallStackEntry, parentCall: CallStackEntry | undefined, summarize: undefined | ((result: any) => Record<string, any>), endTime: Date, startCallPromise: Promise<void>) {
        // ensure end is logged after start is logged
        await startCallPromise;
        result = await this.saveMedia(result);
        const mergedSummary = processSummary(result, summarize, currentCall, parentCall);
        await this.saveCallEnd({
            project_id: this.projectId,
            id: currentCall.callId,
            ended_at: endTime.toISOString(),
            output: result,
            summary: mergedSummary
        });
    }

    public async finishCallWithException(error: any, currentCall: CallStackEntry, endTime: Date, startCallPromise: Promise<void>) {
        // ensure end is logged after start is logged
        await startCallPromise;
        await this.saveCallEnd({
            project_id: this.projectId,
            id: currentCall.callId,
            ended_at: endTime.toISOString(),
            output: null,
            summary: {},
            exception: error instanceof Error ? error.message : String(error)
        });
    }
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