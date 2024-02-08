import {
  GridColDef,
  GridColumnGroupingModel,
  GridRowSelectionModel,
  GridRowsProp,
} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {useEffect, useMemo, useState} from 'react';

import {Timestamp} from '../../../../Timestamp';
import {useWeaveflowRouteContext} from '../context';
import {StyledDataGrid} from '../StyledDataGrid';
import {basicField} from './common/DataTable';
import {ObjectVersionLink, ObjectVersionsLink} from './common/Links';
import {FilterLayoutTemplate} from './common/SimpleFilterableDataTable';
import {SimplePageLayout} from './common/SimplePageLayout';
import {TypeVersionCategoryChip} from './common/TypeVersionCategoryChip';
import {useInitializingFilter, useURLSearchParamsDict} from './util';
import {HackyTypeCategory} from './wfInterface/types';
import {
  objectVersionKeyToRefUri,
  ObjectVersionSchema,
  useRootObjectVersions,
} from './wfReactInterface/interface';

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
    } else if (filter.typeCategory) {
      return _.capitalize(filter.typeCategory) + 's';
    }
    return 'All Objects';
  }, [filter.objectName, filter.typeCategory]);

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
  typeCategory?: HackyTypeCategory | null;
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
  const {baseRouter} = useWeaveflowRouteContext();

  const effectiveFilter = useMemo(() => {
    return {...props.initialFilter, ...props.frozenFilter};
  }, [props.initialFilter, props.frozenFilter]);

  const effectivelyLatestOnly = !effectiveFilter.objectName;

  const filteredObjectVersions = useRootObjectVersions(
    props.entity,
    props.project,
    {
      category: effectiveFilter.typeCategory
        ? [effectiveFilter.typeCategory]
        : undefined,
      objectIds: effectiveFilter.objectName
        ? [effectiveFilter.objectName]
        : undefined,
      latestOnly: effectivelyLatestOnly,
    }
  );

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
        objectVersions={filteredObjectVersions.result ?? []}
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
        id: objectVersionKeyToRefUri(ov),
        obj: ov,
        createdAt: ov.createdAtMs,
      };
    });
  }, [props.objectVersions]);
  const columns: GridColDef[] = [
    basicField('version', 'Object', {
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
            filePath={obj.path}
            refExtra={obj.refExtra}
          />
        );
      },
    }),
    basicField('typeCategory', 'Category', {
      width: 100,
      renderCell: cellParams => {
        const obj: ObjectVersionSchema = cellParams.row.obj;
        return <TypeVersionCategoryChip typeCategory={obj.category} />;
      },
    }),
    basicField('createdAt', 'Created', {
      width: 100,
      renderCell: cellParams => {
        const obj: ObjectVersionSchema = cellParams.row.obj;
        return <Timestamp value={obj.createdAtMs / 1000} format="relative" />;
      },
    }),
    ...(props.usingLatestFilter
      ? [
          basicField('peerVersions', 'Versions', {
            width: 100,
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

const PeerVersionsLink: React.FC<{obj: ObjectVersionSchema}> = props => {
  const obj = props.obj;
  const objectVersions = useRootObjectVersions(obj.entity, obj.project, {
    objectIds: [obj.objectId],
  });
  return (
    <ObjectVersionsLink
      entity={obj.entity}
      project={obj.project}
      filter={{
        objectName: obj.objectId,
      }}
      versionCount={(objectVersions.result ?? []).length}
      neverPeek
      variant="secondary"
    />
  );
};
