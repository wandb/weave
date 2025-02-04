import {Box, Stack, Typography} from '@mui/material';
import React, {useMemo, useState} from 'react';

import {Checkbox} from '../../../../Checkbox';
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
  const [showLatestOnly, setShowLatestOnly] = useState(true);

  const filteredDatasets = useMemo(() => {
    if (!showLatestOnly) {
      return datasets;
    }

    // Group datasets by objectId and find the latest version for each
    const latestVersions = new Map<string, ObjectVersionSchema>();
    datasets.forEach(dataset => {
      const existing = latestVersions.get(dataset.objectId);
      if (!existing || dataset.versionIndex > existing.versionIndex) {
        latestVersions.set(dataset.objectId, dataset);
      }
    });
    return Array.from(latestVersions.values());
  }, [datasets, showLatestOnly]);

  const dropdownOptions = filteredDatasets.map(dataset => ({
    label: `${dataset.objectId}:v${dataset.versionIndex}`,
    value: dataset,
  }));

  return (
    <Stack spacing={1} sx={{flex: 1, mt: 2}}>
      <div>
        <Typography sx={{...typographyStyle, fontWeight: 600}}>
          Dataset selection
        </Typography>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            cursor: 'pointer',
          }}>
          <Checkbox
            checked={showLatestOnly}
            onCheckedChange={checked => setShowLatestOnly(checked === true)}
            size="small"
          />
          <Typography
            onClick={() => setShowLatestOnly(!showLatestOnly)}
            sx={{...typographyStyle, userSelect: 'none', cursor: 'pointer'}}>
            Show latest versions only
          </Typography>
        </Box>
      </div>
      <Select
        placeholder="Select Dataset"
        value={dropdownOptions.find(opt => opt.value === selectedDataset)}
        options={dropdownOptions}
        onChange={option => setSelectedDataset((option as any)?.value ?? null)}
      />
    </Stack>
  );
};
