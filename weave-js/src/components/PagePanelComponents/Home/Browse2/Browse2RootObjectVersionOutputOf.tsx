import React, {FC, useMemo} from 'react';
import {useParams} from 'react-router-dom';
import {useNodeValue} from '@wandb/weave/react';
import {callsTableFilter, callsTableNode, callsTableOpCounts} from './callTree';
import {Browse2RootObjectVersionItemParams} from './CommonLib';
import {SmallRef, parseRefMaybe} from './SmallRef';
import {Typography} from '@material-ui/core';

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
    <SmallRef objRef={outputOfRunRef} />
  ) : (
    <Typography>-</Typography>
  );
};
