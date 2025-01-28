import React, {useEffect} from 'react';

import {useDatasetEditContext} from './DatasetEditorContext';
import {EditableDatasetView} from './EditableDatasetView';

export interface DatasetPreviewProps {
  mappedRows: any[];
  datasetObject: any;
  editContextRef: React.MutableRefObject<any>;
}

export const DatasetPreview: React.FC<DatasetPreviewProps> = ({
  mappedRows,
  datasetObject,
  editContextRef,
}) => {
  const editContext = useDatasetEditContext();
  const hasSetRows = React.useRef(false);

  useEffect(() => {
    if (editContext) {
      editContextRef.current = editContext;
    }
  }, [editContext, editContextRef]);

  useEffect(() => {
    if (mappedRows.length > 0 && editContext && !hasSetRows.current) {
      const rowsMap = new Map(mappedRows.map(row => [row.___weave.id, row]));
      editContext.setAddedRows(rowsMap);
      hasSetRows.current = true;
    }
  }, [mappedRows, editContext]);

  useEffect(() => {
    hasSetRows.current = false;
  }, [mappedRows]);

  return <EditableDatasetView datasetObject={datasetObject} isEditing={true} />;
};
