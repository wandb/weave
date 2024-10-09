import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import {
  Box,
  Button,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Typography,
} from '@mui/material';
import React from 'react';

import {
  useDatasetNames,
  useDatasetVersionsForDatasetName,
} from './leaderboardConfigQuery';
import {LeaderboardConfigType, VersionSpec} from './LeaderboardConfigType';
import {ScoreConfig} from './ScoreConfig';

export const ColumnConfig: React.FC<{
  entity: string;
  project: string;
  column: LeaderboardConfigType['config']['columns'][0];
  onUpdate: (
    updatedColumn: LeaderboardConfigType['config']['columns'][0]
  ) => void;
  onRemove: () => void;
}> = ({entity, project, column, onUpdate, onRemove}) => {
  const datasetNames = useDatasetNames(entity, project);
  const datasetVersions = useDatasetVersionsForDatasetName(column.dataset.name);

  const handleAddScore = () => {
    onUpdate({
      ...column,
      scores: [
        ...column.scores,
        {scorer: {name: '', version: 'latest'}, metrics: []},
      ],
    });
  };

  const handleRemoveScore = (index: number) => {
    onUpdate({
      ...column,
      scores: column.scores.filter((_, i) => i !== index),
    });
  };

  const handleUpdateScore = (
    index: number,
    updatedScore: (typeof column.scores)[0]
  ) => {
    onUpdate({
      ...column,
      scores: column.scores.map((score, i) =>
        i === index ? updatedScore : score
      ),
    });
  };

  return (
    <Box sx={{mb: 2, p: 2, border: '1px solid #ccc', borderRadius: 1}}>
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{mb: 2}}>
        <Typography variant="subtitle1">Column</Typography>
        <IconButton onClick={onRemove} size="small">
          <DeleteIcon />
        </IconButton>
      </Stack>
      <FormControl fullWidth sx={{mb: 2}}>
        <InputLabel>Dataset</InputLabel>
        <Select
          value={column.dataset.name}
          label="Dataset"
          onChange={e =>
            onUpdate({
              ...column,
              dataset: {...column.dataset, name: e.target.value},
            })
          }>
          {datasetNames.map(name => (
            <MenuItem key={name} value={name}>
              {name}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
      <FormControl fullWidth sx={{mb: 2}}>
        <InputLabel>Dataset Version</InputLabel>
        <Select
          value={column.dataset.version}
          label="Dataset Version"
          onChange={e =>
            onUpdate({
              ...column,
              dataset: {
                ...column.dataset,
                version: e.target.value as VersionSpec,
              },
            })
          }>
          <MenuItem value="latest">Latest</MenuItem>
          <MenuItem value="all">All</MenuItem>
          {datasetVersions.map(({version, versionIndex}) => (
            <MenuItem key={version} value={version}>
              Version {versionIndex}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
      {column.scores.map((score, index) => (
        <ScoreConfig
          key={index}
          score={score}
          datasetName={column.dataset.name}
          datasetVersion={column.dataset.version}
          onUpdate={updatedScore => handleUpdateScore(index, updatedScore)}
          onRemove={() => handleRemoveScore(index)}
        />
      ))}
      <Button startIcon={<AddIcon />} onClick={handleAddScore} sx={{mt: 1}}>
        Add Score
      </Button>
    </Box>
  );
};
