import {
  GridColDef,
  GridColumnGroupingModel,
  GridRowSelectionModel,
  GridRowsProp,
} from '@mui/x-data-grid-pro';
import React, {useEffect, useMemo, useState} from 'react';

import {ErrorPanel} from '../../../../ErrorPanel';
import {Loading} from '../../../../Loading';
import {LoadingDots} from '../../../../LoadingDots';
import {Timestamp} from '../../../../Timestamp';
import {StyledDataGrid} from '../StyledDataGrid';
import {basicField} from './common/DataTable';
import {Empty} from './common/Empty';
import {EMPTY_PROPS_OPERATIONS} from './common/EmptyContent';
import {
  CallsLink,
  opNiceName,
  OpVersionLink,
  OpVersionsLink,
} from './common/Links';
import {SimplePageLayout} from './common/SimplePageLayout';
import {useControllableState, useURLSearchParamsDict} from './util';
import {useWFHooks} from './wfReactInterface/context';
import {opVersionKeyToRefUri} from './wfReactInterface/utilities';
import {OpVersionSchema} from './wfReactInterface/wfDataModelHooksInterface';

export type WFHighLevelOpVersionFilter = {
  opName?: string | null;
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

  const filteredOpVersions = useOpVersions(props.entity, props.project, {
    opIds: effectiveFilter.opName ? [effectiveFilter.opName] : undefined,
    latestOnly: effectivelyLatestOnly,
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
  const columns: GridColDef[] = [
    basicField('op', 'Op', {
      hideable: false,
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
        return <OpCallsLink obj={obj} />;
      },
    }),

    basicField('createdAtMs', 'Created', {
      width: 100,
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
              return <PeerVersionsLink obj={obj} />;
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
      experimentalFeatures={{columnGrouping: true}}
      disableRowSelectionOnClick
      rowSelectionModel={rowSelectionModel}
      columnGroupingModel={columnGroupingModel}
    />
  );
};

const PeerVersionsLink: React.FC<{obj: OpVersionSchema}> = props => {
  const {useOpVersions} = useWFHooks();
  const obj = props.obj;
  // Here, we really just want to know the count - and it should be calculated
  // by the server, not by the client. This is a performance optimization. In
  // the meantime we will just fetch the first 100 versions and display 99+ if
  // there are at least 100. Someone can come back and add `count` to the 3
  // query APIs which will make this faster.
  const ops = useOpVersions(
    obj.entity,
    obj.project,
    {
      opIds: [obj.opId],
    },
    100
  );
  if (ops.loading) {
    return <LoadingDots />;
  }

  const versionCount = ops?.result?.length ?? 0;

  return (
    <OpVersionsLink
      entity={obj.entity}
      project={obj.project}
      filter={{
        opName: obj.opId,
      }}
      versionCount={Math.min(versionCount, 99)}
      countIsLimited={versionCount === 100}
      neverPeek
      variant="secondary"
    />
  );
};

const OpCallsLink: React.FC<{obj: OpVersionSchema}> = props => {
  const {useCallsStats} = useWFHooks();

  const obj = props.obj;
  const refUri = opVersionKeyToRefUri(obj);

  const calls = useCallsStats(obj.entity, obj.project, {
    opVersionRefs: [refUri],
  });
  if (calls.loading) {
    return <LoadingDots />;
  }

  const callCount = calls?.result?.count ?? 0;

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
