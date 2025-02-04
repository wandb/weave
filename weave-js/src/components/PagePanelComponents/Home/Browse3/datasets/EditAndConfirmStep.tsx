import {Box} from '@mui/material';
import React, {useMemo} from 'react';

import {DatasetPreview} from './DatasetPreview';
import {CallData, FieldMapping, mapCallsToDatasetRows} from './schemaUtils';

export interface EditAndConfirmStepProps {
  selectedCalls: CallData[];
  fieldMappings: FieldMapping[];
  datasetObject: any;
  editContextRef: React.MutableRefObject<any>;
}

export const EditAndConfirmStep: React.FC<EditAndConfirmStepProps> = ({
  selectedCalls,
  fieldMappings,
  datasetObject,
  editContextRef,
}) => {
  const mappedRows = useMemo(() => {
    return mapCallsToDatasetRows(selectedCalls, fieldMappings);
  }, [selectedCalls, fieldMappings]);

  return (
    <Box sx={{height: '100%', width: '100%'}}>
      <DatasetPreview
        mappedRows={mappedRows}
        datasetObject={datasetObject}
        editContextRef={editContextRef}
      />
    </Box>
  );
};
