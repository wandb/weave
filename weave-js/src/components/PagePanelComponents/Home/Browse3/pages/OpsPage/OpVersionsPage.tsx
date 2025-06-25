import {
  GridColDef,
  GridColumnGroupingModel,
  GridRowSelectionModel,
  GridRowsProp,
} from '@mui/x-data-grid-pro';
import {UserLink} from '@wandb/weave/components/UserLink';
import React, {useEffect, useMemo, useState} from 'react';

import {TEAL_600} from '../../../../../../common/css/color.styles';
import {ErrorPanel} from '../../../../../ErrorPanel';
import {Loading} from '../../../../../Loading';
import {LoadingDots} from '../../../../../LoadingDots';
import {Timestamp} from '../../../../../Timestamp';
import {StyledDataGrid} from '../../StyledDataGrid';
import {basicField} from '../common/DataTable';
import {Empty} from '../common/Empty';
import {EMPTY_PROPS_OPERATIONS} from '../common/EmptyContent';
import {CallsLink, OpVersionLink, OpVersionsLink} from '../common/Links';
import {opNiceName} from '../common/opNiceName';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {useControllableState, useURLSearchParamsDict} from '../util';
import {useWFHooks} from '../wfReactInterface/context';
import {opVersionKeyToRefUri} from '../wfReactInterface/utilities';
import {OpVersionSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {WFHighLevelOpVersionFilter} from './opsPageTypes';

// Cache for storing call stats and peer versions query results
type QueryCache = {
  callStats: Map<string, number>;
  peerVersions: Map<string, {count: number; isLimited: boolean}>;
};

export const OpVersionsPage: React.FC<{
  entity: string;
  project: string;
  initialFilter?: WFHighLevelOpVersionFilter;
  // Setting this will make the component a controlled component. The parent
  // is responsible for updating the filter.
  onFilterUpdate?: (filter: WFHighLevelOpVersionFilter) => void;
}> = props => {
  const [filter, setFilter] = useControllableState(
    props.initialFilter ?? {},
    props.onFilterUpdate
  );

  const title = useMemo(() => {
    if (filter.opName) {
      return 'Implementations of ' + filter.opName;
    }
    return 'All Operations';
  }, [filter.opName]);

  return (
    <SimplePageLayout
      title={title}
      hideTabsIfSingle
      tabs={[
        {
          label: '',
          content: (
            <FilterableOpVersionsTable
              {...props}
              initialFilter={filter}
              onFilterUpdate={setFilter}
            />
          ),
        },
      ]}
    />
  );
};

export const FilterableOpVersionsTable: React.FC<{
  entity: string;
  project: string;
  frozenFilter?: WFHighLevelOpVersionFilter;
  initialFilter?: WFHighLevelOpVersionFilter;
  // Setting this will make the component a controlled component. The parent
  // is responsible for updating the filter.
  onFilterUpdate?: (filter: WFHighLevelOpVersionFilter) => void;
}> = props => {
  const {useOpVersions} = useWFHooks();
  const effectiveFilter = useMemo(() => {
    return {...props.initialFilter, ...props.frozenFilter};
  }, [props.initialFilter, props.frozenFilter]);

  const effectivelyLatestOnly = !effectiveFilter.opName;

  const filteredOpVersions = useOpVersions({
    entity: props.entity,
    project: props.project,
    filter: {
      opIds: effectiveFilter.opName ? [effectiveFilter.opName] : undefined,
      latestOnly: effectivelyLatestOnly,
    },
    metadataOnly: true,
  });

  const rows: GridRowsProp = useMemo(() => {
    return (filteredOpVersions.result ?? []).map((ov, i) => {
      return {
        ...ov,
        id: opVersionKeyToRefUri(ov),
        op: `${opNiceName(ov.opId)}:v${ov.versionIndex}`,
        obj: ov,
      };
    });
  }, [filteredOpVersions.result]);

  // cache results in the table, so scrolling doesn't cause re-query
  const queryCache = useMemo(
    (): QueryCache => ({
      callStats: new Map<string, number>(),
      peerVersions: new Map<string, {count: number; isLimited: boolean}>(),
    }),
    []
  );

  // only show user column if there are any columns with a user id
  const showUserColumn = rows.some(row => row.obj.userId != null);

  const columns: GridColDef[] = [
    basicField('op', 'Op', {
      hideable: false,
      valueGetter: (unused: any, row: any) => {
        return row.obj.opId;
      },
      renderCell: cellParams => {
        // Icon to indicate navigation to the object version
        const obj: OpVersionSchema = cellParams.row.obj;
        return (
          <OpVersionLink
            entityName={obj.entity}
            projectName={obj.project}
            opName={obj.opId}
            version={obj.versionHash}
            versionIndex={obj.versionIndex}
            fullWidth={true}
            color={TEAL_600}
          />
        );
      },
    }),

    basicField('calls', 'Calls', {
      width: 100,
      sortable: false,
      filterable: false,
      renderCell: cellParams => {
        const obj: OpVersionSchema = cellParams.row.obj;
        return <OpCallsLink obj={obj} queryCache={queryCache} />;
      },
    }),

    ...(showUserColumn
      ? [
          basicField('userId', 'User', {
            width: 150,
            filterable: false,
            sortable: false,
            valueGetter: (unused: any, row: any) => {
              return row.obj.userId;
            },
            renderCell: (params: any) => {
              const userId = params.value;
              if (userId == null) {
                return <div></div>;
              }
              return <UserLink userId={userId} includeName />;
            },
          }),
        ]
      : []),

    basicField('createdAtMs', 'Last updated', {
      width: 130,
      renderCell: cellParams => {
        const createdAtMs = cellParams.value;
        return <Timestamp value={createdAtMs / 1000} format="relative" />;
      },
    }),

    ...(effectivelyLatestOnly
      ? [
          basicField('peerVersions', 'Versions', {
            width: 100,
            sortable: false,
            filterable: false,
            renderCell: cellParams => {
              const obj: OpVersionSchema = cellParams.row.obj;
              return <PeerVersionsLink obj={obj} queryCache={queryCache} />;
            },
          }),
        ]
      : []),
  ];
  const columnGroupingModel: GridColumnGroupingModel = [];

  // Highlight table row if it matches peek drawer.
  const query = useURLSearchParamsDict();
  const {peekPath} = query;
  const peekId = peekPath ? peekPath.split('/').pop() : null;
  const rowIds = useMemo(() => {
    return rows.map(row => row.id);
  }, [rows]);
  const [rowSelectionModel, setRowSelectionModel] =
    useState<GridRowSelectionModel>([]);
  useEffect(() => {
    if (rowIds.length === 0) {
      // Data may have not loaded
      return;
    }
    if (peekId == null) {
      // No peek drawer, clear any selection
      setRowSelectionModel([]);
    } else {
      // If peek drawer matches a row, select it.
      // If not, don't modify selection.
      if (rowIds.includes(peekId)) {
        setRowSelectionModel([peekId]);
      }
    }
  }, [rowIds, peekId]);

  if (filteredOpVersions.loading) {
    return <Loading centered />;
  }
  if (filteredOpVersions.error) {
    return <ErrorPanel />;
  }

  // TODO: Only show the empty state if unfiltered
  const opVersions = filteredOpVersions.result ?? [];
  const isEmpty = opVersions.length === 0;
  if (isEmpty) {
    return <Empty {...EMPTY_PROPS_OPERATIONS} />;
  }

  return (
    <StyledDataGrid
      // Start Column Menu
      // ColumnMenu is only needed when we have other actions
      // such as filtering.
      disableColumnMenu={true}
      // We don't have enough columns to justify filtering
      disableColumnFilter={true}
      disableMultipleColumnsFiltering={true}
      // ColumnPinning seems to be required in DataGridPro, else it crashes.
      disableColumnPinning={false}
      // We don't have enough columns to justify re-ordering
      disableColumnReorder={true}
      // The columns are fairly simple, so we don't need to resize them.
      disableColumnResize={false}
      // We don't have enough columns to justify hiding some of them.
      disableColumnSelector={true}
      // We don't have enough columns to justify sorting by multiple columns.
      disableMultipleColumnsSorting={true}
      // End Column Menu
      rows={rows}
      initialState={{
        sorting: {
          sortModel: [{field: 'createdAtMs', sort: 'desc'}],
        },
      }}
      columnHeaderHeight={40}
      rowHeight={38}
      columns={columns}
      disableRowSelectionOnClick
      rowSelectionModel={rowSelectionModel}
      columnGroupingModel={columnGroupingModel}
    />
  );
};

const PeerVersionsLink: React.FC<{
  obj: OpVersionSchema;
  queryCache: QueryCache;
}> = ({obj, queryCache}) => {
  const {useOpVersions} = useWFHooks();

  // Create a cache key for this specific op
  const cacheKey = `${obj.entity}/${obj.project}/${obj.opId}`;

  // Check if we already have the result cached
  const cachedResult = queryCache.peerVersions.get(cacheKey);
  const shouldFetch = cachedResult === undefined;

  // Here, we really just want to know the count - and it should be calculated
  // by the server, not by the client. This is a performance optimization. In
  // the meantime we will just fetch the first 100 versions and display 99+ if
  // there are at least 100. Someone can come back and add `count` to the 3
  // query APIs which will make this faster.
  const ops = useOpVersions({
    entity: obj.entity,
    project: obj.project,
    filter: {
      opIds: [obj.opId],
    },
    limit: 100,
    metadataOnly: true,
    skip: !shouldFetch,
  });

  // Cache the result when available
  if (ops.result && shouldFetch) {
    const versionCount = ops.result.length;
    queryCache.peerVersions.set(cacheKey, {
      count: Math.min(versionCount, 99),
      isLimited: versionCount === 100,
    });
  }

  // Use cached value if available, otherwise use the current query result
  const result =
    cachedResult ??
    (ops.result
      ? {
          count: Math.min(ops.result.length, 99),
          isLimited: ops.result.length === 100,
        }
      : null);

  if (ops.loading && cachedResult === undefined) {
    return <LoadingDots />;
  }

  if (!result) {
    return <LoadingDots />;
  }

  return (
    <OpVersionsLink
      entity={obj.entity}
      project={obj.project}
      filter={{
        opName: obj.opId,
      }}
      versionCount={result.count}
      countIsLimited={result.isLimited}
      neverPeek
      variant="secondary"
    />
  );
};

const OpCallsLink: React.FC<{
  obj: OpVersionSchema;
  queryCache: QueryCache;
}> = props => {
  const {useCallsStats} = useWFHooks();

  const obj = props.obj;
  const refUri = opVersionKeyToRefUri(obj);

  // Check if we already have the result cached
  const cachedCallCount = props.queryCache.callStats.get(refUri);
  const shouldFetch = cachedCallCount === undefined;

  const calls = useCallsStats({
    entity: obj.entity,
    project: obj.project,
    filter: {
      opVersionRefs: [refUri],
    },
    skip: !shouldFetch,
  });

  // Cache the result when available
  if (calls.result?.count !== undefined && shouldFetch) {
    props.queryCache.callStats.set(refUri, calls.result.count);
  }

  // Use cached value if available, otherwise use the current query result
  const callCount = cachedCallCount ?? calls?.result?.count ?? 0;

  if (calls.loading && cachedCallCount === undefined) {
    return <LoadingDots />;
  }

  if (callCount === 0) {
    return null;
  }
  return (
    <CallsLink
      neverPeek
      entity={obj.entity}
      project={obj.project}
      callCount={callCount}
      filter={{
        opVersionRefs: [refUri],
      }}
      variant="secondary"
    />
  );
};
