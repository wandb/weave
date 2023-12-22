import {useNodeValue} from '@wandb/weave/react';
import React, {FC, useCallback, useMemo} from 'react';
import {useHistory, useParams} from 'react-router-dom';

import {useWeaveflowRouteContext} from '../Browse3/context';
import {callsTableFilter, callsTableNode, callsTableOpCounts} from './callTree';
import {Browse2RootObjectVersionItemParams} from './CommonLib';
import {opDisplayName} from './dataModel';
import {LinkTable} from './LinkTable';

export const Browse2RootObjectVersionUsers: FC<{uri: string}> = ({uri}) => {
  const params = useParams<Browse2RootObjectVersionItemParams>();
  const {baseRouter} = useWeaveflowRouteContext();
  const calledOpCountsNode = useMemo(() => {
    const streamTableRowsNode = callsTableNode({
      entityName: params.entity,
      projectName: params.project,
      streamName: 'stream',
    });
    const filtered = callsTableFilter(streamTableRowsNode, {
      inputUris: [uri],
    });
    return callsTableOpCounts(filtered);
  }, [params.entity, params.project, uri]);
  const calledOpCountsQuery = useNodeValue(calledOpCountsNode);

  const rows = useMemo(() => {
    const calledOpCounts = calledOpCountsQuery.result ?? [];
    return calledOpCounts.map((row: any, i: number) => ({
      id: i,
      _name: row.name,
      name: opDisplayName(row.name),
      count: row.count,
    }));
  }, [calledOpCountsQuery]);
  const history = useHistory();
  const handleRowClick = useCallback(
    (row: any) => {
      history.push(
        `${baseRouter.opPageUrl(row._name)}?inputUri=${encodeURIComponent(uri)}`
      );
    },
    [history, baseRouter, uri]
  );

  return <LinkTable rows={rows} handleRowClick={handleRowClick} />;
};
