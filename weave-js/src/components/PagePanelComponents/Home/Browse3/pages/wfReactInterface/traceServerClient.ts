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

export interface TraceCallSchema {
  entity: string;
  project: string;
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
}

interface TraceCallReadReq {
  entity: string;
  project: string;
  id: string;
}

export interface TraceCallReadRes {
  call: TraceCallSchema;
}

interface TraceCallsFilter {
  op_version_refs?: string[];
  input_object_version_refs?: string[];
  output_object_version_refs?: string[];
  parent_ids?: string[];
  trace_ids?: string[];
  call_ids?: string[];
  trace_roots_only?: boolean;
}

interface TraceCallsQueryReq {
  entity: string;
  project: string;
  filter?: TraceCallsFilter;
  limit?: number;
}

export interface TraceCallsQueryRes {
  calls: TraceCallSchema[];
}

export class TraceServerClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private makeRequest = async <QT, ST>(endpoint: string, req: QT): Promise<ST> => {
    const url = `${this.baseUrl}${endpoint}`;

    // eslint-disable-next-line wandb/no-unprefixed-urls
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(req),
    });
    const res = await response.json();
    return res;

  };

  callsQuery: (req: TraceCallsQueryReq) => Promise<TraceCallsQueryRes> = (req) => {
    return this.makeRequest<TraceCallsQueryReq, TraceCallsQueryRes>('/calls/query', req);
  }
  callRead: (req: TraceCallReadReq) => Promise<TraceCallReadRes> = (req) => {
    return this.makeRequest<TraceCallReadReq, TraceCallReadRes>('/call/read', req);
  }
}

