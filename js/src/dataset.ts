import { WeaveObject, WeaveObjectParameters } from "./weaveObject";

interface DatasetParameters extends WeaveObjectParameters {
    rows: Record<string, any>[];
}

export class Dataset extends WeaveObject {
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

    get length(): number {
        return this.rows.length;
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