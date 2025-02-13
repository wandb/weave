import {Box, Typography} from '@mui/material';
import React from 'react';

import {PlaygroundPage} from '../PlaygroundPage/PlaygroundPage';

interface AgentdomePageProps {
  entity: string;
  project: string;
}

export const AgentdomePage: React.FC<AgentdomePageProps> = ({
  entity,
  project,
}) => {
  return (
    <>
      <PlaygroundPage entity={entity} project={project} agentdome />
    </>
  );
};
