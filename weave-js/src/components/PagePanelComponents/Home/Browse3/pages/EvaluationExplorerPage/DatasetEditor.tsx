import React, {useEffect} from 'react';

import {
  CreateDatasetProvider,
  useCreateDatasetContext,
} from '../../datasets/CreateDatasetDrawerContext';
import {EditableDatasetView} from '../../datasets/EditableDatasetView';
import {useDatasetSaving} from '../../datasets/useDatasetSaving';

const dummyRow = {
  user_input: 'Hello, how are you?',
  expected_output: "I'm good, thank you!",
};

export const NewEmptyDatasetEditor = ({
  entity,
  project,
}: {
  entity: string;
  project: string;
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
      <NewEmptyDatasetEditorInner />
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
