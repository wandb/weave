import {uuidv7} from 'uuidv7';

import {stainlessPromise} from './stainlessPromise';

export interface Call {
  project_id: string;
  id: string;
  op_name: string;
  trace_id: string;
  parent_id: string | null;
  started_at: string;
  ended_at?: string;
  inputs: any;
  output?: any;
  exception?: string;
  [key: string]: any;
}

interface QueryParams {
  project_id: string;
  limit?: number;
  order_by?: keyof Call;
  order_dir?: 'asc' | 'desc';
  filters?: Partial<Call>;
  filter?: {call_ids?: string[]};
}

interface Obj {
  project_id: string;
  object_id: string;
  created_at: string;
  deleted_at: string | null;
  digest: string;
  version_index: number;
  is_latest: number;
  kind: string;
  base_object_class: string | null;
  val: any;
}

interface File {
  project_id: string;
  digest: string;
  content: Blob;
}

interface Table {
  project_id: string;
  digest: string;
  rows: Array<{digest: string; val: any}>;
}

function ok<T>(data: T, response?: Response) {
  return stainlessPromise(data, response);
}

export class InMemoryTraceServer {
  private _calls: Call[] = [];
  private _objs: Obj[] = [];
  private _files: File[] = [];
  private _tables: Table[] = [];
  private _lastCallCount: number = 0;
  private _lastChangeTime: number = Date.now();

  calls = {
    upsertBatch: (batchReq: {
      batch: Array<{mode: 'start' | 'end'; req: any}>;
    }) => {
      for (const item of batchReq.batch) {
        if (item.mode === 'start') {
          this._calls.push(item.req.start);
          this._updateChangeTime();
        } else if (item.mode === 'end') {
          const call = this._calls.find(c => c.id === item.req.end.id);
          if (call) {
            Object.assign(call, item.req.end);
            this._updateChangeTime();
          }
        }
      }
      return ok({});
    },

    streamQuery: (queryParams: QueryParams) => {
      const filteredCalls = this._filterCalls(queryParams);
      const body =
        filteredCalls.map(call => JSON.stringify(call)).join('\n') +
        (filteredCalls.length ? '\n' : '');
      return stainlessPromise(undefined, new Response(body));
    },
  };

  objects = {
    create: (req: {obj: {project_id: string; object_id: string; val: any}}) => {
      const now = new Date().toISOString();
      const digest = this.generateDigest(req.obj.val);

      const newObj: Obj = {
        project_id: req.obj.project_id,
        object_id: req.obj.object_id,
        created_at: now,
        deleted_at: null,
        digest: digest,
        version_index: 0,
        is_latest: 1,
        kind: req.obj.val._type || 'unknown',
        base_object_class: req.obj.val._bases ? req.obj.val._bases[0] : null,
        val: req.obj.val,
      };

      const existingObjs = this._objs.filter(
        obj =>
          obj.project_id === req.obj.project_id &&
          obj.object_id === req.obj.object_id
      );
      if (existingObjs.length > 0) {
        newObj.version_index = existingObjs.length;
        existingObjs.forEach(obj => (obj.is_latest = 0));
      }

      this._objs.push(newObj);
      return ok({digest});
    },

    read: (req: {project_id: string; object_id: string; digest?: string}) => {
      const obj = this._objs.find(
        o =>
          o.project_id === req.project_id &&
          o.object_id === req.object_id &&
          (req.digest ? o.digest === req.digest : o.is_latest === 1)
      );

      if (!obj) {
        throw new Error(
          `Object not found: ${req.project_id}/${req.object_id}${req.digest ? ':' + req.digest : ''}`
        );
      }

      return ok({obj});
    },
  };

  tables = {
    create: (req: {table: {project_id: string; rows: any[]}}) => {
      const digest = this.generateDigest(req.table.rows);
      const rows = req.table.rows.map(rowVal => ({
        digest: this.generateDigest(rowVal),
        val: rowVal,
      }));
      this._tables.push({
        project_id: req.table.project_id,
        digest,
        rows,
      });
      return ok({digest});
    },

    query: (req: {project_id: string; digest: string}) => {
      const table = this._tables.find(
        t => t.project_id === req.project_id && t.digest === req.digest
      );
      if (!table) {
        throw new Error(
          `Table not found: ${req.project_id}/table/${req.digest}`
        );
      }
      return ok({rows: table.rows});
    },
  };

  files = {
    create: (data: {project_id: string; file: Blob}) => {
      return ok(
        (async () => {
          const digest = this.generateDigest(await data.file.arrayBuffer());
          this._files.push({
            project_id: data.project_id,
            digest,
            content: data.file,
          });
          return {digest};
        })()
      );
    },
  };

  feedback = {
    create: (_req: any) => ok({id: uuidv7()}),
  };

  v2Calls = {
    complete: (_project: string, params: {entity: string; batch: Call[]}) => {
      this._applyCompletes(params.batch);
      return ok({});
    },
  };

  post = (
    path: string,
    opts?: {
      body?: {
        batch?: Call[];
        start?: Call;
        end?: (Partial<Call> & {id: string}) | undefined;
      };
    }
  ) => {
    const body = opts?.body;
    if (path.endsWith('/calls/complete')) {
      this._applyCompletes(body?.batch ?? []);
      return ok({});
    }
    if (path.endsWith('/call/start')) {
      const start = body?.start;
      if (start) {
        this._calls.push(start);
        this._updateChangeTime();
      }
      return ok({id: start?.id, trace_id: start?.trace_id});
    }
    if (path.endsWith('/call/end')) {
      const end = body?.end;
      const call = end && this._calls.find(c => c.id === end.id);
      if (call && end) {
        Object.assign(call, end);
        this._updateChangeTime();
      }
      return ok({});
    }
    throw new Error(`InMemoryTraceServer: unhandled post to ${path}`);
  };

  put = (path: string, _opts?: {body?: unknown}) => {
    throw new Error(`InMemoryTraceServer: unhandled put to ${path}`);
  };

  private _applyCompletes(batch: Call[]) {
    for (const complete of batch) {
      const existing = this._calls.find(c => c.id === complete.id);
      if (existing) {
        Object.assign(existing, complete);
      } else {
        this._calls.push(complete);
      }
      this._updateChangeTime();
    }
  }

  private _filterCalls(queryParams: QueryParams): Call[] {
    let filteredCalls = this._calls.filter(
      call => call.project_id === queryParams.project_id
    );

    if (queryParams.filters) {
      filteredCalls = filteredCalls.filter(call => {
        return Object.entries(queryParams.filters || {}).every(
          ([key, value]) => call[key] === value
        );
      });
    }

    if (queryParams.filter?.call_ids) {
      const ids = new Set(queryParams.filter.call_ids);
      filteredCalls = filteredCalls.filter(call => ids.has(call.id));
    }

    if (queryParams.order_by) {
      filteredCalls.sort((a, b) => {
        if (a[queryParams.order_by!] < b[queryParams.order_by!])
          return queryParams.order_dir === 'asc' ? -1 : 1;
        if (a[queryParams.order_by!] > b[queryParams.order_by!])
          return queryParams.order_dir === 'asc' ? 1 : -1;
        return 0;
      });
    }

    if (queryParams.limit) {
      filteredCalls = filteredCalls.slice(0, queryParams.limit);
    }

    return filteredCalls;
  }

  private generateDigest(_data: any): string {
    return uuidv7();
  }

  private _updateChangeTime(): void {
    this._lastChangeTime = Date.now();
    this._lastCallCount = this._calls.length;
  }

  async waitForPendingOperations(
    stabilizationTime: number = 50,
    maxWaitTime: number = 1500,
    minWaitTime: number = 10
  ): Promise<void> {
    const startTime = Date.now();
    const initialCallCount = this._calls.length;
    let hasSeenNewCalls = false;

    await new Promise(resolve => setTimeout(resolve, minWaitTime));

    while (Date.now() - startTime < maxWaitTime) {
      const currentCallCount = this._calls.length;
      const timeSinceLastChange = Date.now() - this._lastChangeTime;

      if (currentCallCount > initialCallCount) {
        hasSeenNewCalls = true;
      }

      if (
        hasSeenNewCalls &&
        currentCallCount === this._lastCallCount &&
        timeSinceLastChange >= stabilizationTime
      ) {
        return;
      }

      if (currentCallCount !== this._lastCallCount) {
        this._lastCallCount = currentCallCount;
        this._lastChangeTime = Date.now();
      }

      await new Promise(resolve => setTimeout(resolve, 5));
    }

    console.warn(
      `waitForPendingOperations timed out after ${maxWaitTime}ms. Calls: initial=${initialCallCount}, final=${this._calls.length}`
    );
  }

  async getCalls(
    projectId: string,
    limit?: number,
    filters?: Partial<Call>
  ): Promise<Call[]> {
    await this.waitForPendingOperations();
    return this.listCalls(projectId, limit, filters);
  }

  listCalls(
    projectId: string,
    limit?: number,
    filters?: Partial<Call>
  ): Call[] {
    return this._filterCalls({
      project_id: projectId,
      limit,
      filters,
    });
  }
}
