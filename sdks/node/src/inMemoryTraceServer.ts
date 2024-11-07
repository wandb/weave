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

export class InMemoryTraceServer {
  private _calls: Call[] = [];
  private _objs: Obj[] = [];
  private _files: File[] = [];

  call = {
    callStartBatchCallUpsertBatchPost: async (batchReq: {
      batch: Array<{mode: 'start' | 'end'; req: any}>;
    }) => {
      for (const item of batchReq.batch) {
        if (item.mode === 'start') {
          this._calls.push(item.req.start);
        } else if (item.mode === 'end') {
          const call = this._calls.find(c => c.id === item.req.end.id);
          if (call) {
            Object.assign(call, item.req.end);
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

  private generateDigest(data: ArrayBuffer): string {
    // In a real implementation, you'd want to use a proper hashing algorithm.
    // For simplicity, we're using uuidv7 here.
    return uuidv7();
  }

  // ... other existing methods ...
}
