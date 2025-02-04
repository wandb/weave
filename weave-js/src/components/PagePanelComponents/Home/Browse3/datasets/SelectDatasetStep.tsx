import {Stack, Typography} from '@mui/material';
import React from 'react';

import {Select} from '../../../../Form/Select';
import {ObjectVersionSchema} from '../pages/wfReactInterface/wfDataModelHooksInterface';

const typographyStyle = {fontFamily: 'Source Sans Pro'};

export interface SelectDatasetStepProps {
  selectedDataset: ObjectVersionSchema | null;
  setSelectedDataset: (dataset: ObjectVersionSchema | null) => void;
  datasets: ObjectVersionSchema[];
  selectedCallsCount: number;
}

export const SelectDatasetStep: React.FC<SelectDatasetStepProps> = ({
  selectedDataset,
  setSelectedDataset,
  datasets,
  selectedCallsCount,
}) => {
  const dropdownOptions = datasets.map(dataset => ({
    label: `${dataset.objectId}:v${dataset.versionIndex}`,
    value: dataset,
  }));

  return (
    <Stack spacing={1} sx={{flex: 1, mt: 2}}>
      <Typography sx={{...typographyStyle, fontWeight: 600}}>
        Dataset selection
      </Typography>
      <Select
        placeholder="Select Dataset"
        value={dropdownOptions.find(opt => opt.value === selectedDataset)}
        options={dropdownOptions}
        onChange={option => setSelectedDataset((option as any)?.value ?? null)}
      />
    </Stack>
  );
};
