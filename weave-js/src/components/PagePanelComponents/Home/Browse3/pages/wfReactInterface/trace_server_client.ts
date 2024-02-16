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
type CallQueryRes = {
    calls: Array<TraceCallSchema>
}

export const fetchAllCalls = async (): Promise<CallQueryRes> => {
    const url = "http://127.0.0.1:6345/calls/query"
    // eslint-disable-next-line wandb/no-unprefixed-urls
    const response = await fetch(url, {
        method: 'POST',
        headers: {
        'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            "entity": "test_entity",
            "project": "test_project",
        }),
    });
    return response.json();
}
