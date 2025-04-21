import {createWeaveTableRef} from '../../../../../react';
import {
  TableCreateReq,
  TableCreateRes,
} from '../pages/wfReactInterface/traceServerClientTypes';
import {ObjectVersionSchema} from '../pages/wfReactInterface/wfDataModelHooksInterface';

export interface CreateNewDatasetOptions {
  projectId: string;
  entity: string;
  project: string;
  datasetName: string;
  rows: Array<Record<string, any>>;
  tableCreate: (table: TableCreateReq) => Promise<TableCreateRes>;
  objCreate: (projectId: string, objectId: string, obj: any) => Promise<any>;
  router: any;
}

export interface UpdateDatasetOptions {
  projectId: string;
  entity: string;
  project: string;
  selectedDataset: ObjectVersionSchema;
  datasetObject: any;
  updateSpecs: Array<
    {pop: {index: number}} | {insert: {index: number; row: Record<string, any>}}
  >;
  tableUpdate: (
    projectId: string,
    tableDigest: string,
    specs: any
  ) => Promise<any>;
  objCreate: (projectId: string, objectId: string, obj: any) => Promise<any>;
  router: any;
}

export const createNewDataset = async ({
  projectId,
  entity,
  project,
  datasetName,
  rows,
  tableCreate,
  objCreate,
  router,
}: CreateNewDatasetOptions) => {
  const newTableResult = await tableCreate({
    table: {
      project_id: projectId,
      rows,
    },
  });

  if (!newTableResult?.digest) {
    console.error('Invalid response from table create', newTableResult);
    throw new Error('Invalid response from table create');
  }

  const newTableRef = createWeaveTableRef(
    entity,
    project,
    newTableResult.digest
  );

  const newDatasetResp = await objCreate(projectId, datasetName, {
    _type: 'Dataset',
    name: datasetName,
    description: null,
    ref: null,
    _class_name: 'Dataset',
    _bases: ['Object', 'BaseModel'],
    rows: newTableRef,
  });

  const newDatasetUrl = router.objectVersionUIUrl(
    entity,
    project,
    datasetName,
    newDatasetResp,
    undefined,
    undefined
  );

  return {
    url: newDatasetUrl,
    objectId: datasetName,
  };
};

export const updateExistingDataset = async ({
  projectId,
  entity,
  project,
  selectedDataset,
  datasetObject,
  updateSpecs,
  tableUpdate,
  objCreate,
  router,
}: UpdateDatasetOptions) => {
  const existingTableDigest = datasetObject.rows.split('/').pop();

  const updatedTableResult = await tableUpdate(
    projectId,
    existingTableDigest,
    updateSpecs
  );

  if (!updatedTableResult?.digest) {
    throw new Error('Invalid response from table update');
  }

  const updatedTableRef = createWeaveTableRef(
    entity,
    project,
    updatedTableResult.digest
  );

  const updatedDatasetResp = await objCreate(
    projectId,
    selectedDataset.objectId,
    {
      ...datasetObject,
      rows: updatedTableRef,
    }
  );

  const updatedDatasetUrl = router.objectVersionUIUrl(
    entity,
    project,
    selectedDataset.objectId,
    updatedDatasetResp,
    undefined,
    undefined
  );

  return {
    url: updatedDatasetUrl,
    objectId: selectedDataset.objectId,
  };
};
