import {requireGlobalClient} from './clientApi';
import {Table} from './table';
import {ObjectRef, WeaveObject, WeaveObjectParameters} from './weaveObject';

interface DatasetParameters<R extends DatasetRow>
  extends WeaveObjectParameters {
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

/**
 * Dataset object with easy saving and automatic versioning
 *
 * @example
 * // Create a dataset
 * const dataset = new Dataset({
 *   id: 'grammar-dataset',
 *   rows: [
 *     { id: '0', sentence: "He no likes ice cream.", correction: "He doesn't like ice cream." },
 *     { id: '1', sentence: "She goed to the store.", correction: "She went to the store." },
 *     { id: '2', sentence: "They plays video games all day.", correction: "They play video games all day." }
 *   ]
 * })
 *
 * // Access a specific example
 * const exampleLabel = dataset.getRow(2).sentence;
 *
 * // Save the dataset
 * const ref = await dataset.save()
 *
 */
export class Dataset<R extends DatasetRow> extends WeaveObject {
  public rows: Table<R>;

  constructor(parameters: DatasetParameters<R>) {
    const baseParameters = {
      id: parameters.id,
      description: parameters.description,
    };
    super(baseParameters);
    this.rows = new Table(parameters.rows);
  }

  async save(): Promise<ObjectRef> {
    return requireGlobalClient().publish(this);
  }

  get length(): number {
    return this.rows.length;
  }

  async *[Symbol.asyncIterator](): AsyncIterator<any> {
    for (let i = 0; i < this.length; i++) {
      yield this.getRow(i);
    }
  }

  getRow(index: number): R {
    const tableRow = this.rows.row(index);
    const datasetRow: R = {...tableRow, __savedRef: undefined};
    if (this.__savedRef && tableRow.__savedRef) {
      datasetRow.__savedRef = Promise.all([
        this.__savedRef,
        tableRow.__savedRef,
      ]).then(([ref, tableRowRef]) => {
        return new DatasetRowRef(
          ref.projectId,
          ref.objectId,
          ref.digest,
          tableRowRef.rowDigest
        );
      });
    }
    return datasetRow;
  }
}
