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
  useScorerNamesForDataset,
  useScorerVersionsForDatasetAndScorer,
} from './leaderboardConfigQuery';
import {LeaderboardConfigType, VersionSpec} from './LeaderboardConfigType';
import {MetricConfig} from './MetricConfig';

export const ScoreConfig: React.FC<{
  entity: string;
  project: string;
  score: LeaderboardConfigType['config']['columns'][0]['scores'][0];
  datasetName: string;
  datasetVersion: string;
  onUpdate: (
    updatedScore: LeaderboardConfigType['config']['columns'][0]['scores'][0]
  ) => void;
  onRemove: () => void;
}> = ({ entity, project, score, datasetName, datasetVersion, onUpdate, onRemove}) => {
  const scorerNames = useScorerNamesForDataset(
    entity,
    project,
    datasetName,
    datasetVersion
  );
  const scorerVersions = useScorerVersionsForDatasetAndScorer(
    datasetName,
    datasetVersion,
    score.scorer.name
  );

  const handleAddMetric = () => {
    onUpdate({
      ...score,
      metrics: [
        ...score.metrics,
        {displayName: '', path: [], minTrials: undefined, maxTrials: undefined},
      ],
    });
  };

  const handleRemoveMetric = (index: number) => {
    onUpdate({
      ...score,
      metrics: score.metrics.filter((_, i) => i !== index),
    });
  };

  const handleUpdateMetric = (
    index: number,
    updatedMetric: (typeof score.metrics)[0]
  ) => {
    onUpdate({
      ...score,
      metrics: score.metrics.map((metric, i) =>
        i === index ? updatedMetric : metric
      ),
    });
  };

  return (
    <Box sx={{mb: 2, p: 2, border: '1px solid #eee', borderRadius: 1}}>
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{mb: 2}}>
        <Typography variant="subtitle2">Score</Typography>
        <IconButton onClick={onRemove} size="small">
          <DeleteIcon />
        </IconButton>
      </Stack>
      <FormControl fullWidth sx={{mb: 2}}>
        <InputLabel>Scorer</InputLabel>
        <Select
          value={score.scorer.name}
          label="Scorer"
          onChange={e =>
            onUpdate({
              ...score,
              scorer: {...score.scorer, name: e.target.value},
            })
          }>
          {scorerNames.map(name => (
            <MenuItem key={name} value={name}>
              {name}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
      <FormControl fullWidth sx={{mb: 2}}>
        <InputLabel>Scorer Version</InputLabel>
        <Select
          value={score.scorer.version}
          label="Scorer Version"
          onChange={e =>
            onUpdate({
              ...score,
              scorer: {...score.scorer, version: e.target.value as VersionSpec},
            })
          }>
          <MenuItem value="latest">Latest</MenuItem>
          <MenuItem value="all">All</MenuItem>
          {scorerVersions.map(({version, versionIndex}) => (
            <MenuItem key={version} value={version}>
              Version {versionIndex}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
      {score.metrics.map((metric, index) => (
        <MetricConfig
          key={index}
          metric={metric}
          datasetName={datasetName}
          datasetVersion={datasetVersion}
          scorerName={score.scorer.name}
          scorerVersion={score.scorer.version}
          onUpdate={updatedMetric => handleUpdateMetric(index, updatedMetric)}
          onRemove={() => handleRemoveMetric(index)}
        />
      ))}
      <Button startIcon={<AddIcon />} onClick={handleAddMetric} sx={{mt: 1}}>
        Add Metric
      </Button>
    </Box>
  );
};
