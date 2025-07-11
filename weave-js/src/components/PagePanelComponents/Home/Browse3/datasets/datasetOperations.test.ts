import {beforeEach, describe, expect, it, vi} from 'vitest';

import {ObjectVersionSchema} from '../pages/wfReactInterface/wfDataModelHooksInterface';
import {createNewDataset, updateExistingDataset} from './datasetOperations';

const mockTableUpdate = vi.fn();
const mockTableCreate = vi.fn();
const mockObjCreate = vi.fn();
const mockRouter = {
  objectVersionUIUrl: vi.fn().mockReturnValue('/mock-url'),
};

beforeEach(() => {
  vi.clearAllMocks();
  mockTableUpdate.mockReset();
  mockTableCreate.mockReset();
  mockObjCreate.mockReset();
});

describe('createNewDataset', () => {
  const createOptions = {
    projectId: 'test-project',
    entity: 'test-entity',
    project: 'test-project',
    datasetName: 'new-dataset',
    rows: [{row: 'data'}],
    tableCreate: mockTableCreate,
    objCreate: mockObjCreate,
    router: mockRouter,
  };

  it('should create a new dataset with initial data', async () => {
    mockTableCreate.mockResolvedValue({digest: 'new-digest'});
    mockObjCreate.mockResolvedValue('v1');

    const result = await createNewDataset(createOptions);

    expect(result).toEqual({
      objectDigest: 'v1',
      url: '/mock-url',
      objectId: 'new-dataset',
    });

    expect(mockTableCreate).toHaveBeenCalledWith({
      table: {
        project_id: 'test-project',
        rows: [{row: 'data'}],
      },
    });

    expect(mockObjCreate).toHaveBeenCalledWith({
      projectId: 'test-project',
      objectId: 'new-dataset',
      val: {
        _type: 'Dataset',
        name: 'new-dataset',
        description: null,
        ref: null,
        _class_name: 'Dataset',
        _bases: ['Object', 'BaseModel'],
        rows: 'weave:///test-entity/test-project/table/new-digest',
      },
    });
  });

  it('should throw error on invalid table create response', async () => {
    mockTableCreate.mockResolvedValue({});
    await expect(createNewDataset(createOptions)).rejects.toThrow(
      'Invalid response from table create'
    );
  });
});

describe('updateExistingDataset', () => {
  const updateOptions = {
    projectId: 'test-project',
    entity: 'test-entity',
    project: 'test-project',
    selectedDataset: {
      objectId: 'dataset-123',
      versionHash: 'abc',
    } as ObjectVersionSchema,
    datasetObject: {rows: 'weave:///old-project/table/old-digest'},
    updateSpecs: [{pop: {index: 0}}, {insert: {index: 0, row: {data: 'new'}}}],
    tableUpdate: mockTableUpdate,
    objCreate: mockObjCreate,
    router: mockRouter,
  };

  it('should update existing dataset with new version', async () => {
    mockTableUpdate.mockResolvedValue({digest: 'updated-digest'});
    mockObjCreate.mockResolvedValue('v2');

    const result = await updateExistingDataset(updateOptions);

    expect(result).toEqual({
      objectDigest: 'v2',
      url: '/mock-url',
      objectId: 'dataset-123',
    });

    expect(mockTableUpdate).toHaveBeenCalledWith({
      projectId: 'test-project',
      baseDigest: 'old-digest',
      updates: [{pop: {index: 0}}, {insert: {index: 0, row: {data: 'new'}}}],
    });

    expect(mockObjCreate).toHaveBeenCalledWith({
      projectId: 'test-project',
      objectId: 'dataset-123',
      val: {
        rows: 'weave:///test-entity/test-project/table/updated-digest',
      },
    });
  });

  it('should throw error on invalid table update response', async () => {
    mockTableUpdate.mockResolvedValue({});
    await expect(updateExistingDataset(updateOptions)).rejects.toThrow(
      'Invalid response from table update'
    );
  });
});
