import { WeaveObject } from "./weaveObject";


export type Op<T extends (...args: any[]) => any> = {
    __isOp: true;
    wrappedFunction: T;
    __boundThis?: WeaveObject;
    __name: string;
} & T;
interface StreamReducer<T, R> {
    initialState: R;
    reduceFn: (state: R, chunk: T) => R;
}

export interface OpOptions<T extends (...args: any[]) => any> {
    name?: string;
    streamReducer?: StreamReducer<any, any>;
    originalFunction?: T;
    summarize?: (result: Awaited<ReturnType<T>>) => Record<string, any>;
    bindThis?: WeaveObject;
}

export function isOp(value: any): value is Op<any> {
    return value && value.__isOp === true;
}

export function getOpWrappedFunction<T extends (...args: any[]) => any>(opValue: Op<T>): T {
    return opValue.wrappedFunction;
}

export function getOpName(opValue: Op<any>): string {
    return opValue.__name;
}

export class OpRef {
    constructor(public projectId: string, public objectId: string, public digest: string) { }

    public uri() {
        return `weave:///${this.projectId}/op/${this.objectId}:${this.digest}`;
    }
}
