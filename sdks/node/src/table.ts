import {parseTableRefUri} from './uriParser';

export class TableRef {
  constructor(
    public projectId: string,
    public digest: string
  ) {}

  public uri() {
    return `weave:///${this.projectId}/table/${this.digest}`;
  }

  /**
   * Parse a table ref URI string into a TableRef object.
   * Format: weave:///entity/project/table/digest
   */
  static parseUri(uri: string): TableRef {
    const parsed = parseTableRefUri(uri);
    return new TableRef(parsed.projectId, parsed.digest);
  }
}

export class TableRowRef {
  constructor(
    public projectId: string,
    public digest: string,
    public rowDigest: string
  ) {}

  public uri() {
    return `weave:///${this.projectId}/table/${this.digest}/id/${this.rowDigest}`;
  }
}

type TableRow = Record<string, any> & {
  __savedRef?: TableRowRef | Promise<TableRowRef>;
};

export class Table<R extends TableRow = TableRow> {
  private _rows: R[];
  __savedRef?: TableRef | Promise<TableRef>;

  constructor(rows: R[] | string | TableRef) {
    if (Array.isArray(rows)) {
      this._rows = rows;
    } else {
      // Store ref info but rows not loaded yet
      this._rows = [];
      // Store the ref for later loading
      if (typeof rows === 'string') {
        this.__savedRef = Promise.resolve(TableRef.parseUri(rows));
      } else {
        this.__savedRef = Promise.resolve(rows);
      }
    }
  }

  /**
   * Load table rows from the server if they haven't been loaded yet.
   * This method should be called after constructing a Table with a ref.
   * After loading, rows can be accessed synchronously via getRows(), length, etc.
   */
  async load(): Promise<void> {
    // If rows already loaded (array passed to constructor), nothing to do
    if (this._rows.length > 0) {
      return;
    }

    // If no saved ref, nothing to load
    if (!this.__savedRef) {
      return;
    }

    const tableRef = await this.__savedRef;

    const {requireGlobalClient} = await import('./clientApi');
    const client = requireGlobalClient();

    // Fetch table data from server
    const response = await client.traceServerApi.table.tableQueryTableQueryPost(
      {
        project_id: tableRef.projectId,
        digest: tableRef.digest,
      }
    );

    // Convert to rows with __savedRef
    this._rows = response.data.rows.map((row: any) => {
      const rowData = row.val as R;
      rowData.__savedRef = new TableRowRef(
        tableRef.projectId,
        tableRef.digest,
        row.digest
      );
      return rowData;
    });
  }

  /**
   * Get all rows synchronously.
   * Note: If table was constructed with a ref, you must call load() first.
   */
  get rows(): R[] {
    return this._rows;
  }

  get length(): number {
    return this._rows.length;
  }

  async *[Symbol.asyncIterator](): AsyncIterator<R> {
    for (let i = 0; i < this._rows.length; i++) {
      yield this._rows[i];
    }
  }

  row(index: number): R {
    return this._rows[index];
  }
}
