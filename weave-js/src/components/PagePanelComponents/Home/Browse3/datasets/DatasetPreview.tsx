import React, {useEffect} from 'react';

import {useDatasetEditContext} from './DatasetEditorContext';
import {EditableDatasetView} from './EditableDatasetView';

export interface DatasetPreviewProps {
  mappedRows: Array<{___weave: {id: string; isNew: boolean}}>;
  datasetObject: any;
}

export const DatasetPreview: React.FC<DatasetPreviewProps> = ({
  mappedRows,
  datasetObject,
}) => {
  const {setAddedRows, addedRows} = useDatasetEditContext();

  // Only set rows if they don't exist or if they're different
  useEffect(() => {
    const rowsMap = new Map(
      mappedRows.map(row => [
        row.___weave.id,
        {...row, ___weave: {...row.___weave, serverValue: row}},
      ])
    );

    // Check if we need to initialize
    const needsInitialization = addedRows.size === 0;

    if (needsInitialization) {
      setAddedRows(rowsMap);
    }
  }, [mappedRows, setAddedRows, addedRows]);

  return (
    <EditableDatasetView
      datasetObject={datasetObject}
      isEditing={true}
      hideRemoveForAddedRows={true}
    />
  );
};
