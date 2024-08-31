import { v4 as uuidv4 } from 'uuid';

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

export class InMemoryTraceServer {
    private _calls: Call[] = [];

    call = {
        callStartBatchCallUpsertBatchPost: async (batchReq: { batch: Array<{ mode: 'start' | 'end', req: any }> }) => {
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
        }
    };

    calls = {
        callsStreamQueryPost: async (queryParams: QueryParams) => {
            let filteredCalls = this._calls.filter(call => call.project_id === queryParams.project_id);

            // Apply filters if any
            if (queryParams.filters) {
                filteredCalls = filteredCalls.filter(call => {
                    return Object.entries(queryParams.filters || {}).every(([key, value]) => call[key] === value);
                });
            }

            // Apply ordering
            if (queryParams.order_by) {
                filteredCalls.sort((a, b) => {
                    if (a[queryParams.order_by!] < b[queryParams.order_by!]) return queryParams.order_dir === 'asc' ? -1 : 1;
                    if (a[queryParams.order_by!] > b[queryParams.order_by!]) return queryParams.order_dir === 'asc' ? 1 : -1;
                    return 0;
                });
            }

            // Apply limit
            if (queryParams.limit) {
                filteredCalls = filteredCalls.slice(0, queryParams.limit);
            }

            return {
                calls: filteredCalls,
                next_page_token: null // Simplified: no pagination in this in-memory version
            };
        }
    };
}