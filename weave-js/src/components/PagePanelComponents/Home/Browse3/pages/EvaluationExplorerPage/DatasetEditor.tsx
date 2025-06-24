import {Box} from '@mui/material';
import {Button} from '@wandb/weave/components';
import React, {useCallback, useEffect} from 'react';

import {DatasetFilePicker} from '../../datasets/CreateDatasetDrawer';
import {
  CREATE_DATASET_ACTIONS,
  CreateDatasetProvider,
  useCreateDatasetContext,
} from '../../datasets/CreateDatasetDrawerContext';
import {DatasetEditProvider} from '../../datasets/DatasetEditorContext';
import {
  DatasetObjectVal,
  EditableDatasetView,
  EditableDatasetViewProps,
} from '../../datasets/EditableDatasetView';
import {useDatasetSaving} from '../../datasets/useDatasetSaving';
import {HEADER_HEIGHT_PX} from './constants';
import {clientBound, hookify} from './hooks';
import {getObjByRef} from './query';

const dummyRow = {
  user_input: 'Hello, how are you?',
  expected_output: "I'm good, thank you!",
};

export const NewDatasetEditor = ({
  entity,
  project,
  useFilePicker = false,
  onSaveComplete,
}: {
  entity: string;
  project: string;
  useFilePicker?: boolean;
  onSaveComplete?: (datasetRef?: string) => void;
}) => {
  const {handleSaveDataset} = useDatasetSaving({
    entity,
    project,
    onSaveComplete: datasetRef => {
      onSaveComplete?.(datasetRef);
    },
  });
  return (
    <CreateDatasetProvider onPublishDataset={handleSaveDataset}>
      {useFilePicker ? (
        <NewFileDatasetEditorInner />
      ) : (
        <NewEmptyDatasetEditorInner />
      )}
    </CreateDatasetProvider>
  );
};

const NewEmptyDatasetEditorInner = () => {
  const {state, initializeDataset} = useCreateDatasetContext();
  const {parsedData} = state;

  useEffect(() => {
    if (!parsedData) {
      initializeDataset([dummyRow]);
    }
  }, [initializeDataset, parsedData]);

  if (!parsedData) {
    return null;
  }

  return <EditableDatasetViewInner datasetObject={parsedData} />;
};

const NewFileDatasetEditorInner = () => {
  const {state, parseFile} = useCreateDatasetContext();
  const {parsedData} = state;

  if (!parsedData) {
    return (
      <Box sx={{p: 2}}>
        <DatasetFilePicker handleFileSelect={parseFile} />
      </Box>
    );
  }

  return <EditableDatasetViewInner datasetObject={parsedData} />;
};

const EditableDatasetViewInner: React.FC<
  Pick<EditableDatasetViewProps, 'datasetObject'>
> = props => {
  const {handlePublishDataset, dispatch} = useCreateDatasetContext();
  useEffect(() => {
    // TODO: Get the name from the user
    dispatch({
      type: CREATE_DATASET_ACTIONS.SET_DATASET_NAME,
      payload: 'eval-dataset',
    });

    // TODO: Validate the name
    // const validationResult = validateDatasetName(value);
  }, [dispatch]);
  const onSave = useCallback(() => {
    handlePublishDataset();
  }, [handlePublishDataset]);
  return (
    <EditableDatasetView
      {...props}
      isEditing={true}
      hideRemoveForAddedRows={false}
      showAddRowButton={true}
      hideIdColumn={true}
      disableNewRowHighlight={true}
      isNewDataset={true}
      footerHeight={HEADER_HEIGHT_PX}
      extraFooterContent={
        <Button icon="save" variant="primary" onClick={onSave}>
          Save Changes
        </Button>
      }
    />
  );
};

const useObjByRef = clientBound(hookify(getObjByRef));

export const ExistingDatasetEditor: React.FC<{datasetRef: string}> = ({
  datasetRef,
}) => {
  const datasetObject = useObjByRef(datasetRef);
  console.log(datasetObject);
  if (datasetObject.loading || datasetObject.error || !datasetObject.data) {
    // TODO
    return null;
  }
  return (
    <DatasetEditProvider>
      <EditableDatasetView
        // TODO: unsafe cast
        datasetObject={datasetObject.data.val as DatasetObjectVal}
        isEditing={true}
        hideRemoveForAddedRows={false}
        showAddRowButton={true}
        hideIdColumn={true}
        footerHeight={HEADER_HEIGHT_PX}
        extraFooterContent={
          <Button icon="save" variant="primary" onClick={() => {}}>
            Save Changes
          </Button>
        }
      />
    </DatasetEditProvider>
  );
};
