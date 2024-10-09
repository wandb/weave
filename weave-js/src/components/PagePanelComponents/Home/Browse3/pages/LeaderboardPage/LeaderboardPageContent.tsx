import {Alert,Box, Typography} from '@mui/material';
import React from 'react';

import {useCurrentLeaderboardConfig} from './leaderboardConfigQuery';
import {LeaderboardConfig} from './LeaderboardPageConfig';

export const LeaderboardPageContent: React.FC = () => {
  const currentConfig = useCurrentLeaderboardConfig();

  const handleConfigUpdate = (newConfig: typeof currentConfig) => {
    // TODO: Implement this
    console.log('New config:', newConfig);
  };

  return (
    <Box sx={{width: '100%', p: 2}}>
      <Alert severity="info" sx={{mb: 3}}>
        <Typography variant="body1">
          This is an unlisted beta page. Features may be incomplete or subject to change.
        </Typography>
      </Alert>
      <LeaderboardConfig
        currentConfig={currentConfig}
        onConfigUpdate={handleConfigUpdate}
      />
    </Box>
  );
};