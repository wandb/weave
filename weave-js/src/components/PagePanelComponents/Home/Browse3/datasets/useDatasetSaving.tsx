import {makeRefObject} from '@wandb/weave/util/refs';
import React from 'react';
import {toast} from 'react-toastify';

import {useWeaveflowCurrentRouteContext} from '../context';
import {useWFHooks} from '../pages/wfReactInterface/context';
import {createNewDataset} from './datasetOperations';
import {DatasetPublishToast} from './DatasetPublishToast';

interface UseDatasetSavingOptions {
  entity: string;
  project: string;
  onSaveComplete?: (datasetRef?: string) => void;
  showToast?: boolean;
}

interface DatasetSavingResult {
  isCreatingDataset: boolean;
  handleSaveDataset: (name: string, rows: any[]) => Promise<void>;
}

/**
 * Hook for saving datasets that encapsulates the common logic used in multiple places
 * like DatasetsPage and EmptyContent
 */
export const useDatasetSaving = ({
  entity,
  project,
  onSaveComplete,
  showToast = true,
}: UseDatasetSavingOptions): DatasetSavingResult => {
  const [isCreatingDataset, setIsCreatingDataset] = React.useState(false);
  const router = useWeaveflowCurrentRouteContext();
  const {useObjCreate, useTableCreate} = useWFHooks();

  // Get the create hooks
  const tableCreate = useTableCreate();
  const objCreate = useObjCreate();

  const handleSaveDataset = React.useCallback(
    async (name: string, rows: any[]) => {
      setIsCreatingDataset(true);
      let datasetRef: undefined | string = undefined;
      try {
        // Create the dataset using the actual API function
        const result = await createNewDataset({
          projectId: `${entity}/${project}`,
          entity,
          project,
          datasetName: name,
          rows,
          tableCreate,
          objCreate,
          router,
        });

        datasetRef = makeRefObject(
          entity,
          project,
          'object',
          result.objectId,
          result.objectDigest,
          undefined
        );

        // Show success message with link to the new dataset
        if (showToast) {
          toast(
            <DatasetPublishToast
              message={'Dataset created successfully!'}
              url={result.url}
            />,
            {
              position: 'top-right',
              autoClose: 5000,
              hideProgressBar: true,
              closeOnClick: true,
              pauseOnHover: true,
            }
          );
        }
      } catch (error: any) {
        console.error('Failed to create dataset:', error);
        toast.error(`Failed to create dataset: ${error.message}`);
      } finally {
        setIsCreatingDataset(false);
        onSaveComplete?.(datasetRef);
      }
    },
    [entity, project, tableCreate, objCreate, router, onSaveComplete, showToast]
  );

  return {
    isCreatingDataset,
    handleSaveDataset,
  };
};
