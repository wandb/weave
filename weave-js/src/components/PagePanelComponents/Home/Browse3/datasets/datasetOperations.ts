import React from 'react';

import {ObjectVersionSchema} from '../pages/wfReactInterface/wfDataModelHooksInterface';

export interface CreateDatasetVersionOptions {
  projectId: string;
  selectedDataset: ObjectVersionSchema;
  datasetObject: any;
  editContextRef: React.MutableRefObject<any>;
  tableUpdate: (
    projectId: string,
    tableDigest: string,
    specs: any
  ) => Promise<any>;
  objCreate: (projectId: string, objectId: string, obj: any) => Promise<any>;
  router: any;
  entity: string;
  project: string;
}

export const createDatasetVersion = async ({
  projectId,
  selectedDataset,
  datasetObject,
  editContextRef,
  tableUpdate,
  objCreate,
  router,
  entity,
  project,
}: CreateDatasetVersionOptions): Promise<{
  url: string;
  objectId: string;
}> => {
  if (!editContextRef.current) {
    throw new Error('Dataset edit context not initialized');
  }

  const originalTableDigest = datasetObject.rows.split('/').pop();
  const tableUpdateSpecs =
    editContextRef.current.convertEditsToTableUpdateSpec();

  const tableUpdateResp = await tableUpdate(
    projectId,
    originalTableDigest,
    tableUpdateSpecs
  );

  if (!tableUpdateResp?.digest) {
    throw new Error('Invalid response from table update');
  }

  const tableRef = `weave:///${projectId}/table/${tableUpdateResp.digest}`;

  const createResp = await objCreate(projectId, selectedDataset.objectId, {
    ...datasetObject,
    rows: tableRef,
  });

  const url = router.objectVersionUIUrl(
    entity,
    project,
    selectedDataset.objectId,
    createResp,
    undefined,
    undefined
  );

  return {
    url,
    objectId: selectedDataset.objectId,
  };
};
