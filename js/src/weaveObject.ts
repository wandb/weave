import { boundOp } from "./op";
import { Op, getOpName } from './opType';

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
        this.predict_and_score = boundOp(this, this.predict_and_score);
    }

    async evaluate({ model }: { model: Op<any> }) {
        const results: Array<{ modelOutput: any, scores: { [key: string]: any }, modelLatency: number }> = [];
        for await (const example of this.dataset) {
            const result = await this.predict_and_score({ model, example });
            results.push(result);
        }
        return this.summarizeResults(results);
    }

    async predict_and_score({ model, example }: { model: Op<any>, example: Record<string, any> }) {
        const startTime = new Date();
        const modelOutput = await model(example);
        const endTime = new Date();
        const modelLatency = (endTime.getTime() - startTime.getTime()) / 1000; // Convert to seconds

        const scores: { [key: string]: any } = {};
        for (const scorer of this.scorers) {
            const score = await scorer(modelOutput, example);
            scores[getOpName(scorer)] = score;
        }

        return { modelOutput, scores, modelLatency };
    }

    private summarizeResults(results: Array<{ modelOutput: any, scores: { [key: string]: any }, modelLatency: number }>) {
        const summarizeNestedObject = (obj: any, currentPath: string = ''): Record<string, any> => {
            const nestedSummary: Record<string, any> = {};

            for (const [key, value] of Object.entries(obj)) {
                const newPath = currentPath ? `${currentPath}.${key}` : key;

                if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                    nestedSummary[key] = summarizeNestedObject(value, newPath);
                } else {
                    const values = results.map(result => {
                        const keys = newPath.split('.');
                        return keys.reduce((acc: any, k) => acc && acc[k], result);
                    });

                    const columnSummary = this.summarizeColumn(values);
                    if (Object.keys(columnSummary).length > 0) {
                        nestedSummary[key] = columnSummary;
                    }
                }
            }

            return nestedSummary;
        };

        // Use the first result as a template for the structure
        const templateResult = results[0];
        return summarizeNestedObject(templateResult);
    }

    private summarizeColumn(values: any[]): Record<string, number> {
        if (values.every(v => typeof v === 'boolean')) {
            const trueCount = values.filter(v => v).length;
            return {
                true_count: trueCount,
                true_fraction: trueCount / values.length
            };
        } else if (values.every(v => typeof v === 'number')) {
            const sum = values.reduce((acc, v) => acc + v, 0);
            return {
                mean: sum / values.length
            };
        }
        return {};
    }
}

export function getClassChain(instance: WeaveObject): string[] {
    const bases: string[] = [];
    let currentProto = Object.getPrototypeOf(instance);

    while (currentProto && currentProto.constructor.name !== 'Object') {
        bases.push(currentProto.constructor.name);
        currentProto = Object.getPrototypeOf(currentProto);
    }

    return bases;
}