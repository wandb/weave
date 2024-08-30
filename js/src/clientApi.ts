import { Api } from './serverApi';
import { v4 as uuidv4 } from 'uuid';
import { uuidv7 } from 'uuidv7';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';

let serverApi: Api<null>;
let globalProjectName: string;
let activeCallStack: { callId: string; traceId: string }[] = [];

function readApiKeyFromNetrc(host: string): string | undefined {
    const netrcPath = path.join(os.homedir(), '.netrc');
    if (!fs.existsSync(netrcPath)) {
        return undefined;
    }

    const netrcContent = fs.readFileSync(netrcPath, 'utf-8');
    const lines = netrcContent.split('\n');
    let foundMachine = false;
    for (const line of lines) {
        const trimmedLine = line.trim();
        if (trimmedLine.startsWith('machine') && trimmedLine.includes(host)) {
            foundMachine = true;
        } else if (foundMachine && trimmedLine.startsWith('password')) {
            return trimmedLine.split(' ')[1];
        }
    }
    return undefined;
}

function init(projectName: string): void {
    globalProjectName = projectName;
    const host = 'https://trace.wandb.ai'
    const apiKey = readApiKeyFromNetrc('api.wandb.ai');
    const headers: Record<string, string> = {
        'User-Agent': `W&B Internal JS Client ${process.env.VERSION || 'unknown'}`,
    };
    console.log('apiKey', apiKey)
    if (apiKey) {
        headers['Authorization'] = `Basic ${Buffer.from(`api:${apiKey}`).toString('base64')}`;
    }
    serverApi = new Api({
        baseUrl: host,
        baseApiParams: {
            headers: headers,
        },
    });
    console.log(`Initializing project: ${projectName}`);

    // Start auto-patching process
    // patchOpenAI();
}

function op(fn: Function, opName?: string) {
    const actualOpName = opName || fn.name || 'anonymous';

    return async function (...args: any[]) {
        if (!globalProjectName) {
            throw new Error("Project not initialized. Call init() first.");
        }

        const startTime = new Date().toISOString();
        const callId = generateCallId();
        let traceId: string;
        let parentId: string | null = null;

        if (activeCallStack.length === 0) {
            traceId = generateTraceId();
        } else {
            traceId = activeCallStack[activeCallStack.length - 1].traceId;
            parentId = activeCallStack[activeCallStack.length - 1].callId;
        }

        activeCallStack.push({ callId, traceId });

        const startReq = {
            start: {
                project_id: globalProjectName,
                id: callId,
                op_name: actualOpName,
                trace_id: traceId,
                parent_id: parentId,
                started_at: startTime,
                attributes: {}, // Add any relevant attributes
                inputs: args.reduce((acc, arg, index) => ({ ...acc, [`arg${index}`]: arg }), {}),
            }
        };

        try {
            await serverApi.call.callStartCallStartPost(startReq);

            console.log(`Operation: ${actualOpName}, Call ID: ${callId}, Trace ID: ${traceId}, Parent ID: ${parentId || 'None'}`);
            const result = await Promise.resolve(fn(...args));

            const endTime = new Date().toISOString();
            const endReq = {
                end: {
                    project_id: globalProjectName,
                    id: callId,
                    ended_at: endTime,
                    output: result,
                    summary: {}, // Add any relevant summary information
                }
            };

            await serverApi.call.callEndCallEndPost(endReq);

            return result;
        } catch (error) {
            const endTime = new Date().toISOString();
            const endReq = {
                end: {
                    project_id: globalProjectName,
                    id: callId,
                    ended_at: endTime,
                    exception: error instanceof Error ? error.message : String(error),
                    summary: {}, // Add any relevant summary information
                }
            };

            await serverApi.call.callEndCallEndPost(endReq);

            throw error;
        } finally {
            activeCallStack.pop();
        }
    }
}

function ref(uri: string) {
    console.log(`Ref: ${uri}`);
}

function generateTraceId(): string {
    return uuidv4(); // Using v4 for traceId
}

function generateCallId(): string {
    return uuidv7(); // Using v7 for callId
}

export { init, op, ref };
