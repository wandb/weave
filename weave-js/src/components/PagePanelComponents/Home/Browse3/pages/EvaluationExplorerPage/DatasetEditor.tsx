import React, {useMemo} from 'react';

import {CreateDatasetProvider} from '../../datasets/CreateDatasetDrawerContext';
import {
  DatasetObjectVal,
  EditableDatasetView,
} from '../../datasets/EditableDatasetView';
import {useDatasetSaving} from '../../datasets/useDatasetSaving';

export const NewDatasetEditor = ({
  entity,
  project,
}: {
  entity: string;
  project: string;
}) => {
  const {isCreatingDataset, handleSaveDataset} = useDatasetSaving({
    entity,
    project,
    onSaveComplete: () => {
      console.error('TODO: Implement me');
    },
  });
  const emptyDataset: DatasetObjectVal = useMemo(() => {
    return {
      _type: 'Dataset',
      name: null,
      description: null,
      rows: JSON.stringify([]),
      _class_name: 'Dataset',
      _bases: ['Object', 'BaseModel'],
    };
  }, []);

  return (
    <CreateDatasetProvider onPublishDataset={handleSaveDataset}>
      <EditableDatasetView isEditing datasetObject={emptyDataset} />
    </CreateDatasetProvider>
  );
};
