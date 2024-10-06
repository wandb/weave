import {AsyncLocalStorage} from 'async_hooks';
import {uuidv7} from 'uuidv7';

import {computeDigest} from './digest';
import {isWeaveImage} from './media';
import {
  Op,
  OpRef,
  ParameterNamesOption,
  getOpName,
  getOpWrappedFunction,
  isOp,
} from './opType';
import {Table, TableRef, TableRowRef} from './table';
import {
  EndedCallSchemaForInsert,
  StartedCallSchemaForInsert,
  Api as TraceServerApi,
} from './traceServerApi';
import {packageVersion} from './userAgent';
import {WandbServerApi} from './wandbServerApi';
import {ObjectRef, WeaveObject, getClassChain} from './weaveObject';

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

  peek(): CallStackEntry | null {
    return this.stack[this.stack.length - 1] ?? null;
  }

  pushNewCall(): {
    currentCall: CallStackEntry;
    parentCall: CallStackEntry | undefined;
    newStack: CallStack;
  } {
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

    const newCall: CallStackEntry = {callId, traceId, childSummary: {}};

    const newStack = new CallStack([...this.stack, newCall]);
    return {
      currentCall: newCall,
      parentCall,
      newStack,
    };
  }
}

type CallStartParams = StartedCallSchemaForInsert;
type CallEndParams = EndedCallSchemaForInsert;

export class WeaveClient {
  private stackContext = new AsyncLocalStorage<CallStack>();
  public traceServerApi: TraceServerApi<any>;
  private wandbServerApi: WandbServerApi;
  private callQueue: Array<{mode: 'start' | 'end'; data: any}> = [];
  private batchProcessTimeout: NodeJS.Timeout | null = null;
  private isBatchProcessing: boolean = false;
  private readonly BATCH_INTERVAL: number = 200;

  public projectId: string;
  public quiet: boolean = false;

  constructor(
    traceServerApi: TraceServerApi<any>,
    wandbServerApi: WandbServerApi,
    projectId: string,
    quiet: boolean = false
  ) {
    this.traceServerApi = traceServerApi;
    this.wandbServerApi = wandbServerApi;
    this.projectId = projectId;
    this.quiet = quiet;
  }

  private scheduleBatchProcessing() {
    if (this.batchProcessTimeout || this.isBatchProcessing) return;
    this.batchProcessTimeout = setTimeout(
      () => this.processBatch(),
      this.BATCH_INTERVAL
    );
  }

  private async processBatch() {
    if (this.isBatchProcessing || this.callQueue.length === 0) {
      this.batchProcessTimeout = null;
      return;
    }

    this.isBatchProcessing = true;

    // We count characters item by item, and try to limit batches to about
    // this size.
    const maxBatchSizeChars = 5 * 1024 * 1024;

    let batchToProcess = [];
    let currentBatchSize = 0;

    while (this.callQueue.length > 0 && currentBatchSize < maxBatchSizeChars) {
      const item = this.callQueue[0];
      const itemSize = JSON.stringify(item).length;

      if (currentBatchSize + itemSize <= maxBatchSizeChars) {
        batchToProcess.push(this.callQueue.shift()!);
        currentBatchSize += itemSize;
      } else {
        break;
      }
    }

    const batchReq = {
      batch: batchToProcess.map(item => ({
        mode: item.mode,
        req: item.data,
      })),
    };

    try {
      await this.traceServerApi.call.callStartBatchCallUpsertBatchPost(
        batchReq
      );
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

  // save* methods attached __savedRef promises to their values. These must
  // be synchronous, so we can guarantee that calling savedWeaveValues
  // immediately makes __savedRef promises available.

  public saveObject(obj: WeaveObject, objId?: string): void {
    if (obj.__savedRef) {
      return;
    }
    for (const [key, value] of Object.entries(obj)) {
      this.saveWeaveValues(value);
    }

    obj.__savedRef = (async () => {
      const classChain = getClassChain(obj);
      const className = classChain[0];
      if (!objId) {
        objId = obj.id;
      }

      let saveAttrs = obj.saveAttrs();
      saveAttrs = await this.serializedVal(saveAttrs);
      // Frontend does this overly specific check for datasets, so we need to add both _type and _class_name
      // for now.
      //   data._type === 'Dataset' &&
      //   data._class_name === 'Dataset' &&
      //   _.isEqual(data._bases, ['Object', 'BaseModel'])
      const saveValue = {
        _type: className,
        _class_name: className,
        _bases: classChain.slice(1),
        ...saveAttrs,
      };
      const response = await this.traceServerApi.obj.objCreateObjCreatePost({
        obj: {
          project_id: this.projectId,
          object_id: objId,
          val: saveValue,
        },
      });
      const ref = new ObjectRef(this.projectId, objId, response.data.digest);
      // console.log(`Saved object: ${ref.ui_url()}`);
      return ref;
    })();
  }

  private saveTable(table: Table): void {
    if (table.__savedRef) {
      return;
    }

    table.__savedRef = (async () => {
      const rowsWithoutRefs = table.rows.map(row => {
        return {...row, __savedRef: undefined};
      });
      const rows = await this.serializedVal(rowsWithoutRefs);
      const response =
        await this.traceServerApi.table.tableCreateTableCreatePost({
          table: {
            project_id: this.projectId,
            rows,
          },
        });
      const ref = new TableRef(this.projectId, response.data.digest);
      return ref;
    })();
    const tableQueryPromise = (async () => {
      const tableRef = await table.__savedRef;
      const tableQueryRes =
        await this.traceServerApi.table.tableQueryTableQueryPost({
          project_id: this.projectId,
          digest: tableRef?.digest!,
        });
      return {
        tableDigest: tableRef?.digest!,
        tableQueryResult: tableQueryRes.data,
      };
    })();
    for (let i = 0; i < table.rows.length; i++) {
      const row = table.rows[i];
      row.__savedRef = (async () => {
        const {tableDigest, tableQueryResult} = await tableQueryPromise;
        return new TableRowRef(
          this.projectId,
          tableDigest,
          tableQueryResult.rows[i].digest
        );
      })();
    }
  }

  /**
   * Recursively save a Weave value, attaching __savedRef Promises to
   * nested value that gets its own ref.
   *
   * This function must be synchronous, so that code that does ref-tracking
   * (currently only Dataset/DatasetRow in the js client) has refs
   * available immediately.
   */
  private saveWeaveValues(val: any): void {
    if (Array.isArray(val)) {
      val.map(item => this.saveWeaveValues(item));
    } else if (val != null && val.__savedRef) {
      return;
    } else if (val instanceof WeaveObject) {
      this.saveObject(val);
    } else if (val instanceof Table) {
      this.saveTable(val);
    } else if (isWeaveImage(val)) {
    } else if (isOp(val)) {
      this.saveOp(val);
    } else if (typeof val === 'object' && val !== null) {
      for (const [key, value] of Object.entries(val)) {
        this.saveWeaveValues(value);
      }
    }
  }

  // serialize* methods are async, and return the serialized value
  // of a Weave value.

  private async serializedFileBlob(
    typeName: string,
    fileName: string,
    fileContent: Blob
  ): Promise<any> {
    const buffer = await fileContent.arrayBuffer().then(Buffer.from);
    const digest = computeDigest(buffer);

    const placeholder = {
      _type: 'CustomWeaveType',
      weave_type: {type: typeName},
      files: {
        [fileName]: digest,
      },
      load_op: 'NO_LOAD_OP',
    };

    try {
      await this.traceServerApi.file.fileCreateFileCreatePost({
        project_id: this.projectId,
        // @ts-ignore
        file: fileContent,
      });
    } catch (error) {
      console.error('Error saving file:', error);
    }

    return placeholder;
  }

  private async serializedImage(
    imageData: Buffer,
    imageType: 'png'
  ): Promise<any> {
    const blob = new Blob([imageData], {type: `image/${imageType}`});
    return this.serializedFileBlob('PIL.Image.Image', 'image.png', blob);
  }

  /**
   * Get the serialized value of a Weave value, by recursively
   * resolving any __savedRef promises to their uri().
   *
   * This function is asynchronous, and must be called after saveWeaveValues
   * has been called on the value.
   */
  private async serializedVal(val: any): Promise<any> {
    if (Array.isArray(val)) {
      return Promise.all(val.map(async item => this.serializedVal(item)));
    } else if (val != null && val.__savedRef) {
      return (await val.__savedRef).uri();
    } else if (isWeaveImage(val)) {
      return await this.serializedImage(val.data, val.imageType);
    } else if (val instanceof WeaveObject) {
      throw new Error('Programming error:  WeaveObject not saved');
    } else if (val instanceof Table) {
      throw new Error('Programming error: Table not saved');
    } else if (isOp(val)) {
      throw new Error('Programming error: Op not saved');
    } else if (typeof val === 'object' && val !== null) {
      const result: {[key: string]: any} = {};
      for (const [key, value] of Object.entries(val)) {
        result[key] = await this.serializedVal(value);
      }
      return result;
    } else {
      return val;
    }
  }

  private saveCallStart(callStart: CallStartParams) {
    this.callQueue.push({mode: 'start', data: {start: callStart}});
    this.scheduleBatchProcessing();
  }

  private saveCallEnd(callEnd: CallEndParams) {
    this.callQueue.push({mode: 'end', data: {end: callEnd}});
    this.scheduleBatchProcessing();
  }

  public getCallStack(): CallStack {
    return this.stackContext.getStore() || new CallStack();
  }

  public pushNewCall() {
    return this.getCallStack().pushNewCall();
  }

  public runWithCallStack<T>(callStack: CallStack, fn: () => T): T {
    return this.stackContext.run(callStack, fn);
  }

  private async paramsToCallInputs(
    params: any[],
    thisArg: any,
    parameterNames: ParameterNamesOption
  ) {
    let inputs: Record<string, any> = {};

    // Add 'self' first if thisArg is a WeaveObject
    if (thisArg instanceof WeaveObject) {
      inputs['self'] = thisArg;
    }
    if (parameterNames === 'useParam0Object') {
      inputs = {...inputs, ...params[0]};
    } else if (parameterNames) {
      params.forEach((arg, index) => {
        inputs[parameterNames[index]] = arg;
      });
    } else {
      params.forEach((arg, index) => {
        inputs[`arg${index}`] = arg;
      });
    }
    this.saveWeaveValues(inputs);
    return await this.serializedVal(inputs);
  }

  public async saveOp(op: Op<(...args: any[]) => any>): Promise<any> {
    if (op.__savedRef) {
      return op.__savedRef;
    }
    op.__savedRef = (async () => {
      const objId = getOpName(op);
      const opFn = getOpWrappedFunction(op);
      const saveValue = await this.serializedFileBlob(
        'Op',
        'obj.py',
        new Blob([opFn.toString()])
      );
      const response = await this.traceServerApi.obj.objCreateObjCreatePost({
        obj: {
          project_id: this.projectId,
          object_id: objId,
          val: saveValue,
        },
      });
      const ref = new OpRef(this.projectId, objId, response.data.digest);

      // console.log('Saved op: ', ref.ui_url());
      return ref;
    })();
    return op.__savedRef;
  }

  public async startCall(
    opRef: OpRef | Op<any>,
    params: any[],
    parameterNames: ParameterNamesOption,
    thisArg: any,
    currentCall: CallStackEntry,
    parentCall: CallStackEntry | undefined,
    startTime: Date,
    displayName?: string
  ) {
    const inputs = await this.paramsToCallInputs(
      params,
      thisArg,
      parameterNames
    );
    if (isOp(opRef)) {
      this.saveOp(opRef);
      opRef = await opRef.__savedRef;
    }
    const startReq = {
      project_id: this.projectId,
      id: currentCall.callId,
      op_name: opRef.uri(),
      trace_id: currentCall.traceId,
      parent_id: parentCall?.callId,
      started_at: startTime.toISOString(),
      display_name: displayName,
      attributes: {
        weave: {
          client_version: packageVersion,
          source: 'js-sdk',
        },
      },
      inputs,
    };
    return this.saveCallStart(startReq);
  }

  public async finishCall(
    result: any,
    currentCall: CallStackEntry,
    parentCall: CallStackEntry | undefined,
    summarize: undefined | ((result: any) => Record<string, any>),
    endTime: Date,
    startCallPromise: Promise<void>
  ) {
    // Important to do this first before any awaiting, so we're guaranteed that children
    // summaries are processed before parents!
    const mergedSummary = processSummary(
      result,
      summarize,
      currentCall,
      parentCall
    );
    // ensure end is logged after start is logged
    await startCallPromise;
    this.saveWeaveValues(result);
    result = await this.serializedVal(result);
    await this.saveCallEnd({
      project_id: this.projectId,
      id: currentCall.callId,
      ended_at: endTime.toISOString(),
      output: result,
      summary: mergedSummary,
    });
  }

  public async finishCallWithException(
    error: any,
    currentCall: CallStackEntry,
    parentCall: CallStackEntry | undefined,
    endTime: Date,
    startCallPromise: Promise<void>
  ) {
    const mergedSummary = processSummary(
      null,
      undefined,
      currentCall,
      parentCall
    );
    // ensure end is logged after start is logged
    await startCallPromise;
    await this.saveCallEnd({
      project_id: this.projectId,
      id: currentCall.callId,
      ended_at: endTime.toISOString(),
      output: null,
      summary: mergedSummary,
      exception: error instanceof Error ? error.message : String(error),
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
  const result: Summary = {...right};
  for (const [key, leftValue] of Object.entries(left)) {
    if (key in result) {
      if (typeof leftValue === 'number' && typeof result[key] === 'number') {
        result[key] = leftValue + result[key];
      } else if (
        typeof leftValue === 'object' &&
        typeof result[key] === 'object'
      ) {
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
  let ownSummary = summarize && result != null ? summarize(result) : {};

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
    parentCall.childSummary = mergeSummaries(
      mergedSummary,
      parentCall.childSummary
    );
  }

  return mergedSummary;
}
