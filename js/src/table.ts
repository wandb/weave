export class TableRef {
    constructor(public projectId: string, public digest: string) { }

    public uri() {
        return `weave:///${this.projectId}/table/${this.digest}`;
    }

}

export class TableRowRef {
    constructor(public projectId: string, public digest: string, public rowDigest: string) { }

    public uri() {
        return `weave:///${this.projectId}/table/${this.digest}/id/${this.rowDigest}`;
    }

}

type TableRow = Record<string, any> & {
    __savedRef?: TableRowRef | Promise<TableRowRef>;
}

export class Table {
    __savedRef?: TableRef | Promise<TableRef>;

    constructor(public rows: TableRow[]) { }

    get length(): number {
        return this.rows.length;
    }

    async *[Symbol.asyncIterator](): AsyncIterator<any> {
        for (let i = 0; i < this.length; i++) {
            yield this.row(i);
        }
    }

    row(index: number): TableRow {
        return this.rows[index];
    }
}