import DeleteIcon from '@mui/icons-material/Delete';
import {
  Box,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Typography,
} from '@mui/material';
import React from 'react';

import {LeaderboardConfigType, VersionSpec} from './LeaderboardConfigType';
import {
  useModelNames,
  useModelVersionsForModelName,
} from './useCurrentLeaderboardConfig';

export const ModelConfig: React.FC<{
  model: LeaderboardConfigType['config']['models'][0];
  onUpdate: (
    updatedModel: LeaderboardConfigType['config']['models'][0]
  ) => void;
  onRemove: () => void;
}> = ({model, onUpdate, onRemove}) => {
  const modelNames = useModelNames();
  const modelVersions = useModelVersionsForModelName(model.name);

  return (
    <Box sx={{mb: 2, p: 2, border: '1px solid #ccc', borderRadius: 1}}>
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{mb: 2}}>
        <Typography variant="subtitle1">Model</Typography>
        <IconButton onClick={onRemove} size="small">
          <DeleteIcon />
        </IconButton>
      </Stack>
      <FormControl fullWidth sx={{mb: 2}}>
        <InputLabel>Model Name</InputLabel>
        <Select
          value={model.name}
          label="Model Name"
          onChange={e => onUpdate({...model, name: e.target.value})}>
          {modelNames.map(name => (
            <MenuItem key={name} value={name}>
              {name}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
      <FormControl fullWidth>
        <InputLabel>Model Version</InputLabel>
        <Select
          value={model.version}
          label="Model Version"
          onChange={e =>
            onUpdate({...model, version: e.target.value as VersionSpec})
          }>
          <MenuItem value="latest">Latest</MenuItem>
          <MenuItem value="all">All</MenuItem>
          {modelVersions.map(({version, versionIndex}) => (
            <MenuItem key={version} value={version}>
              Version {versionIndex}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
    </Box>
  );
};
