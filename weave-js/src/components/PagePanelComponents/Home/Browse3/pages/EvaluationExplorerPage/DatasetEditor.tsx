import {Box} from '@mui/material';
import React, {useCallback, useEffect, useRef} from 'react';

import {DatasetFilePicker} from '../../datasets/CreateDatasetDrawer';
import {
  CreateDatasetProvider,
  useCreateDatasetContext,
} from '../../datasets/CreateDatasetDrawerContext';
import {EditableDatasetView} from '../../datasets/EditableDatasetView';
import {SUPPORTED_FILE_EXTENSIONS} from '../../datasets/fileFormats';
import {useDatasetSaving} from '../../datasets/useDatasetSaving';

const dummyRow = {
  user_input: 'Hello, how are you?',
  expected_output: "I'm good, thank you!",
};

export const NewDatasetEditor = ({
  entity,
  project,
  useFilePicker = false,
}: {
  entity: string;
  project: string;
  useFilePicker?: boolean;
}) => {
  const {handleSaveDataset} = useDatasetSaving({
    entity,
    project,
    onSaveComplete: () => {
      console.error('TODO: Implement me');
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

  return (
    <EditableDatasetView
      datasetObject={parsedData}
      isEditing={true}
      hideRemoveForAddedRows={false}
      showAddRowButton={true}
      hideIdColumn={true}
      disableNewRowHighlight={true}
      isNewDataset={true}
    />
  );
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

  return (
    <EditableDatasetView
      datasetObject={parsedData}
      isEditing={true}
      hideRemoveForAddedRows={false}
      showAddRowButton={true}
      hideIdColumn={true}
      disableNewRowHighlight={true}
      isNewDataset={true}
    />
  );
};
