import {Alert, Box, Button, Typography} from '@mui/material';
import React, {useState} from 'react';

import {LeaderboardConfigType} from './LeaderboardConfigType';

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
          flexGrow: 1,
          overflowY: 'auto',
          p: 2,
        }}>
        {showAlert && <TempAlert onClose={() => setShowAlert(false)} />}
        <Typography variant="h5" gutterBottom>
          Leaderboard Configuration
        </Typography>
      </Box>

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
