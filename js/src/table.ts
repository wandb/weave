export class TableRef {
    constructor(public projectId: string, public digest: string) { }

    public uri() {
        return `weave:///${this.projectId}/table/${this.digest}`;
    }

}

export class Table {
    constructor(public rows: Record<string, any>[]) { }

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