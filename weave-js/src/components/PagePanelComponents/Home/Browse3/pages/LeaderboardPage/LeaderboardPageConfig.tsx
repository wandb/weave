import {
  Alert,
  Box,
  Button,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Typography,
} from '@mui/material';
import React, {useCallback, useMemo, useState} from 'react';

import {useWFHooks} from '../wfReactInterface/context';
import {FilterAndGroupDatasetSpec, FilterAndGroupSourceEvaluationSpec, FilterAndGroupSpec, LeaderboardConfigType} from './LeaderboardConfigType';

export const LeaderboardConfig: React.FC<{
  entity: string;
  project: string;
  config: LeaderboardConfigType;
  onCancel: () => void;
  onPersist: () => void;
  setConfig: (
    updater: (config: LeaderboardConfigType) => LeaderboardConfigType
  ) => void;
}> = ({entity, project, config, setConfig, onPersist, onCancel}) => {
  const handleSave = () => {
    onPersist();
  };

  const handleCancel = () => {
    onCancel();
  };

  const [showAlert, setShowAlert] = useState(true);


  return (
    <Box
      sx={{
        width: '50%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        border: '1px solid #e0e0e0',
      }}>
      <Box
        sx={{
          // flexGrow: 1,
          overflowY: 'auto',
          p: 2,
        }}>
        {showAlert && <TempAlert onClose={() => setShowAlert(false)} />}
        <Typography variant="h5" gutterBottom>
          Leaderboard Configuration
        </Typography>
      </Box>

      <Box sx={{mt: 2, mb: 2, flex: 1, overflowY: 'auto'}}>
        <Typography variant="h6" gutterBottom>
          Configuration Preview
        </Typography>
        <pre
          style={{
            backgroundColor: '#f5f5f5',
            padding: '10px',
            borderRadius: '4px',
            overflowX: 'auto',
            whiteSpace: 'pre-wrap',
            wordWrap: 'break-word',
          }}>
          {JSON.stringify(config, null, 2)}
        </pre>
      </Box>

      {/* Add config builder / editor here */}

      <Box
        sx={{
          display: 'flex',
          justifyContent: 'flex-end',
          height: '51px',
          p: 1,
          borderTop: '1px solid #e0e0e0',
        }}>
        <Button variant="outlined" onClick={handleCancel} sx={{mr: 2}}>
          Cancel
        </Button>
        <Button variant="contained" onClick={handleSave} sx={{mr: 2}}>
          Save
        </Button>
      </Box>
    </Box>
  );
};

const TempAlert: React.FC<{onClose: () => void}> = ({onClose}) => {
  return (
    <Alert severity="info" onClose={onClose}>
      <Typography variant="body1">
        Configuration edtior purely for internal exploration, not for production
        use.
      </Typography>
    </Alert>
  );
};

// These functions are placeholders which I will implement.

const fetchEvaluationNames = async (): Promise<string[]> => {
  // TODO
  return Promise.resolve([])
}

const fetchEvaluationVersionsForName = async (name: string): Promise<string[]> => {
  // TODO
  return Promise.resolve([])
}

const fetchDatasetNamesForSpec = async (spec: FilterAndGroupSpec): Promise<string[]> => {
  // TODO
  return Promise.resolve([])
}

const fetchDatasetVersionsForSpecAndName = async (spec: FilterAndGroupSpec, name: string): Promise<string[]> => {
  // TODO
  return Promise.resolve([])
}

const fetchModelNamesForSpec = async (spec: FilterAndGroupSpec): Promise<string[]> => {
  // TODO
  return Promise.resolve([])
}

const fetchModelVersionsForSpecndName = async (spec: FilterAndGroupSpec, name: string): Promise<string[]> => {
  // TODO
  return Promise.resolve([])
}

const fetchScorerNamesForSpec = async (spec: FilterAndGroupSpec): Promise<string[]> => {
  // TODO
  return Promise.resolve([])
}

const fetchScorerVersionsForSpecAndName = async (spec: FilterAndGroupSpec, name: string): Promise<string[]> => {
  // TODO
  return Promise.resolve([])
}

const fetchMetricPathsForSpec = async (spec: FilterAndGroupSpec): Promise<string[]> => {
    // TODO
    return Promise.resolve([])
}

