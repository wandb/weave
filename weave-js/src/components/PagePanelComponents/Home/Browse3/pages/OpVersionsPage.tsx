import {
  GridColDef,
  GridColumnGroupingModel,
  GridRowSelectionModel,
  GridRowsProp,
} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {useEffect, useMemo, useState} from 'react';

import {Timestamp} from '../../../../Timestamp';
import {StyledDataGrid} from '../StyledDataGrid';
import {CategoryChip} from './common/CategoryChip';
import {basicField} from './common/DataTable';
import {CallsLink, OpVersionLink, OpVersionsLink} from './common/Links';
import {SimplePageLayout} from './common/SimplePageLayout';
import {useInitializingFilter, useURLSearchParamsDict} from './util';
import {HackyOpCategory} from './wfInterface/types';
import {useWFHooks} from './wfReactInterface/context';
import {opVersionKeyToRefUri} from './wfReactInterface/utilities';
import {OpVersionSchema} from './wfReactInterface/wfDataModelHooksInterface';

export type WFHighLevelOpVersionFilter = {
  opCategory?: HackyOpCategory | null;
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
  const {filter, setFilter} = useInitializingFilter(
    props.initialFilter,
    props.onFilterUpdate
  );

  const title = useMemo(() => {
    if (filter.opName) {
      return 'Implementations of ' + filter.opName;
    } else if (filter.opCategory) {
      return _.capitalize(filter.opCategory) + ' Operations';
    }
    return 'All Operations';
  }, [filter.opCategory, filter.opName]);

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

  const filteredObjectVersions = useOpVersions(props.entity, props.project, {
    category: effectiveFilter.opCategory
      ? [effectiveFilter.opCategory]
      : undefined,
    opIds: effectiveFilter.opName ? [effectiveFilter.opName] : undefined,
    latestOnly: effectivelyLatestOnly,
  });

  const rows: GridRowsProp = useMemo(() => {
    return (filteredObjectVersions.result ?? []).map((ov, i) => {
      return {
        id: opVersionKeyToRefUri(ov),
        obj: ov,
        createdAt: ov.createdAtMs,
      };
    });
  }, [filteredObjectVersions.result]);
  const columns: GridColDef[] = [
    basicField('version', 'Op', {
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
          />
        );
      },
    }),

    basicField('calls', 'Calls', {
      width: 100,
      renderCell: cellParams => {
        const obj: OpVersionSchema = cellParams.row.obj;
        return <OpCallsLink obj={obj} />;
      },
    }),

    basicField('typeCategory', 'Category', {
      width: 100,
      renderCell: cellParams => {
        const obj: OpVersionSchema = cellParams.row.obj;
        return obj.category && <CategoryChip value={obj.category} />;
      },
    }),

    basicField('createdAt', 'Created', {
      width: 100,
      renderCell: cellParams => {
        const obj: OpVersionSchema = cellParams.row.obj;
        return <Timestamp value={obj.createdAtMs / 1000} format="relative" />;
      },
    }),

    ...(effectivelyLatestOnly
      ? [
          basicField('peerVersions', 'Versions', {
            width: 100,
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

  return (
    <StyledDataGrid
      rows={rows}
      initialState={{
        sorting: {
          sortModel: [{field: 'createdAt', sort: 'desc'}],
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
  const {useCalls} = useWFHooks();

  const obj = props.obj;
  const refUri = opVersionKeyToRefUri(obj);

  // Here, we really just want to know the count - and it should be calculated
  // by the server, not by the client. This is a performance optimization. In
  // the meantime we will just fetch the first 100 versions and display 99+ if
  // there are at least 100. Someone can come back and add `count` to the 3
  // query APIs which will make this faster.
  const calls = useCalls(
    obj.entity,
    obj.project,
    {
      opVersionRefs: [refUri],
    },
    100
  );

  const callCount = calls?.result?.length ?? 0;

  if (callCount === 0) {
    return null;
  }
  return (
    <CallsLink
      neverPeek
      entity={obj.entity}
      project={obj.project}
      callCount={Math.min(callCount, 99)}
      countIsLimited={callCount === 100}
      filter={{
        opVersionRefs: [refUri],
      }}
      variant="secondary"
    />
  );
};
