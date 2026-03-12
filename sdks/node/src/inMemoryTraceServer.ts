import {uuidv7} from 'uuidv7';

// This is mostly used for testing
// TODO: Maybe move the interfaces to something like trace_server_interface.py

interface Call {
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
  [key: string]: any; // Index signature to allow dynamic property access
}

interface QueryParams {
  project_id: string;
  limit?: number;
  order_by?: keyof Call;
  order_dir?: 'asc' | 'desc';
  filters?: Partial<Call>;
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

export class InMemoryTraceServer {
  private _calls: Call[] = [];
  private _objs: Obj[] = [];
  private _files: File[] = [];
  private _tables: Table[] = [];
  private _lastCallCount: number = 0;
  private _lastChangeTime: number = Date.now();

  call = {
    callStartBatchCallUpsertBatchPost: async (batchReq: {
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
    },
  };

  calls = {
    callsStreamQueryPost: async (queryParams: QueryParams) => {
      let filteredCalls = this._calls.filter(
        call => call.project_id === queryParams.project_id
      );

      // Apply filters if any
      if (queryParams.filters) {
        filteredCalls = filteredCalls.filter(call => {
          return Object.entries(queryParams.filters || {}).every(
            ([key, value]) => call[key] === value
          );
        });
      }

      // Apply ordering
      if (queryParams.order_by) {
        filteredCalls.sort((a, b) => {
          if (a[queryParams.order_by!] < b[queryParams.order_by!])
            return queryParams.order_dir === 'asc' ? -1 : 1;
          if (a[queryParams.order_by!] > b[queryParams.order_by!])
            return queryParams.order_dir === 'asc' ? 1 : -1;
          return 0;
        });
      }

      // Apply limit
      if (queryParams.limit) {
        filteredCalls = filteredCalls.slice(0, queryParams.limit);
      }

      return {
        calls: filteredCalls,
        next_page_token: null, // Simplified: no pagination in this in-memory version
      };
    },
  };

  obj = {
    objCreateObjCreatePost: async (req: {
      obj: {project_id: string; object_id: string; val: any};
    }) => {
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

      // Update version_index and is_latest for existing objects
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

      return {
        data: {
          digest: digest,
        },
      };
    },

    objReadObjReadPost: async (req: {
      project_id: string;
      object_id: string;
      digest?: string;
    }) => {
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

      return {
        data: {
          obj: obj,
        },
      };
    },
  };

  table = {
    tableCreateTableCreatePost: async (req: {
      table: {project_id: string; rows: any[]};
    }) => {
      const digest = this.generateDigest(req.table.rows);

      // Create row entries with individual digests
      const rows = req.table.rows.map(rowVal => ({
        digest: this.generateDigest(rowVal),
        val: rowVal,
      }));

      const newTable: Table = {
        project_id: req.table.project_id,
        digest: digest,
        rows: rows,
      };

      this._tables.push(newTable);

      return {
        data: {
          digest: digest,
        },
      };
    },

    tableQueryTableQueryPost: async (req: {
      project_id: string;
      digest: string;
    }) => {
      const table = this._tables.find(
        t => t.project_id === req.project_id && t.digest === req.digest
      );

      if (!table) {
        throw new Error(
          `Table not found: ${req.project_id}/table/${req.digest}`
        );
      }

      return {
        data: {
          rows: table.rows,
        },
      };
    },
  };

  file = {
    fileCreateFileCreatePost: async (data: {
      project_id: string;
      file: Blob;
    }) => {
      const digest = this.generateDigest(await data.file.arrayBuffer());

      const newFile: File = {
        project_id: data.project_id,
        digest: digest,
        content: data.file,
      };

      this._files.push(newFile);

      return {
        digest: digest,
      };
    },
  };

  feedback = {
    feedbackCreateFeedbackCreatePost: async (req: any) => {
      // Stub implementation for feedback API (used by scorer feedback attachment)
      return {
        data: {
          id: uuidv7(),
        },
      };
    },
  };

  private generateDigest(data: any): string {
    // In a real implementation, you'd want to use a proper hashing algorithm.
    // For simplicity, we're using uuidv7 here.
    return uuidv7();
  }

  private _updateChangeTime(): void {
    this._lastChangeTime = Date.now();
    this._lastCallCount = this._calls.length;
  }

  /**
   * Waits for all pending operations to complete by checking if the call count
   * has stabilized for a minimum period. This is specifically designed for tests
   * where we need to wait for the weave client's async batch processing.
   *
   * @param stabilizationTime - How long to wait for no changes (default: 50ms)
   * @param maxWaitTime - Maximum time to wait before giving up (default: 2000ms)
   * @param minWaitTime - Minimum time to wait even if calls appear immediately (default: 20ms)
   * @returns Promise that resolves when operations have stabilized
   */
  async waitForPendingOperations(
    stabilizationTime: number = 50,
    maxWaitTime: number = 1500,
    minWaitTime: number = 10
  ): Promise<void> {
    const startTime = Date.now();
    const initialCallCount = this._calls.length;
    let hasSeenNewCalls = false;

    // Wait minimum time to allow async operations to start
    await new Promise(resolve => setTimeout(resolve, minWaitTime));

    while (Date.now() - startTime < maxWaitTime) {
      const currentCallCount = this._calls.length;
      const timeSinceLastChange = Date.now() - this._lastChangeTime;

      // Track if we've seen new calls since we started waiting
      if (currentCallCount > initialCallCount) {
        hasSeenNewCalls = true;
      }

      // If we've seen new calls and they've been stable for the stabilization time, we're done
      if (
        hasSeenNewCalls &&
        currentCallCount === this._lastCallCount &&
        timeSinceLastChange >= stabilizationTime
      ) {
        return;
      }

      // Update our tracking
      if (currentCallCount !== this._lastCallCount) {
        this._lastCallCount = currentCallCount;
        this._lastChangeTime = Date.now();
      }

      // Small delay before checking again
      await new Promise(resolve => setTimeout(resolve, 5));
    }

    // If we get here, we timed out, but don't throw - just proceed
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
    const result = await this.calls.callsStreamQueryPost({
      project_id: projectId,
      limit,
      filters,
    });
    return result.calls;
  }

  // ... other existing methods ...
}
