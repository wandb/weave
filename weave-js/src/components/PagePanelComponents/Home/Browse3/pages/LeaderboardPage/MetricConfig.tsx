import DeleteIcon from '@mui/icons-material/Delete';
import {
  Box,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import React from 'react';

import {Direction, LeaderboardConfigType} from './LeaderboardConfigType';
import {useMetricPathsForDatasetAndScorer} from './useCurrentLeaderboardConfig';

export const MetricConfig: React.FC<{
  metric: LeaderboardConfigType['config']['columns'][0]['scores'][0]['metrics'][0];
  datasetName: string;
  datasetVersion: string;
  scorerName: string;
  scorerVersion: string;
  onUpdate: (
    updatedMetric: LeaderboardConfigType['config']['columns'][0]['scores'][0]['metrics'][0]
  ) => void;
  onRemove: () => void;
}> = ({
  metric,
  datasetName,
  datasetVersion,
  scorerName,
  scorerVersion,
  onUpdate,
  onRemove,
}) => {
  const metricPaths = useMetricPathsForDatasetAndScorer(
    datasetName,
    datasetVersion,
    scorerName,
    scorerVersion
  );

  return (
    <Box sx={{mb: 2, p: 2, border: '1px solid #f5f5f5', borderRadius: 1}}>
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{mb: 2}}>
        <Typography variant="subtitle2">Metric</Typography>
        <IconButton onClick={onRemove} size="small">
          <DeleteIcon />
        </IconButton>
      </Stack>
      <TextField
        fullWidth
        label="Display Name"
        value={metric.displayName}
        onChange={e => onUpdate({...metric, displayName: e.target.value})}
        sx={{mb: 2}}
      />
      <FormControl fullWidth sx={{mb: 2}}>
        <InputLabel>Metric Path</InputLabel>
        <Select
          value={metric.path.join('.')}
          label="Metric Path"
          onChange={e =>
            onUpdate({...metric, path: e.target.value.split('.')})
          }>
          {metricPaths.map(path => (
            <MenuItem key={path} value={path}>
              {path}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
      <TextField
        fullWidth
        label="Min Trials"
        type="number"
        value={metric.minTrials || ''}
        onChange={e =>
          onUpdate({
            ...metric,
            minTrials: parseInt(e.target.value, 10) || undefined,
          })
        }
        sx={{mb: 2}}
      />
      <TextField
        fullWidth
        label="Max Trials"
        type="number"
        value={metric.maxTrials || ''}
        onChange={e =>
          onUpdate({
            ...metric,
            maxTrials: parseInt(e.target.value, 10) || undefined,
          })
        }
        sx={{mb: 2}}
      />
      <FormControl fullWidth sx={{mb: 2}}>
        <InputLabel>Sort Direction</InputLabel>
        <Select
          value={metric.sort?.direction || ''}
          label="Sort Direction"
          onChange={e => {
            const direction = e.target.value as Direction | 'desc';
            onUpdate({
              ...metric,
              sort: direction
                ? {...(metric.sort || {precedence: 0}), direction}
                : undefined,
            });
          }}>
          <MenuItem value="">No sort</MenuItem>
          <MenuItem value="asc">Ascending</MenuItem>
          <MenuItem value="desc">Descending</MenuItem>
        </Select>
      </FormControl>
      {metric.sort && (
        <TextField
          fullWidth
          label="Sort Precedence"
          type="number"
          value={metric.sort.precedence}
          onChange={e =>
            onUpdate({
              ...metric,
              sort: {
                ...metric.sort!,
                precedence: parseInt(e.target.value, 10) || 0,
              },
            })
          }
        />
      )}
    </Box>
  );
};
