import { boundOp } from "./op";
import { Op } from './opType';

interface WeaveObjectParameters {
    id?: string;
    description?: string;
}

export class ObjectRef {
    constructor(public projectId: string, public objectId: string, public digest: string) { }

    public uri() {
        return `weave:///${this.projectId}/object/${this.objectId}:${this.digest}`;
    }

    public ui_url() {
        return `https://wandb.ai/${this.projectId}/weave/ops/${this.objectId}/versions/${this.digest}`;
    }
}


export class WeaveObject {
    saveAttrNames: string[] = [];
    __savedRef?: ObjectRef | Promise<ObjectRef>;

    constructor(private baseParameters: WeaveObjectParameters) { }

    className() {
        return Object.getPrototypeOf(this).constructor.name;
    }

    saveAttrs() {
        const attrs: { [key: string]: any } = {};
        this.saveAttrNames.forEach(attr => {
            // @ts-ignore
            attrs[attr] = this[attr];
        });
        return attrs;
    }

    id() {
        return this.baseParameters.id;
    }

    description() {
        return this.baseParameters.description;
    }
}

interface DatasetParameters extends WeaveObjectParameters {
    rows: Record<string, any>[];
}

// TODO: use table
export class DatasetFake extends WeaveObject {
    saveAttrNames = ['rows'];
    private rows: Record<string, any>[];

    constructor(parameters: DatasetParameters) {
        const baseParameters = {
            id: parameters.id,
            description: parameters.description
        }
        super(baseParameters);
        this.rows = parameters.rows;
    }

    async *[Symbol.asyncIterator](): AsyncIterator<any> {
        for (const item of this.rows) {
            yield item;
        }
    }

    row(index: number) {
        return this.rows[index];
    }
}

interface EvaluationParameters extends WeaveObjectParameters {
    dataset: DatasetFake;
    scorers: Op<any>[];
}

export class Evaluation extends WeaveObject {
    saveAttrNames = ['dataset', 'scorers'];
    private dataset: DatasetFake;
    private scorers: Op<any>[];

    constructor(parameters: EvaluationParameters) {
        super(parameters);
        this.dataset = parameters.dataset;
        this.scorers = parameters.scorers;
        this.evaluate = boundOp(this, this.evaluate);
    }

    async evaluate(model: Op<any>) {
        const results: Array<{ item: any, modelOutput: any, scores: { [key: string]: any } }> = [];
        for await (const item of this.dataset) {
            const modelOutput = await model(item);

            const scores: { [key: string]: any } = {};
            for (const scorer of this.scorers) {
                const score = await scorer(modelOutput, item);
                scores[scorer.name] = score;
            }
            results.push({ item, modelOutput, scores });
        }
        return results
    }
}

// TODO: match python
export function getClassChain(instance: WeaveObject): string[] {
    const bases: string[] = [];
    let currentProto = Object.getPrototypeOf(instance);

    while (currentProto && currentProto.constructor.name !== 'Object') {
        bases.push(currentProto.constructor.name);
        currentProto = Object.getPrototypeOf(currentProto);
    }

    return bases;
}