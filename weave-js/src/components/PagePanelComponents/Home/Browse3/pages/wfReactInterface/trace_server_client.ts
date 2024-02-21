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

// This should match `trace_server_interface.py::TraceObjSchema` exactly!!
export type TraceObjSchema = {
    entity: string;
    project: string;
    name: string;
    version_hash: string;

    type_dict: {[key: string]: any};
    encoded_file_map_as_length_and_big_int: {[key: string]: [number, number]};
    metadata_dict: {[key: string]: any};

    created_at_s: number
}

type Trace_ObjsFilter = {

}

type TraceObjsQueryReq= {
    entity: string,
    project: string,
    filter?: Trace_ObjsFilter
    // # TODO: Bring other fields from `trace_server_interface.py::TraceCallsQueryReq`
}

type TraceObjQueryRes = {
    objs: Array<TraceObjSchema>
}



type TraceObjReadReq = {
    entity: string,
    project: string,
    name: string,
    version_hash: string
}

type  TraceObjReadRes = {
    obj: TraceObjSchema
}


const makeTraceServerEndpointFn = <QT, ST,>(endpoint: string) => {
    const baseUrl = "http://127.0.0.1:6345"
    const url = `${baseUrl}${endpoint}`
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
        return res;
    }
    return fn
}



export const callsQuery = makeTraceServerEndpointFn<TraceCallsQueryReq, TraceCallQueryRes>("/calls/query")
export const objectsQuery = makeTraceServerEndpointFn<TraceObjsQueryReq, TraceObjQueryRes>("/objs/query")
export const objectsRead = makeTraceServerEndpointFn<TraceObjReadReq, TraceObjReadRes>("/obj/read")

