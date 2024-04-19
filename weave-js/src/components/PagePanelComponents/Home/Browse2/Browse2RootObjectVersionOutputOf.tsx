import Typography from '@mui/material/Typography';
import {useNodeValue} from '@wandb/weave/react';
import React, {FC, useMemo} from 'react';
import {useParams} from 'react-router-dom';

import {callsTableFilter, callsTableNode, callsTableOpCounts} from './callTree';
import {Browse2RootObjectVersionItemParams} from './CommonLib';
import {parseRefMaybe, SmallRef} from './SmallRef';

export const Browse2RootObjectVersionOutputOf: FC<{uri: string}> = ({uri}) => {
  const params = useParams<Browse2RootObjectVersionItemParams>();
  const calledOpCountsNode = useMemo(() => {
    const streamTableRowsNode = callsTableNode({
      entityName: params.entity,
      projectName: params.project,
      streamName: 'stream',
    });
    const filtered = callsTableFilter(streamTableRowsNode, {
      outputUris: [uri],
    });
    return callsTableOpCounts(filtered);
  }, [params.entity, params.project, uri]);
  const calledOpCountsQuery = useNodeValue(calledOpCountsNode);

  const outputOfRunRef = useMemo(() => {
    const runName = (calledOpCountsQuery.result ?? [])[0]?.name;
    const ref = parseRefMaybe(runName);
    return ref;
  }, [calledOpCountsQuery]);

  return outputOfRunRef != null ? (
    <SmallRef objRef={outputOfRunRef} wfTable="OpVersion" />
  ) : (
    <Typography>-</Typography>
  );
};
