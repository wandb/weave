import {Box} from '@mui/material';
import React, {useMemo} from 'react';

import {DatasetPreview} from './DatasetPreview';
import {CallData, FieldMapping, mapCallsToDatasetRows} from './schemaUtils';

export interface EditAndConfirmStepProps {
  selectedCalls: CallData[];
  fieldMappings: FieldMapping[];
  datasetObject: any;
  isNewDataset?: boolean;
}

interface WeaveRow {
  ___weave: {id: string; isNew: boolean};
  [key: string]: any;
}

export const EditAndConfirmStep: React.FC<EditAndConfirmStepProps> = ({
  selectedCalls,
  fieldMappings,
  datasetObject,
  isNewDataset,
}) => {
  const mappedRows = useMemo(() => {
    const rows = mapCallsToDatasetRows(selectedCalls, fieldMappings);

    // For new datasets, only include the fields that were mapped
    if (isNewDataset) {
      const targetFields = new Set(fieldMappings.map(m => m.targetField));
      return rows.map(row => {
        const {___weave, ...rest} = row;
        const filteredData = Object.fromEntries(
          Object.entries(rest).filter(([key]) => targetFields.has(key))
        );
        return {
          ___weave,
          ...filteredData,
        } as WeaveRow;
      });
    }

    return rows;
  }, [selectedCalls, fieldMappings, isNewDataset]);

  return (
    <Box sx={{height: '100%', width: '100%'}}>
      <DatasetPreview mappedRows={mappedRows} datasetObject={datasetObject} />
    </Box>
  );
};
