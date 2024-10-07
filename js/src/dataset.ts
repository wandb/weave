import {Table} from './table';
import {ObjectRef, WeaveObject, WeaveObjectParameters} from './weave-object';

interface DatasetParameters<R extends DatasetRow> extends WeaveObjectParameters {
  rows: R[];
}

export class DatasetRowRef {
  constructor(
    public projectId: string,
    public objId: string,
    public digest: string,
    public rowDigest: string
  ) {}

  public uri() {
    return `weave:///${this.projectId}/object/${this.objId}:${this.digest}/attr/rows/id/${this.rowDigest}`;
  }
}

export type DatasetRow = Record<string, any> & {
  __savedRef?: DatasetRowRef | Promise<DatasetRowRef>;
};

export class Dataset<R extends DatasetRow> extends WeaveObject {
  public rows: Table<R>;

  constructor({rows, ...baseParameters}: DatasetParameters<R>) {
    super(baseParameters);
    this.rows = new Table(rows);
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
    for (let i = 0; i < this.length; i++) {
      yield this.row(i);
    }
  }

  row(index: number): R {
    const tableRow = this.rows.row(index);
    const datasetRow: R = {...tableRow, __savedRef: undefined};
    if (this.__savedRef && tableRow.__savedRef) {
      datasetRow.__savedRef = Promise.all([this.__savedRef, tableRow.__savedRef]).then(([ref, tableRowRef]) => {
        return new DatasetRowRef(ref.projectId, ref.objectId, ref.digest, tableRowRef.rowDigest);
      });
    }
    return datasetRow;
  }
}
