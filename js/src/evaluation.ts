import { WeaveObject, WeaveObjectParameters } from "./weaveObject";
import { Op, getOpName } from "./opType";
import { boundOp } from "./op";
import { Dataset } from "./dataset";

interface EvaluationParameters extends WeaveObjectParameters {
    dataset: Dataset;
    scorers: Op<any>[];
}

export class Evaluation extends WeaveObject {
    saveAttrNames = ['dataset', 'scorers'];
    private dataset: Dataset;
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
