import { WeaveObject, WeaveObjectParameters, ObjectRef } from "./weaveObject";
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

    async save(): Promise<ObjectRef> {
        // Need require because of circular dependency
        const client = require('./clientApi').globalClient;
        return client.saveObject(this);
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
        return this.rows.row(index)
    }
}