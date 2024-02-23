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
}

export interface TraceCallQueryRes {
  calls: TraceCallSchema[];
}

const makeTraceServerEndpointFn = <QT, ST>(endpoint: string) => {
  // TODO: make this configurable
  const baseUrl = 'http://127.0.0.1:6345';
  const url = `${baseUrl}${endpoint}`;
  const fn = async (req: QT): Promise<ST> => {
    // eslint-disable-next-line wandb/no-unprefixed-urls
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(req),
    });
    const res = await response.json();
    console.log(res);
    return res;
  };
  return fn;
};

export const callsQuery = makeTraceServerEndpointFn<
  TraceCallsQueryReq,
  TraceCallQueryRes
>('/calls/query');

export const callRead = makeTraceServerEndpointFn<
  TraceCallReadReq,
  TraceCallReadRes
>('/call/read');
