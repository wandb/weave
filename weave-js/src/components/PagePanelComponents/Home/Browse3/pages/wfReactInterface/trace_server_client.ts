import fetch from 'isomorphic-unfetch';

type StatusCodeEnum = "OK" | "ERROR" | "UNSET"

// This should match `trace_server_interface.py::CallSchema` exactly!!
export type TraceCallSchema = {
    entity: string;
    project: string;
    id: string;
    
    name: string;

    trace_id: string;
    parent_id?: string;
    
    status_code: StatusCodeEnum;
    start_time_s: number;
    end_time_s?: number;
    exception?: string;
    
    attributes?: Record<string, any>;
    inputs?: Record<string, any>;
    outputs?: Record<string, any>;
    summary?: Record<string, any>;
}
type TraceCallQueryRes = {
    calls: Array<TraceCallSchema>
}

type Trace_CallsFilter = {
    names?: string[];
    input_object_version_refs?: string[];
    output_object_version_refs?: string[];
    parent_ids?: string[];
    trace_ids?: string[];
    call_ids?: string[];
    trace_roots_only?: boolean;
}

type TraceCallsQueryReq= {
    entity: string,
    project: string,
    filter?: Trace_CallsFilter
    // # TODO: Bring other fields from `trace_server_interface.py::TraceCallsQueryReq`
}



export const callsQuery = async (req: TraceCallsQueryReq): Promise<TraceCallQueryRes> => {
    const url = "http://127.0.0.1:6345/calls/query"
    // eslint-disable-next-line wandb/no-unprefixed-urls
    const response = await fetch(url, {
        method: 'POST',
        headers: {
        'Content-Type': 'application/json',
        },
        body: JSON.stringify(req),
    });
    const res = await response.json();
    console.log("Retrieved trace calls: ", res.calls.length)
    return res;
}
