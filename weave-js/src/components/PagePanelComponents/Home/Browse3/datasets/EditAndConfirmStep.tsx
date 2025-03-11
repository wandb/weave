import {Box} from '@mui/material';
import React from 'react';

import {EditableDatasetView} from './EditableDatasetView';
import {CallData, FieldMapping} from './schemaUtils';

export interface EditAndConfirmStepProps {
  selectedCalls: CallData[];
  fieldMappings: FieldMapping[];
  datasetObject: any;
  isNewDataset?: boolean;
}

// Pure component without effects
export const EditAndConfirmStep: React.FC<EditAndConfirmStepProps> = ({
  datasetObject,
}) => {
  return (
    <Box sx={{height: '100%', width: '100%'}}>
      <EditableDatasetView
        datasetObject={datasetObject}
        isEditing={true}
        hideRemoveForAddedRows={true}
        showAddRowButton={false}
      />
    </Box>
  );
};
