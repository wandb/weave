import {FilterList} from '@mui/icons-material';
import {Typography} from '@mui/material';
import React, {FC} from 'react';

import {CallFilter, StreamId} from './callTree';
import {useRunsWithFeedback} from './callTreeHooks';
import {Paper} from './CommonLib';
import {RunsTable} from './RunsTable';

export const Browse2Calls: FC<{
  streamId: StreamId;
  filters: CallFilter;
}> = ({streamId, filters}) => {
  const selectedQuery = useRunsWithFeedback(streamId, filters);

  return (
    <Paper>
      <Typography variant="h6" gutterBottom>
        Runs
      </Typography>
      {filters.inputUris != null && (
        <div
          style={{
            display: 'flex',
            whiteSpace: 'nowrap',
            textOverflow: 'ellipsis',
            overflow: 'hidden',
          }}>
          <FilterList />
          <i>Showing runs where input is one of: </i>
          {filters.inputUris.map((inputUri, i) => (
            <div key={i}>{inputUri}</div>
          ))}
        </div>
      )}
      <RunsTable loading={selectedQuery.loading} spans={selectedQuery.result} />
    </Paper>
  );
};
