import React, {useEffect, useMemo, useState} from 'react';
import {useWFHooks} from '../wfReactInterface/context';
import {
  GridColDef,
  GridColumnGroupingModel,
  GridRowSelectionModel,
  GridRowsProp,
} from '@mui/x-data-grid-pro';
import {StyledDataGrid} from '../../StyledDataGrid';
import {basicField} from '../common/DataTable';
import {CustomLink, ObjectVersionLink, objectVersionText} from '../common/Links';
import {
  buildDynamicColumns,
  prepareFlattenedDataForTable,
} from '../common/tabularListViews/columnBuilder';
import {Checkbox} from '@wandb/weave/components/Checkbox';
import {UserLink} from '@wandb/weave/components/UserLink';
import {Timestamp} from '../../../../../Timestamp';
import {useURLSearchParamsDict} from '../util';
import {objectVersionKeyToRefUri} from '../wfReactInterface/utilities';
import {
  isTableRef,
  makeRefExpandedPayload,
} from '../wfReactInterface/tsDataModelHooksCallRefExpansion';
import {
  KNOWN_BASE_OBJECT_CLASSES,
  OBJECT_ATTR_EDGE_NAME,
} from '../wfReactInterface/constants';
import _ from 'lodash';
import {Pill} from '../../../../../Tag';
import {ObjectVersionSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {TEAL_600} from '../../../../../../common/css/color.styles';
import {LoadingDots} from '../../../../../LoadingDots';
import {Icon, IconNames} from '@wandb/weave/components/Icon';

// Custom table component specifically for scorers with a custom category column
const ScorerObjectVersionsTable: React.FC<{
  objectVersions: ObjectVersionSchema[];
  objectTitle?: string;
  onRowClick?: (objectVersion: ObjectVersionSchema) => void;
  selectedVersions?: string[];
  setSelectedVersions?: (selected: string[]) => void;
  hidePropsAsColumns?: boolean;
  hidePeerVersionsColumn?: boolean;
  hideCreatedAtColumn?: boolean;
  hideVersionSuffix?: boolean;
}> = props => {
  const {selectedVersions, setSelectedVersions} = props;
  const showPropsAsColumns = !props.hidePropsAsColumns;
  
  const rows: GridRowsProp = useMemo(() => {
    const vals = props.objectVersions.map(ov => ov.val);
    const flat = prepareFlattenedDataForTable(vals);

    return props.objectVersions.map((ov, i) => {
      let val = flat[i];
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
              renderHeader: () => null,
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

      // Object name column
      basicField('weave__object_version_link', props.objectTitle ?? 'Object', {
        hideable: false,
        valueGetter: (unused: any, row: any) => {
          return row.obj.objectId;
        },
        renderCell: cellParams => {
          const obj: ObjectVersionSchema = cellParams.row.obj;
          if (props.onRowClick) {
            let text = props.hideVersionSuffix
              ? obj.objectId
              : objectVersionText(obj.objectId, obj.versionIndex);

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

    // Add dynamic columns if needed
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

    // Custom category column for scorers
    cols.push(
      basicField('baseObjectClass', 'Type', {
        width: 200,
        display: 'flex',
        valueGetter: (unused: any, row: any) => {
          return row.obj.baseObjectClass;
        },
        renderCell: cellParams => {
          const category = cellParams.value;
          // Custom rendering based on scorer type
          if (category === 'AnnotationSpec') {
            return (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Icon name={IconNames.UsersTeam} size="sm" />
                <span>Human Annotation</span>
              </div>
            );
          } else if (category === 'Scorer') {
            return (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Icon name={IconNames.CodeAlt} size="sm" />
                <span>Programmatic Scorer</span>
              </div>
            );
          }
          return null;
        },
      })
    );

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
        basicField('createdAtMs', 'Created', {
          width: 100,
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
      return;
    }
    if (peekId == null) {
      setRowSelectionModel([]);
    } else {
      if (rowIds.includes(peekId)) {
        setRowSelectionModel([peekId]);
      }
    }
  }, [rowIds, peekId]);

  return (
    <StyledDataGrid
      disableColumnMenu={true}
      disableColumnFilter={true}
      disableMultipleColumnsFiltering={true}
      disableColumnPinning={false}
      disableColumnReorder={true}
      disableColumnResize={false}
      disableColumnSelector={true}
      disableMultipleColumnsSorting={true}
      rows={rows}
      initialState={{
        sorting: {
          sortModel: [{field: 'baseObjectClass', sort: 'asc'}],
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

// Helper component to show peer versions link (simplified for this example)
const PeerVersionsLink: React.FC<{obj: ObjectVersionSchema}> = props => {
  const {useRootObjectVersions} = useWFHooks();

  const obj = props.obj;
  const objectVersionsNode = useRootObjectVersions(
    obj.entity,
    obj.project,
    {
      objectIds: [obj.objectId],
    },
    100,
    true
  );
  if (objectVersionsNode.loading) {
    return <LoadingDots />;
  }
  const countValue = objectVersionsNode.result?.length ?? 0;
  return <div>{countValue} versions</div>;
};

export const CombinedScorersTable: React.FC<{
  entity: string;
  project: string;
}> = ({entity, project}) => {
  const {useRootObjectVersions} = useWFHooks();
  const objectVersions = useRootObjectVersions(
    entity,
    project,
    {
      baseObjectClasses: ['Scorer', 'AnnotationSpec'],
      latestOnly: true,
    },
    undefined,
    true
  );

  if (objectVersions.loading) {
    return <div>Loading...</div>;
  }

  if (objectVersions.error) {
    return <div>Error loading scorers</div>;
  }

  return (
    <ScorerObjectVersionsTable
      objectVersions={objectVersions.result ?? []}
      objectTitle="Scorer"
    />
  );
}; 