import {
  GridColDef,
  GridColumnGroupingModel,
  GridRowSelectionModel,
  GridRowsProp,
} from '@mui/x-data-grid-pro';
import {Checkbox} from '@wandb/weave/components/Checkbox';
import {UserLink} from '@wandb/weave/components/UserLink';
import _ from 'lodash';
import React, {useEffect, useMemo, useState} from 'react';

import {TEAL_600} from '../../../../../../common/css/color.styles';
import {ErrorPanel} from '../../../../../ErrorPanel';
import {Loading} from '../../../../../Loading';
import {LoadingDots} from '../../../../../LoadingDots';
import {Timestamp} from '../../../../../Timestamp';
import {useWeaveflowRouteContext} from '../../context';
import {StyledDataGrid} from '../../StyledDataGrid';
import {basicField} from '../common/DataTable';
import {Empty} from '../common/Empty';
import {
  EMPTY_PROPS_ACTION_SPECS,
  EMPTY_PROPS_ANNOTATIONS,
  EMPTY_PROPS_DASHBOARDS,
  EMPTY_PROPS_DATASETS,
  EMPTY_PROPS_LEADERBOARDS,
  EMPTY_PROPS_MODEL,
  EMPTY_PROPS_OBJECTS,
  EMPTY_PROPS_PROGRAMMATIC_SCORERS,
  EMPTY_PROPS_PROMPTS,
} from '../common/EmptyContent';
import {
  CustomLink,
  ObjectVersionLink,
  ObjectVersionsLink,
  objectVersionText,
} from '../common/Links';
import {FilterLayoutTemplate} from '../common/SimpleFilterableDataTable';
import {
  buildDynamicColumns,
  prepareFlattenedDataForTable,
} from '../common/tabularListViews/columnBuilder';
import {TypeVersionCategoryChip} from '../common/TypeVersionCategoryChip';
import {useURLSearchParamsDict} from '../util';
import {
  KNOWN_BASE_OBJECT_CLASSES,
  OBJECT_ATTR_EDGE_NAME,
} from '../wfReactInterface/constants';
import {useWFHooks} from '../wfReactInterface/context';
import {
  isTableRef,
  makeRefExpandedPayload,
} from '../wfReactInterface/tsDataModelHooksCallRefExpansion';
import {objectVersionKeyToRefUri} from '../wfReactInterface/utilities';
import {ObjectVersionSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {WFHighLevelObjectVersionFilter} from './objectsPageTypes';

const DATASET_BASE_OBJECT_CLASS = 'Dataset';

export const ObjectVersionsTable: React.FC<{
  objectVersions: ObjectVersionSchema[];
  objectTitle?: string;
  hidePropsAsColumns?: boolean;
  hidePeerVersionsColumn?: boolean;
  hideCategoryColumn?: boolean;
  hideCreatedAtColumn?: boolean;
  hideVersionSuffix?: boolean;
  onRowClick?: (objectVersion: ObjectVersionSchema) => void;
  selectedVersions?: string[];
  setSelectedVersions?: (selected: string[]) => void;
}> = props => {
  // `showPropsAsColumns` probably needs to be a bit more robust
  const {selectedVersions, setSelectedVersions} = props;
  const showPropsAsColumns = !props.hidePropsAsColumns;
  const rows: GridRowsProp = useMemo(() => {
    const vals = props.objectVersions.map(ov => ov.val);
    const flat = prepareFlattenedDataForTable(vals);

    return props.objectVersions.map((ov, i) => {
      let val = flat[i];
      if (ov.baseObjectClass === DATASET_BASE_OBJECT_CLASS) {
        // We don't want to show the rows column for datasets
        // because it is redundant. Probably want a more generic
        // solution here in the future. Maybe exclude table refs?
        val = _.omit(val, 'rows');
      }
      // Show name, even though it can be = to object id, consider adding back
      // val = _.omit(val, 'name');
      return {
        id: objectVersionKeyToRefUri(ov),
        obj: {
          ...ov,
          val,
        },
      };
    });
  }, [props.objectVersions]);

  const showUserColumn = rows.some(row => row.obj.userId != null);

  // TODO: We should make this page very robust similar to the CallsTable page.
  // We will want to do nearly all the same things: URL state management,
  // sorting, filtering, ref expansion, etc... A lot of common logic should be
  // extracted and shared.
  const {cols: columns, groups: columnGroupingModel} = useMemo(() => {
    let groups: GridColumnGroupingModel = [];
    const checkboxColumnArr: GridColDef[] =
      selectedVersions != null && setSelectedVersions
        ? [
            {
              minWidth: 30,
              width: 34,
              field: 'CustomCheckbox',
              sortable: false,
              disableColumnMenu: true,
              resizable: false,
              disableExport: true,
              display: 'flex',
              renderHeader: (params: any) => {
                // TODO: Adding a select all checkbox here not that useful for compare
                // but might for be for other bulk actions.
                return null;
              },
              renderCell: (params: any) => {
                const {objectId, versionIndex} = params.row.obj;
                const objSpecifier = `${objectId}:v${versionIndex}`;
                const isSelected = selectedVersions.includes(objSpecifier);
                return (
                  <Checkbox
                    size="small"
                    checked={isSelected}
                    onCheckedChange={() => {
                      if (isSelected) {
                        setSelectedVersions(
                          selectedVersions.filter(id => id !== objSpecifier)
                        );
                      } else {
                        // Keep the objects in sorted order, regardless of the order checked.
                        setSelectedVersions(
                          [...selectedVersions, objSpecifier].sort((a, b) => {
                            const [aName, aVer] = a.split(':');
                            const [bName, bVer] = b.split(':');
                            if (aName !== bName) {
                              return aName.localeCompare(bName);
                            }
                            const aNum = parseInt(aVer.slice(1), 10);
                            const bNum = parseInt(bVer.slice(1), 10);
                            return aNum - bNum;
                          })
                        );
                      }
                    }}
                  />
                );
              },
            },
          ]
        : [];
    const cols: GridColDef[] = [
      ...checkboxColumnArr,

      // This field name chosen to reduce possibility of conflict
      // with the dynamic fields added below.
      basicField('weave__object_version_link', props.objectTitle ?? 'Object', {
        hideable: false,
        valueGetter: (unused: any, row: any) => {
          return row.obj.objectId;
        },
        renderCell: cellParams => {
          // Icon to indicate navigation to the object version
          const obj: ObjectVersionSchema = cellParams.row.obj;
          if (props.onRowClick) {
            let text = props.hideVersionSuffix
              ? obj.objectId
              : objectVersionText(obj.objectId, obj.versionIndex);

            // This allows us to use the object name as the link text
            // if it is available. Probably should make this workfor
            // the object version link as well.
            if (obj.val.name) {
              text = obj.val.name;
            }

            return (
              <CustomLink text={text} onClick={() => props.onRowClick?.(obj)} />
            );
          }
          return (
            <ObjectVersionLink
              entityName={obj.entity}
              projectName={obj.project}
              objectName={obj.objectId}
              version={obj.versionHash}
              versionIndex={obj.versionIndex}
              fullWidth={true}
              color={TEAL_600}
              hideVersionSuffix={props.hideVersionSuffix}
            />
          );
        },
      }),
    ];

    if (showPropsAsColumns) {
      const dynamicFields: string[] = [];
      const dynamicFieldSet = new Set<string>();
      rows.forEach(r => {
        Object.keys(r.obj.val).forEach(k => {
          if (!dynamicFieldSet.has(k)) {
            dynamicFieldSet.add(k);
            dynamicFields.push(k);
          }
        });
      });

      const {cols: newCols, groupingModel} = buildDynamicColumns<{
        obj: ObjectVersionSchema;
      }>(
        dynamicFields,
        row => ({
          entity: row.obj.entity,
          project: row.obj.project,
        }),
        (row, key) => {
          const obj: ObjectVersionSchema = row.obj;
          const res = obj.val?.[key];
          if (isTableRef(res)) {
            // This whole block is a hack to make the table ref clickable. This
            // is the same thing that the CallsTable does for expanded fields.
            // Once we come up with a common pattern for ref expansion, this
            // will go away.
            const selfRefUri = objectVersionKeyToRefUri(obj);
            const targetRefUri =
              selfRefUri +
              ('/' +
                OBJECT_ATTR_EDGE_NAME +
                '/' +
                key.split('.').join(OBJECT_ATTR_EDGE_NAME + '/'));
            return makeRefExpandedPayload(targetRefUri, res);
          }
          return res;
        }
      );
      cols.push(...newCols);
      groups = groupingModel;
    }

    if (!props.hideCategoryColumn) {
      cols.push(
        basicField('baseObjectClass', 'Category', {
          width: 132,
          display: 'flex',
          valueGetter: (unused: any, row: any) => {
            return row.obj.baseObjectClass;
          },
          renderCell: cellParams => {
            const category = cellParams.value;
            if (KNOWN_BASE_OBJECT_CLASSES.includes(category)) {
              return <TypeVersionCategoryChip baseObjectClass={category} />;
            }
            return null;
          },
        })
      );
    }

    if (showUserColumn) {
      cols.push(
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
        })
      );
    }

    if (!props.hideCreatedAtColumn) {
      cols.push(
        basicField('createdAtMs', 'Last updated', {
          width: 130,
          valueGetter: (unused: any, row: any) => {
            return row.obj.createdAtMs;
          },
          renderCell: cellParams => {
            const createdAtMs = cellParams.value;
            return <Timestamp value={createdAtMs / 1000} format="relative" />;
          },
        })
      );
    }

    if (!props.hidePeerVersionsColumn) {
      cols.push(
        basicField('peerVersions', 'Versions', {
          width: 100,
          sortable: false,
          filterable: false,
          renderCell: cellParams => {
            const obj: ObjectVersionSchema = cellParams.row.obj;
            return <PeerVersionsLink obj={obj} />;
          },
        })
      );
    }

    return {cols, groups};
  }, [
    props,
    showPropsAsColumns,
    rows,
    selectedVersions,
    setSelectedVersions,
    showUserColumn,
  ]);

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
      disableRowSelectionOnClick
      rowSelectionModel={rowSelectionModel}
      columnGroupingModel={columnGroupingModel}
    />
  );
};

export const FilterableObjectVersionsTable: React.FC<{
  entity: string;
  project: string;
  frozenFilter?: WFHighLevelObjectVersionFilter;
  initialFilter?: WFHighLevelObjectVersionFilter;
  objectTitle?: string;
  hideCategoryColumn?: boolean;
  hideCreatedAtColumn?: boolean;
  // Setting this will make the component a controlled component. The parent
  // is responsible for updating the filter.
  onFilterUpdate?: (filter: WFHighLevelObjectVersionFilter) => void;
  selectedVersions?: string[];
  setSelectedVersions?: (selected: string[]) => void;
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
    },
    undefined,
    effectivelyLatestOnly // metadata only when getting latest
  );

  if (filteredObjectVersions.loading) {
    return <Loading centered />;
  }
  if (filteredObjectVersions.error) {
    return <ErrorPanel />;
  }

  // TODO: Only show the empty state if no filters other than baseObjectClass
  const objectVersions = filteredObjectVersions.result ?? [];
  const isEmpty = objectVersions.length === 0;
  if (isEmpty) {
    let propsEmpty = EMPTY_PROPS_OBJECTS;
    const base = props.initialFilter?.baseObjectClass;
    if ('Dashboard' === base) {
      propsEmpty = EMPTY_PROPS_DASHBOARDS;
    } else if ('Prompt' === base) {
      propsEmpty = EMPTY_PROPS_PROMPTS;
    } else if ('Model' === base) {
      propsEmpty = EMPTY_PROPS_MODEL;
    } else if (DATASET_BASE_OBJECT_CLASS === base) {
      propsEmpty = EMPTY_PROPS_DATASETS;
    } else if (base === 'Leaderboard') {
      propsEmpty = EMPTY_PROPS_LEADERBOARDS;
    } else if (base === 'Scorer') {
      propsEmpty = EMPTY_PROPS_PROGRAMMATIC_SCORERS;
    } else if (base === 'ActionSpec') {
      propsEmpty = EMPTY_PROPS_ACTION_SPECS;
    } else if (base === 'AnnotationSpec') {
      propsEmpty = EMPTY_PROPS_ANNOTATIONS;
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
        objectTitle={props.objectTitle}
        hidePropsAsColumns={!!effectivelyLatestOnly}
        hidePeerVersionsColumn={!effectivelyLatestOnly}
        hideCategoryColumn={props.hideCategoryColumn}
        hideCreatedAtColumn={props.hideCreatedAtColumn}
        selectedVersions={props.selectedVersions}
        setSelectedVersions={props.setSelectedVersions}
      />
    </FilterLayoutTemplate>
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
    100,
    true // metadataOnly
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
