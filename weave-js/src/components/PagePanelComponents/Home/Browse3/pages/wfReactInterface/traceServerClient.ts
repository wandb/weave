/**
 * This file defines the connection between the web client and the trace server.
 * The intention is that the implementation is a 1-1 mapping to the trace
 * server's API. This file should not contain any business logic. If possible,
 * we could generate this from `trace_server.py`. Which in effect is a perfect
 * mapping of `weave/trace_server/trace_server_interface.py` as a web service.
 *
 * These types MUST be kept in sync with the types defined in
 * `weave/trace_server/trace_server_interface.py`. Please modify with care.
 *
 * TODO: Currently, we only implement Call Read and Call Query - there are
 * several other endpoints that we should implement.
 */

import fetch from 'isomorphic-unfetch';

export type KeyedDictType = {
  [key: string]: any;
  _keys?: string[];
};

export type TraceCallSchema = {
  project_id: string;
  id: string;
  name: string;
  trace_id: string;
  parent_id?: string;
  start_datetime: string;
  attributes: KeyedDictType;
  inputs: KeyedDictType;
  end_datetime?: string;
  exception?: string;
  outputs?: KeyedDictType;
  summary?: KeyedDictType;
  wb_run_id?: string;
  wb_user_id?: string;
};

type TraceCallReadReq = {
  project_id: string;
  id: string;
};

export type TraceCallReadRes = {
  call: TraceCallSchema;
};

interface TraceCallsFilter {
  op_version_refs?: string[];
  input_object_version_refs?: string[];
  output_object_version_refs?: string[];
  parent_ids?: string[];
  trace_ids?: string[];
  call_ids?: string[];
  trace_roots_only?: boolean;
  wb_run_ids?: string[];
  wb_user_ids?: string[];
}

type TraceCallsQueryReq = {
  project_id: string;
  filter?: TraceCallsFilter;
  limit?: number;
  offset?: number;
};

export type TraceCallsQueryRes = {
  calls: TraceCallSchema[];
};

interface TraceObjectsFilter {
  object_names?: string[];
  is_op?: boolean;
  latest_only?: boolean;
}

type TraceObjQueryReq = {
  project_id: string;
  filter?: TraceObjectsFilter;
};

export interface TraceObjSchema {
  project_id: string;
  name: string;
  created_at: string;
  digest: string;
  version_index: number;
  is_latest: number;
  type: string;
  val: any;
}

type TraceObjQueryRes = {
  objs: TraceObjSchema[];
};

export type TraceRefsReadBatchReq = {
  refs: string[];
};

export type TraceRefsReadBatchRes = {
  vals: any[];
};

export type TraceTableQueryReq = {
  project_id: string;
  table_digest: string;
  filter?: {
    row_digests?: string[];
  };
  limit?: number;
};

export type TraceTableQueryRes = {
  rows: Array<{
    digest: string;
    val: any;
  }>;
};

export class TraceServerClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  callsQuery: (req: TraceCallsQueryReq) => Promise<TraceCallsQueryRes> =
    req => {
      return this.makeRequest<TraceCallsQueryReq, TraceCallsQueryRes>(
        '/calls/query',
        req
      );
    };
  callRead: (req: TraceCallReadReq) => Promise<TraceCallReadRes> = req => {
    return this.makeRequest<TraceCallReadReq, TraceCallReadRes>(
      '/call/read',
      req
    );
  };
  objsQuery: (req: TraceObjQueryReq) => Promise<TraceObjQueryRes> = req => {
    return this.makeRequest<TraceObjQueryReq, TraceObjQueryRes>(
      '/objs/query',
      req
    );
  };

  readBatch: (req: TraceRefsReadBatchReq) => Promise<TraceRefsReadBatchRes> =
    req => {
      return this.makeRequest<TraceRefsReadBatchReq, TraceRefsReadBatchRes>(
        '/refs/read_batch',
        req
      );
    };

  tableQuery: (req: TraceTableQueryReq) => Promise<TraceTableQueryRes> =
    req => {
      return this.makeRequest<TraceTableQueryReq, TraceTableQueryRes>(
        '/table/query',
        req
      );
    };

  private makeRequest = async <QT, ST>(
    endpoint: string,
    req: QT
  ): Promise<ST> => {
    const url = `${this.baseUrl}${endpoint}`;

    // eslint-disable-next-line wandb/no-unprefixed-urls
    const response = await fetch(url, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(req),
    });
    const res = await response.json();
    return res;
  };
}

const MAX_CHUNK_SIZE = 10000;

/**
 * Use this function to query calls from the trace server. This function will
 * handle chunking the results if the user requests more than `MAX_CHUNK_SIZE`
 * calls. This is to protect the server from returning too much data at once.
 *
 * Note: we should probably roll this into the `callsQuery` directly, but I don't
 * want to change the API right now to support cancelation.
 */
export const chunkedCallsQuery = (
  client: TraceServerClient,
  req: TraceCallsQueryReq,
  onSuccess: (res: TraceCallsQueryRes) => void,
  onError: (err: any) => void
): {
  cancel: () => void;
} => {
  let cancelled = false;

  const safeOnSuccess = (res: TraceCallsQueryRes) => {
    if (!cancelled) {
      onSuccess(res);
    }
  };

  const safeOnError = (err: any) => {
    if (!cancelled) {
      onError(err);
    }
  };

  const fetchCalls = async () => {
    const userRequestedLimit = req.limit ?? Infinity;
    const userRequestedOffset = req.offset ?? 0;
    const shouldPage = userRequestedLimit > MAX_CHUNK_SIZE;
    if (!shouldPage) {
      // If the user requested less than the max chunk size, we can just
      // make a single request.
      let page: TraceCallsQueryRes;
      try {
        page = await client.callsQuery(req);
      } catch (err) {
        safeOnError(err);
        return;
      }
      safeOnSuccess(page);
    } else {
      const allCallResults: TraceCallSchema[] = [];
      let effectiveOffset = userRequestedOffset;
      let effectiveRemainingLimit = userRequestedLimit;

      // Keep paging until we have all the results requested.
      while (effectiveRemainingLimit > 0) {
        const effectiveLimit = Math.min(
          effectiveRemainingLimit,
          MAX_CHUNK_SIZE
        );
        const pageReq = {
          ...req,
          limit: effectiveLimit,
          offset: effectiveOffset,
        };
        let page: TraceCallsQueryRes;
        try {
          page = await client.callsQuery(pageReq);
        } catch (err) {
          safeOnError(err);
          return;
        }
        allCallResults.push(...page.calls);
        effectiveRemainingLimit -= page.calls.length;
        effectiveOffset += page.calls.length;

        // Break if we have less than the requested limit.
        if (page.calls.length < effectiveLimit) {
          break;
        }
      }

      safeOnSuccess({
        calls: allCallResults,
      });
    }
  };
  fetchCalls();
  return {
    cancel: () => {
      cancelled = true;
    },
  };
};
