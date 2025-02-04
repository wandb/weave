import {Box} from '@mui/material';
import {get} from 'lodash';
import React, {useMemo} from 'react';
import {v4 as uuidv4} from 'uuid';

import {DatasetPreview} from './DatasetPreview';
import {CallData, FieldMapping} from './schemaUtils';

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
    return selectedCalls.map(call => {
      const row: Record<string, any> = {};

      fieldMappings.forEach(mapping => {
        const inputs = call.val.inputs || {};
        const output = call.val.output;

        let sourceValue: any;
        if (mapping.sourceField === 'output' && typeof output === 'string') {
          sourceValue = output;
        } else {
          sourceValue = get({inputs, output}, mapping.sourceField);
        }

        if (sourceValue !== undefined) {
          row[mapping.targetField] = sourceValue;
        }
      });

      return {
        ___weave: {
          id: `new-${uuidv4()}`,
          isNew: true,
        },
        ...row,
      };
    });
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
