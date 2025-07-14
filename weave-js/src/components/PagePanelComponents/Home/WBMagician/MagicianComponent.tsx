import {Box, Typography} from '@mui/material';
import React, {FC} from 'react';

import {useMagician} from './Magician';

export const MagicianComponent: FC<{
  projectId: string;
}> = ({projectId}) => {
  const {respond} = useMagician();
  const respondDemo = () => {
    respond({
      projectId,
      modelName: 'gpt-4o',
      input: 'Hello, how are you?',
    });
  };

  return (
    <Box sx={{flex: '0 0 400px'}}>
      <Typography variant="h6">Magician Demo</Typography>
      <button onClick={respondDemo}>Respond</button>
      {/* TODO - make this a slick chat interface wired up to the MagicianContext */}
    </Box>
  );
};
