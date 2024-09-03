import { WeaveObject, WeaveObjectParameters } from "./weaveObject";
import { Table } from "./table";

interface DatasetParameters extends WeaveObjectParameters {
    rows: Record<string, any>[];
}

export class Dataset extends WeaveObject {
    saveAttrNames = ['rows'];
    private rows: Table;

    constructor(parameters: DatasetParameters) {
        const baseParameters = {
            id: parameters.id,
            description: parameters.description
        }
        super(baseParameters);
        this.rows = new Table(parameters.rows);
    }

    get length(): number {
        return this.rows.length;
    }

    async *[Symbol.asyncIterator](): AsyncIterator<any> {
        for await (const item of this.rows) {
            yield item;
        }
    }

    row(index: number) {
        this.rows.row(index)
    }
}