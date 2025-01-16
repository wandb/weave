import {AsyncLocalStorage} from 'async_hooks';
import * as fs from 'fs';
import {uuidv7} from 'uuidv7';

import {MAX_OBJECT_NAME_LENGTH} from './constants';
import {Dataset} from './dataset';
import {computeDigest} from './digest';
import {
  CallSchema,
  CallsFilter,
  EndedCallSchemaForInsert,
  StartedCallSchemaForInsert,
  Api as TraceServerApi,
} from './generated/traceServerApi';
import {
  AudioType,
  DEFAULT_AUDIO_TYPE,
  DEFAULT_IMAGE_TYPE,
  ImageType,
  isWeaveAudio,
  isWeaveImage,
} from './media';
import {
  Op,
  OpRef,
  ParameterNamesOption,
  getOpName,
  getOpWrappedFunction,
  isOp,
} from './opType';
import {Settings} from './settings';
import {Table, TableRef, TableRowRef} from './table';
import {packageVersion} from './utils/userAgent';
import {WandbServerApi} from './wandb/wandbServerApi';
import {ObjectRef, WeaveObject, getClassChain} from './weaveObject';

const WEAVE_ERRORS_LOG_FNAME = 'weaveErrors.log';

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
  constructor(private stack: CallStackEntry[] = []) {}

  peek(): CallStackEntry | null {
    return this.stack[this.stack.length - 1] ?? null;
  }

  pushNewCall(): {
    currentCall: CallStackEntry;
    parentCall?: CallStackEntry;
    newStack: CallStack;
  } {
    const parentCall = this.stack[this.stack.length - 1];

    const callId = generateCallId();
    const traceId = parentCall?.traceId ?? generateTraceId();
    const newCall: CallStackEntry = {callId, traceId, childSummary: {}};
    const newStack = new CallStack([...this.stack, newCall]);
    return {currentCall: newCall, parentCall, newStack};
  }
}

type CallStartParams = StartedCallSchemaForInsert;
type CallEndParams = EndedCallSchemaForInsert;

// We count characters item by item, and try to limit batches to about this size.
const MAX_BATCH_SIZE_CHARS = 10 * 1024 * 1024;

export class WeaveClient {
  private stackContext = new AsyncLocalStorage<CallStack>();
  private callQueue: Array<{mode: 'start' | 'end'; data: any}> = [];
  private batchProcessTimeout: NodeJS.Timeout | null = null;
  private isBatchProcessing: boolean = false;
  private batchProcessingPromises: Set<Promise<void>> = new Set();
  private readonly BATCH_INTERVAL: number = 200;
  private errorCount = 0;
  private readonly MAX_ERRORS = 10;

  constructor(
    public traceServerApi: TraceServerApi<any>,
    private wandbServerApi: WandbServerApi,
    public projectId: string,
    public settings: Settings = new Settings()
  ) {}

  private scheduleBatchProcessing() {
    if (this.batchProcessTimeout || this.isBatchProcessing) return;
    const promise = new Promise<void>(resolve => {
      this.batchProcessTimeout = setTimeout(
        () => this.processBatch().then(resolve),
        this.BATCH_INTERVAL
      );
    });
    this.batchProcessingPromises.add(promise);
    promise.finally(() => {
      this.batchProcessingPromises.delete(promise);
    });
  }

  public async waitForBatchProcessing() {
    while (this.batchProcessingPromises.size > 0) {
      await Promise.all(this.batchProcessingPromises);
    }
  }

  private async processBatch() {
    if (this.isBatchProcessing || this.callQueue.length === 0) {
      this.batchProcessTimeout = null;
      return;
    }

    this.isBatchProcessing = true;

    let batchToProcess = [];
    let currentBatchSize = 0;

    while (
      this.callQueue.length > 0 &&
      currentBatchSize < MAX_BATCH_SIZE_CHARS
    ) {
      const item = this.callQueue.shift();
      if (item === undefined) {
        throw new Error('Call queue is empty');
      }

      const itemSize = JSON.stringify(item).length;
      if (itemSize > MAX_BATCH_SIZE_CHARS) {
        fs.appendFileSync(
          WEAVE_ERRORS_LOG_FNAME,
          `Item size ${itemSize} exceeds max batch size ${MAX_BATCH_SIZE_CHARS}.  Item: ${JSON.stringify(item)}\n`
        );
      }

      if (currentBatchSize + itemSize <= MAX_BATCH_SIZE_CHARS) {
        batchToProcess.push(item);
        currentBatchSize += itemSize;
      } else {
        // doesn't fit, put it back
        this.callQueue.unshift(item);
        break;
      }
    }

    if (batchToProcess.length === 0) {
      this.batchProcessTimeout = null;
      return;
    }

    this.isBatchProcessing = true;

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
      this.errorCount++;
      fs.appendFileSync(
        WEAVE_ERRORS_LOG_FNAME,
        `Error processing batch: ${error}\n`
      );

      // Put failed items back at the front of the queue
      this.callQueue.unshift(...batchToProcess);

      // Exit if we have too many errors
      if (this.errorCount > this.MAX_ERRORS) {
        console.error(`Exceeded max errors: ${this.MAX_ERRORS}; exiting`);
        process.exit(1);
      }
    } finally {
      this.isBatchProcessing = false;
      this.batchProcessTimeout = null;
      if (this.callQueue.length > 0) {
        this.scheduleBatchProcessing();
      }
    }
  }

  public publish(obj: any, objId?: string): Promise<ObjectRef> {
    if (obj.__savedRef) {
      return obj.__savedRef;
    } else if (obj instanceof WeaveObject) {
      return this.saveObject(obj, objId);
    } else if (isOp(obj)) {
      return this.saveOp(obj);
    } else {
      return this.saveArbitrary(obj, objId);
    }
  }

  public async getCall(
    callId: string,
    includeCosts: boolean = false
  ): Promise<CallSchema> {
    const calls = await this.getCalls({call_ids: [callId]}, includeCosts);
    if (calls.length === 0) {
      throw new Error(`Call not found: ${callId}`);
    }
    return calls[0];
  }
  public async getCalls(
    filter: CallsFilter = {},
    includeCosts: boolean = false,
    limit: number = 1000
  ) {
    const calls: CallSchema[] = [];
    const iterator = this.getCallsIterator(filter, includeCosts, limit);
    for await (const call of iterator) {
      calls.push(call);
    }
    return calls;
  }
  public async *getCallsIterator(
    filter: CallsFilter = {},
    includeCosts: boolean = false,
    limit: number = 1000
  ): AsyncIterableIterator<CallSchema> {
    const resp =
      await this.traceServerApi.calls.callsQueryStreamCallsStreamQueryPost({
        project_id: this.projectId,
        filter,
        include_costs: includeCosts,
        limit,
      });

    const reader = resp.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const {value, done} = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, {stream: true});
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.trim()) {
          try {
            yield JSON.parse(line);
          } catch (error) {
            console.error('Error parsing JSON:', error, 'Line:', line);
          }
        }
      }
    }

    if (buffer.trim()) {
      try {
        yield JSON.parse(buffer);
      } catch (error) {
        console.error('Error parsing JSON:', error, 'Remaining data:', buffer);
      }
    }
  }

  public async get(ref: ObjectRef): Promise<any> {
    let val: any;
    try {
      const res = await this.traceServerApi.obj.objReadObjReadPost({
        project_id: ref.projectId,
        object_id: ref.objectId,
        digest: ref.digest,
      });
      val = res.data.obj.val;
    } catch (error) {
      if (error instanceof Error && error.message.includes('404')) {
        throw new Error(`Unable to find object for ref uri: ${ref.uri()}`);
      }
      throw error;
    }

    const t = val?._type;
    if (t == 'Dataset') {
      const {_baseParameters, rows} = val;
      let obj = new Dataset({
        id: _baseParameters.id,
        description: _baseParameters.description,
        rows,
      });
      obj.__savedRef = ref;
      // TODO: The table row refs are not correct
      return obj;
    } else if (t == 'Table') {
      const {rows} = val;
      let obj = new Table(rows);
      obj.__savedRef = ref;
      return obj;
    } else if (t == 'CustomWeaveType') {
      const typeName = val.weave_type.type;
      if (typeName == 'PIL.Image.Image') {
        let loadedFiles: {[key: string]: Buffer} = {};
        for (const [name, digest] of Object.entries(val.files)) {
          try {
            const fileContent =
              await this.traceServerApi.file.fileContentFileContentPost({
                project_id: this.projectId,
                digest: digest as string,
              });
            loadedFiles[name] = fileContent.data?.content;
          } catch (error) {
            console.error('Error loading file:', error);
          }
        }
        // TODO: Implement getting img back as buffer
        return 'Coming soon!';
      } else if (typeName == 'wave.Wave_read') {
        let loadedFiles: {[key: string]: Buffer} = {};
        for (const [name, digest] of Object.entries(val.files)) {
          try {
            const fileContent =
              await this.traceServerApi.file.fileContentFileContentPost({
                project_id: this.projectId,
                digest: digest as string,
              });
            loadedFiles[name] = fileContent.data?.content;
          } catch (error) {
            console.error('Error loading file:', error);
          }
        }
        // TODO: Implement getting audio back as buffer
        return 'Coming soon!';
      }
    }
    return val;
  }

  // save* methods attached __savedRef promises to their values. These must
  // be synchronous, so we can guarantee that calling savedWeaveValues
  // immediately makes __savedRef promises available.

  private saveArbitrary(obj: any, objId?: string): Promise<ObjectRef> {
    if (obj.__savedRef) {
      return obj.__savedRef;
    }

    const ref = (async () => {
      if (!objId) {
        objId = uuidv7();
      }

      const serializedObj = await this.serializedVal(obj);
      const response = await this.traceServerApi.obj.objCreateObjCreatePost({
        obj: {
          project_id: this.projectId,
          object_id: objId,
          val: serializedObj,
        },
      });
      return new ObjectRef(this.projectId, objId, response.data.digest);
    })();

    obj.__savedRef = ref;
    return ref;
  }

  private saveObject(obj: WeaveObject, objId?: string): Promise<ObjectRef> {
    if (obj.__savedRef) {
      return Promise.resolve(obj.__savedRef);
    }
    for (const [key, value] of Object.entries(obj)) {
      this.saveWeaveValues(value);
    }

    obj.__savedRef = (async () => {
      const classChain = getClassChain(obj);
      const className = classChain[0];
      if (!objId) {
        objId = sanitizeObjectName(obj.id);
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
      return ref;
    })();

    return obj.__savedRef;
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
    } else if (isWeaveAudio(val)) {
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
    imageType: ImageType = DEFAULT_IMAGE_TYPE
  ): Promise<any> {
    const blob = new Blob([imageData], {type: `image/${imageType}`});
    return this.serializedFileBlob('PIL.Image.Image', 'image.png', blob);
  }

  private async serializedAudio(
    audioData: Buffer,
    audioType: AudioType = DEFAULT_AUDIO_TYPE
  ): Promise<any> {
    const blob = new Blob([audioData], {type: `audio/${audioType}`});
    return this.serializedFileBlob('wave.Wave_read', 'audio.wav', blob);
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
    } else if (isWeaveAudio(val)) {
      return await this.serializedAudio(val.data, val.audioType);
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

  public async saveOp(
    op: Op<(...args: any[]) => any>,
    objId?: string
  ): Promise<any> {
    if (op.__savedRef) {
      return op.__savedRef;
    }
    op.__savedRef = (async () => {
      const resolvedObjId = objId || getOpName(op);
      const opFn = getOpWrappedFunction(op);
      const formattedOpFn = await maybeFormatCode(opFn.toString());
      const saveValue = await this.serializedFileBlob(
        'Op',
        'obj.py',
        new Blob([formattedOpFn])
      );
      const response = await this.traceServerApi.obj.objCreateObjCreatePost({
        obj: {
          project_id: this.projectId,
          object_id: resolvedObjId,
          val: saveValue,
        },
      });
      const ref = new OpRef(
        this.projectId,
        resolvedObjId,
        response.data.digest
      );

      // console.log('Saved op: ', ref.ui_url());
      return ref;
    })();
    return op.__savedRef;
  }

  public async createCall(
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
        leftValue != null &&
        typeof leftValue === 'object' &&
        result[key] != null &&
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

async function maybeFormatCode(code: string) {
  return code;
  //   try {
  //     const prettier = await import('prettier');
  //     return prettier.format(code, { parser: 'babel' });
  //   } catch (error) {
  //     // prettier not available or formatting failed, just use the original string
  //     return code;
  //   }
}

function sanitizeObjectName(name: string): string {
  // Replaces any non-alphanumeric characters with a single dash and removes
  // any leading or trailing dashes. This is more restrictive than the DB
  // constraints and can be relaxed if needed.
  let res = name.replace(/[^\w._]+/g, '-'); // non-words
  res = res.replace(/([._-]{2,})+/g, '-'); // multiple separators
  res = res.replace(/^[-_]+|[-_]+$/g, ''); // leading/trailing separators

  if (!res) {
    throw new Error(`Invalid object name: ${name}`);
  }

  // Truncate if too long
  if (res.length > MAX_OBJECT_NAME_LENGTH) {
    res = res.slice(0, MAX_OBJECT_NAME_LENGTH);
  }

  return res;
}
