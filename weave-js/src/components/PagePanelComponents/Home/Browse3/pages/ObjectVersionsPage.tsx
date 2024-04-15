import {
  GridColDef,
  GridColumnGroupingModel,
  GridRowSelectionModel,
  GridRowsProp,
} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {useEffect, useMemo, useState} from 'react';

import {Loading} from '../../../../Loading';
import {LoadingDots} from '../../../../LoadingDots';
import {Timestamp} from '../../../../Timestamp';
import {useWeaveflowRouteContext} from '../context';
import {StyledDataGrid} from '../StyledDataGrid';
import {basicField} from './common/DataTable';
import {Empty} from './common/Empty';
import {
  EMPTY_PROPS_DATASETS,
  EMPTY_PROPS_MODEL,
  EMPTY_PROPS_OBJECTS,
} from './common/EmptyContent';
import {ObjectVersionLink, ObjectVersionsLink} from './common/Links';
import {FilterLayoutTemplate} from './common/SimpleFilterableDataTable';
import {SimplePageLayout} from './common/SimplePageLayout';
import {TypeVersionCategoryChip} from './common/TypeVersionCategoryChip';
import {useInitializingFilter, useURLSearchParamsDict} from './util';
import {useWFHooks} from './wfReactInterface/context';
import {objectVersionKeyToRefUri} from './wfReactInterface/utilities';
import {
  KnownBaseObjectClassType,
  ObjectVersionSchema,
} from './wfReactInterface/wfDataModelHooksInterface';

export const ObjectVersionsPage: React.FC<{
  entity: string;
  project: string;
  initialFilter?: WFHighLevelObjectVersionFilter;
  // Setting this will make the component a controlled component. The parent
  // is responsible for updating the filter.
  onFilterUpdate?: (filter: WFHighLevelObjectVersionFilter) => void;
}> = props => {
  const {filter, setFilter} = useInitializingFilter(
    props.initialFilter,
    props.onFilterUpdate
  );

  const title = useMemo(() => {
    if (filter.objectName) {
      return 'Versions of ' + filter.objectName;
    } else if (filter.baseObjectClass) {
      return _.capitalize(filter.baseObjectClass) + 's';
    }
    return 'All Objects';
  }, [filter.objectName, filter.baseObjectClass]);

  return (
    <SimplePageLayout
      title={title}
      hideTabsIfSingle
      tabs={[
        {
          label: '',
          content: (
            <FilterableObjectVersionsTable
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

export type WFHighLevelObjectVersionFilter = {
  objectName?: string | null;
  baseObjectClass?: KnownBaseObjectClassType | null;
};

export const FilterableObjectVersionsTable: React.FC<{
  entity: string;
  project: string;
  frozenFilter?: WFHighLevelObjectVersionFilter;
  initialFilter?: WFHighLevelObjectVersionFilter;
  // Setting this will make the component a controlled component. The parent
  // is responsible for updating the filter.
  onFilterUpdate?: (filter: WFHighLevelObjectVersionFilter) => void;
}> = props => {
  const {useRootObjectVersions} = useWFHooks();
  const {baseRouter} = useWeaveflowRouteContext();

  const effectiveFilter = useMemo(() => {
    return {...props.initialFilter, ...props.frozenFilter};
  }, [props.initialFilter, props.frozenFilter]);

  const effectivelyLatestOnly = !effectiveFilter.objectName;

  const filteredObjectVersions = useRootObjectVersions(
    props.entity,
    props.project,
    {
      baseObjectClasses: effectiveFilter.baseObjectClass
        ? [effectiveFilter.baseObjectClass]
        : undefined,
      objectIds: effectiveFilter.objectName
        ? [effectiveFilter.objectName]
        : undefined,
      latestOnly: effectivelyLatestOnly,
    }
  );

  if (filteredObjectVersions.loading) {
    return <Loading centered />;
  }

  // TODO: Only show the empty state if no filters other than baseObjectClass
  const objectVersions = filteredObjectVersions.result ?? [];
  const isEmpty = objectVersions.length === 0;
  if (isEmpty) {
    let propsEmpty = EMPTY_PROPS_OBJECTS;
    const base = props.initialFilter?.baseObjectClass;
    if ('Model' === base) {
      propsEmpty = EMPTY_PROPS_MODEL;
    } else if ('Dataset' === base) {
      propsEmpty = EMPTY_PROPS_DATASETS;
    }
    return <Empty {...propsEmpty} />;
  }

  return (
    <FilterLayoutTemplate
      showFilterIndicator={Object.keys(effectiveFilter ?? {}).length > 0}
      showPopoutButton={Object.keys(props.frozenFilter ?? {}).length > 0}
      filterPopoutTargetUrl={baseRouter.objectVersionsUIUrl(
        props.entity,
        props.project,
        effectiveFilter
      )}>
      <ObjectVersionsTable
        objectVersions={objectVersions}
        usingLatestFilter={effectivelyLatestOnly}
      />
    </FilterLayoutTemplate>
  );
};

const ObjectVersionsTable: React.FC<{
  objectVersions: ObjectVersionSchema[];
  usingLatestFilter?: boolean;
}> = props => {
  const rows: GridRowsProp = useMemo(() => {
    return props.objectVersions.map((ov, i) => {
      return {
        ...ov,
        id: objectVersionKeyToRefUri(ov),
        object: `${ov.objectId}:v${ov.versionIndex}`,
        obj: ov,
      };
    });
  }, [props.objectVersions]);
  const columns: GridColDef[] = [
    basicField('object', 'Object', {
      hideable: false,
      renderCell: cellParams => {
        // Icon to indicate navigation to the object version
        const obj: ObjectVersionSchema = cellParams.row.obj;
        return (
          <ObjectVersionLink
            entityName={obj.entity}
            projectName={obj.project}
            objectName={obj.objectId}
            version={obj.versionHash}
            versionIndex={obj.versionIndex}
          />
        );
      },
    }),
    basicField('baseObjectClass', 'Category', {
      width: 100,
      renderCell: cellParams => {
        const category = cellParams.value;
        if (category === 'Model' || category === 'Dataset') {
          return <TypeVersionCategoryChip baseObjectClass={category} />;
        }
        return null;
      },
    }),
    basicField('createdAtMs', 'Created', {
      width: 100,
      renderCell: cellParams => {
        const createdAtMs = cellParams.value;
        return <Timestamp value={createdAtMs / 1000} format="relative" />;
      },
    }),
    ...(props.usingLatestFilter
      ? [
          basicField('peerVersions', 'Versions', {
            width: 100,
            sortable: false,
            filterable: false,
            renderCell: cellParams => {
              const obj: ObjectVersionSchema = cellParams.row.obj;
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

const PeerVersionsLink: React.FC<{obj: ObjectVersionSchema}> = props => {
  const {useRootObjectVersions} = useWFHooks();

  const obj = props.obj;
  // Here, we really just want to know the count - and it should be calculated
  // by the server, not by the client. This is a performance optimization. In
  // the meantime we will just fetch the first 100 versions and display 99+ if
  // there are at least 100. Someone can come back and add `count` to the 3
  // query APIs which will make this faster.
  const objectVersionsNode = useRootObjectVersions(
    obj.entity,
    obj.project,
    {
      objectIds: [obj.objectId],
    },
    100
  );
  if (objectVersionsNode.loading) {
    return <LoadingDots />;
  }
  const countValue = objectVersionsNode.result?.length ?? 0;
  return (
    <ObjectVersionsLink
      entity={obj.entity}
      project={obj.project}
      filter={{
        objectName: obj.objectId,
      }}
      versionCount={Math.min(countValue, 99)}
      countIsLimited={countValue === 100}
      neverPeek
      variant="secondary"
    />
  );
};
