import {init, login} from '../../clientApi';
import {Table} from '../../table';
import {getWandbConfigs} from '../../wandb/settings';
import {vcrTest} from '../helpers/vcrTest';

describe('Table', () => {
  beforeEach(async () => {
    const {apiKey} = getWandbConfigs();
    await login(apiKey ?? '');
  });

  vcrTest('example', async () => {
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
    const [_entity, project] = ref?.projectId.split('/') ?? [];
    expect(project).toEqual('test-project');
    expect(ref?.uri()).toContain('test-project');

    const row = table.row(0);
    const ref2 = await (row as any).__savedRef; // TODO: This seems wrong... you have to cast to get the ref?  I guess users would rarely do this...
    const [_entity2, project2, _digest2] = ref2?.projectId.split('/') ?? [];
    expect(project2).toEqual('test-project');
    expect(ref2?.uri()).toContain('test-project');
  });
});
