import {init, login} from '../../clientApi';
import {Dataset} from '../../dataset';

describe('Dataset', () => {
  beforeEach(async () => {
    await login({apiKey: process.env.WANDB_API_KEY ?? ''});
  });

  test('should save a dataset', async () => {
    const client = await init('test-project');
    const data = [
      {id: 1, value: 2},
      {id: 2, value: 3},
      {id: 3, value: 4},
    ];

    const dataset = new Dataset({rows: data});
    const ref = await dataset.save();

    const [entity, project] = ref.projectId.split('/') ?? [];
    expect(project).toBe('test-project');

    // Dataset has same rows as the original data
    expect(dataset.length).toBe(3);
    let i = 0;
    for await (const row of dataset) {
      // need to do this because the row has a __savedRef on it that data wont
      expect({id: row.id, value: row.value}).toEqual(data[i]);
      const rowRef = await row?.__savedRef;
      const [rowEntity, rowProject] = rowRef?.projectId.split('/') ?? [];

      // Rows have refs back to the table
      expect(rowProject).toBe('test-project');
      expect(rowRef?.digest).toBe(ref.digest);
      i++;
    }
  });
});
