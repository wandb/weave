import {beforeEach, describe, expect, it, vi} from 'vitest';

import {ObjectVersionSchema} from '../pages/wfReactInterface/wfDataModelHooksInterface';
import type {CreateDatasetVersionOptions} from './datasetOperations';
import {createDatasetVersion} from './datasetOperations';

const mockTableUpdate = vi.fn();
const mockObjCreate = vi.fn();
const mockRouter = {
  objectVersionUIUrl: vi.fn().mockReturnValue('/mock-url'),
};

const mockEditContext = {
  convertEditsToTableUpdateSpec: vi.fn().mockReturnValue({testSpec: true}),
};

const baseOptions: CreateDatasetVersionOptions = {
  projectId: 'test-project',
  selectedDataset: {objectId: 'dataset-123'} as ObjectVersionSchema,
  datasetObject: {rows: 'weave:///old-project/table/old-digest'},
  editContextRef: {current: mockEditContext},
  tableUpdate: mockTableUpdate,
  objCreate: mockObjCreate,
  router: mockRouter,
  entity: 'test-entity',
  project: 'test-project',
};

beforeEach(() => {
  vi.clearAllMocks();
  mockTableUpdate.mockReset();
  mockObjCreate.mockReset();
  mockEditContext.convertEditsToTableUpdateSpec.mockReturnValue({
    testSpec: true,
  });
});

describe('createDatasetVersion', () => {
  it('should create new version and return URL with updated table reference', async () => {
    mockTableUpdate.mockResolvedValue({digest: 'new-digest'});
    mockObjCreate.mockResolvedValue({version: 'v1'});

    const result = await createDatasetVersion(baseOptions);

    expect(result).toEqual({
      url: '/mock-url',
      objectId: 'dataset-123',
    });

    // Verify table operations
    expect(mockTableUpdate).toHaveBeenCalledWith('test-project', 'old-digest', {
      testSpec: true,
    });

    // Verify object creation
    expect(mockObjCreate).toHaveBeenCalledWith('test-project', 'dataset-123', {
      ...baseOptions.datasetObject,
      rows: 'weave:///test-project/table/new-digest',
    });

    // Verify URL generation
    expect(baseOptions.router.objectVersionUIUrl).toHaveBeenCalledWith(
      'test-entity',
      'test-project',
      'dataset-123',
      {version: 'v1'},
      undefined,
      undefined
    );
  });

  it('should handle cross-project table references', async () => {
    mockTableUpdate.mockResolvedValue({digest: 'cross-project-digest'});
    await createDatasetVersion({
      ...baseOptions,
      datasetObject: {rows: 'weave:///other-project/table/other-digest'},
    });

    expect(mockTableUpdate).toHaveBeenCalledWith(
      'test-project',
      'other-digest',
      {testSpec: true}
    );
    expect(mockObjCreate.mock.calls[0][2].rows).toBe(
      'weave:///test-project/table/cross-project-digest'
    );
  });

  it('should throw error when edit context is not initialized', async () => {
    const invalidOptions = {
      ...baseOptions,
      editContextRef: {current: null},
    };

    await expect(createDatasetVersion(invalidOptions)).rejects.toThrow(
      'Dataset edit context not initialized'
    );
  });

  it('should throw error on invalid table update response', async () => {
    mockTableUpdate.mockResolvedValue({});
    await expect(createDatasetVersion(baseOptions)).rejects.toThrow(
      'Invalid response from table update'
    );
  });

  it('should handle table update errors', async () => {
    const error = new Error('Table update failed');
    mockTableUpdate.mockRejectedValue(error);
    await expect(createDatasetVersion(baseOptions)).rejects.toThrow(error);
  });

  it('should handle object creation errors', async () => {
    const error = new Error('Invalid response from table update');
    mockObjCreate.mockRejectedValue(error);
    await expect(createDatasetVersion(baseOptions)).rejects.toThrow(error);
  });
});
