import React, {FC, useMemo} from 'react';
import {useNodeValue} from '@wandb/weave/react';
import {
  CallFilter,
  StreamId,
  callsTableFilter,
  callsTableNode,
  callsTableSelect,
} from './callTree';
import {Paper} from './CommonLib';
import {Typography} from '@mui/material';
import {FilterList} from '@mui/icons-material';
import {RunsTable} from './RunsTable';

export const Browse2Calls: FC<{
  streamId: StreamId;
  filters: CallFilter;
}> = ({streamId, filters}) => {
  const selected = useMemo(() => {
    const streamTableRowsNode = callsTableNode(streamId);
    const filtered = callsTableFilter(streamTableRowsNode, filters);
    return callsTableSelect(filtered);
  }, [filters, streamId]);

  const selectedQuery = useNodeValue(selected);

  const selectedData = selectedQuery.result ?? [];

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
      <RunsTable spans={selectedData} />
    </Paper>
  );
};
