import React, {FC, useCallback, useMemo} from 'react';
import {useParams, useHistory} from 'react-router-dom';
import {useNodeValue} from '@wandb/weave/react';
import {callsTableFilter, callsTableNode, callsTableOpCounts} from './callTree';
import {LinkTable} from './LinkTable';
import {Browse2RootObjectVersionItemParams} from './CommonLib';
import {opPageUrl} from './url';
import {opDisplayName} from './dataModel';

export const Browse2RootObjectVersionUsers: FC<{uri: string}> = ({uri}) => {
  const params = useParams<Browse2RootObjectVersionItemParams>();
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
        `${opPageUrl(row._name)}?inputUri=${encodeURIComponent(uri)}`
      );
    },
    [history, uri]
  );

  return <LinkTable rows={rows} handleRowClick={handleRowClick} />;
};
