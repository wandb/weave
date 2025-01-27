import {init, login} from '../../clientApi';
import {Table} from '../../table';

describe('table', () => {
  beforeEach(async () => {
    await login(process.env.WANDB_API_KEY ?? '');
  });

  test('example', async () => {
    // Table behaves like a container of rows
    const rows = [
      {a: 1, b: 2},
      {a: 3, b: 4},
      {a: 5, b: 6},
    ];

    const table = new Table(rows);
    expect(table.length).toEqual(rows.length);
    let i = 0;
    for await (const row of table) {
      expect(row).toEqual(rows[i]);
      i++;
    }

    // Saving the table generates refs for the table and its rows
    const client = await init('test-project');

    (client as any).saveTable(table); // TODO: Saving a Table is not public... but maybe it should be?
    const ref = await table.__savedRef;

    // not sure how to test entity here
    // test that the ref is for the right entity, project
    const [entity, project] = ref?.projectId.split('/') ?? [];
    expect(project).toEqual('test-project');
    expect(ref?.uri()).toContain('test-project');

    const row = table.row(0);
    const ref2 = await (row as any).__savedRef; // TODO: This seems wrong... you have to cast to get the ref?  I guess users would rarely do this...
    const [entity2, project2, digest2] = ref2?.projectId.split('/') ?? [];
    expect(project2).toEqual('test-project');
    expect(ref2?.uri()).toContain('test-project');
  });
});
