/**
 * Tests for Dataset and Table lazy loading
 */

import {Dataset} from '../dataset';
import {ObjectRef} from '../weaveObject';
import {InMemoryTraceServer} from '../inMemoryTraceServer';
import {initWithCustomTraceServer} from './clientMock';
import {requireGlobalClient} from '../clientApi';

describe('Dataset', () => {
  let traceServer: InMemoryTraceServer;
  const projectId = 'wandb/test-project';

  beforeEach(() => {
    traceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(projectId, traceServer);
  });

  test('hello world', () => {
    expect(1 + 1).toBe(2);
  });

  test('round trip: create dataset and read it back', async () => {
    const client = requireGlobalClient();

    // Create a dataset with some rows
    const originalRows = [
      {id: 1, name: 'Alice', score: 0.95},
      {id: 2, name: 'Bob', score: 0.87},
      {id: 3, name: 'Charlie', score: 0.92},
    ];

    const dataset = new Dataset({
      name: 'test-dataset',
      description: 'A test dataset',
      rows: originalRows,
    });

    // Save the dataset
    const ref = await dataset.save();

    expect(ref).toBeInstanceOf(ObjectRef);
    expect(ref.projectId).toBe(projectId);
    expect(ref.objectId).toBe('test-dataset');

    // Read the dataset back using the factory method
    const uri = `weave:///${projectId}/object/test-dataset:${ref.digest}`;
    const refFromUri = ObjectRef.fromUri(uri);
    const retrievedDataset = await client.get(refFromUri);

    expect(retrievedDataset).toBeInstanceOf(Dataset);
    expect(retrievedDataset.name).toBe('test-dataset');
    expect(retrievedDataset.description).toBe('A test dataset');

    // Check that rows are loaded and accessible synchronously
    expect(retrievedDataset.length).toBe(3);

    const rows = retrievedDataset.rows.rows;
    expect(rows).toHaveLength(3);
    expect(rows[0]).toMatchObject({id: 1, name: 'Alice', score: 0.95});
    expect(rows[1]).toMatchObject({id: 2, name: 'Bob', score: 0.87});
    expect(rows[2]).toMatchObject({id: 3, name: 'Charlie', score: 0.92});

    // Test getRow method
    const row0 = retrievedDataset.getRow(0);
    expect(row0).toMatchObject({id: 1, name: 'Alice', score: 0.95});

    // Test table.row method
    const tableRow1 = retrievedDataset.rows.row(1);
    expect(tableRow1).toMatchObject({id: 2, name: 'Bob', score: 0.87});

    // Verify __savedRef is attached to rows
    expect(rows[0].__savedRef).toBeDefined();
    expect(rows[1].__savedRef).toBeDefined();
  });
});
