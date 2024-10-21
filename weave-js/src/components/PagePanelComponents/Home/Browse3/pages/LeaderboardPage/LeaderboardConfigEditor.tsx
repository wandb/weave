import {Box} from '@material-ui/core';
import React from 'react';

import {PythonLeaderboardObjectVal} from '../../views/Leaderboard/types/leaderboardConfigType';

export const LeaderboardConfigEditor: React.FC<{
  leaderboardVal: PythonLeaderboardObjectVal;
  saving: boolean;
  setWorkingCopy: (leaderboardVal: PythonLeaderboardObjectVal) => void;
  discardChanges: () => void;
  commitChanges: () => void;
}> = ({leaderboardVal, setWorkingCopy, discardChanges, commitChanges}) => {
  return <Box>Config Editor</Box>;
};
