import {Box} from '@mui/material';
import {
  GridColDef,
  GridColumnGroup,
  GridLeafColumn,
  GridRenderCellParams,
  GridSortDirection,
  GridSortItem,
} from '@mui/x-data-grid-pro';
import {Timestamp} from '@wandb/weave/components/Timestamp';
import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {useHistory} from 'react-router-dom';

import {NotApplicable} from '../../../Browse2/NotApplicable';
import {parseRefMaybe, SmallRef} from '../../../Browse2/SmallRef';
import {useWeaveflowRouteContext} from '../../context';
import {PaginationButtons} from '../../pages/CallsPage/CallsTableButtons';
import {StyledDataGrid} from '../../StyledDataGrid';
import {
  GroupedLeaderboardData,
  GroupedLeaderboardModelGroup,
  LeaderboardValueRecord,
} from './query/leaderboardQuery';

const USE_COMPARE_EVALUATIONS_PAGE = true;

interface LeaderboardGridProps {
  entity: string;
  project: string;
  data: GroupedLeaderboardData;
  loading: boolean;
}

type RowData = {
  id: string;
  modelGroupName: string;
  modelGroup: GroupedLeaderboardModelGroup;
};

export const LeaderboardGrid: React.FC<LeaderboardGridProps> = ({
  entity,
  project,
  data,
  loading,
}) => {
  const {peekingRouter} = useWeaveflowRouteContext();
  const history = useHistory();
  const onCellClick = useCallback(
    (record: LeaderboardValueRecord) => {
      const sourceCallId = record.sourceEvaluationCallId;
      if (sourceCallId) {
        let to: string;
        if (USE_COMPARE_EVALUATIONS_PAGE) {
          to = peekingRouter.compareEvaluationsUri(entity, project, [
            sourceCallId,
          ]);
        } else {
          to = peekingRouter.callUIUrl(entity, project, '', sourceCallId, null);
        }
        history.push(to);
      }
    },
    [entity, history, peekingRouter, project]
  );

  const columnStats = useMemo(() => getColumnStats(data), [data]);

  const getColorForScore = useCallback(
    (datasetGroup, scorerGroup, metricPathGroup, score) => {
      const shouldMinimize = ['Avg. Latency'].includes(metricPathGroup);
      if (score == null) {
        return 'transparent';
      }
      const {min, max, count} =
        columnStats.datasetGroups[datasetGroup].scorerGroups[scorerGroup]
          .metricPathGroups[metricPathGroup];
      if (count === 0 || count === 1) {
        return 'transparent';
      }
      const normalizedScore = shouldMinimize
        ? (max - score) / (max - min)
        : (score - min) / (max - min);
      return `hsl(${120 * normalizedScore}, 70%, 85%)`;
    },
    [columnStats.datasetGroups]
  );

  const rows: RowData[] = useMemo(() => {
    const rowData: RowData[] = [];
    Object.entries(data.modelGroups).forEach(([modelGroupName, modelGroup]) => {
      rowData.push({
        id: modelGroupName,
        modelGroupName,
        modelGroup,
      });
    });
    return rowData;
  }, [data]);

  const columns: Array<GridColDef<RowData>> = useMemo(
    () => [
      {
        field: 'modelGroupName',
        headerName: 'Model',
        minWidth: 150,
        flex: 1,
        renderCell: (params: GridRenderCellParams) => {
          const modelRef = parseRefMaybe(
            `weave:///${entity}/${project}/object/${params.value}` ?? ''
          );
          if (modelRef) {
            return (
              <div
                style={{
                  width: '100%',
                  height: '100%',
                  alignContent: 'center',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  lineHeight: '20px',
                }}>
                <SmallRef objRef={modelRef} />
              </div>
            );
          }
          return <div>{params.value}</div>;
        },
      },
      ...Object.entries(columnStats.datasetGroups).flatMap(
        ([datasetGroupName, datasetGroup]) =>
          Object.entries(datasetGroup.scorerGroups).flatMap(
            ([scorerGroupName, scorerGroup]) => {
              return Object.entries(scorerGroup.metricPathGroups).map(
                ([metricPathGroupName, metricPathGroup]) => {
                  return {
                    field: `${datasetGroupName}--${scorerGroupName}--${metricPathGroupName}`,
                    headerName: `${metricPathGroupName}`,
                    // headerName: `${metricPathGroupName.split('.').pop()}`,
                    minWidth: 100,
                    flex: 1,
                    valueGetter: (value: any, row: RowData) => {
                      return valueFromRowData(
                        row,
                        datasetGroupName,
                        scorerGroupName,
                        metricPathGroupName
                      );
                    },
                    getSortComparator: defaultGetSortComparator,

                    renderCell: (params: GridRenderCellParams) => {
                      const record = recordFromRowData(
                        params.row,
                        datasetGroupName,
                        scorerGroupName,
                        metricPathGroupName
                      );
                      const value = record?.metricValue;
                      let inner: React.ReactNode = value;
                      if (inner == null) {
                        inner = <NotApplicable />;
                      } else if (typeof inner === 'number') {
                        if (inner < 1) {
                          inner = `${(inner * 100).toFixed(2)}%`;
                        } else {
                          inner = `${inner.toFixed(2)}`;
                        }
                      } else if (value instanceof Date) {
                        console.log(value.getTime());
                        return (
                          <Timestamp
                            value={value.getTime() / 1000}
                            format="relative"
                          />
                        );
                      } else {
                        inner = JSON.stringify(params.value);
                      }
                      return (
                        <div
                          style={{
                            width: '100%',
                            height: '100%',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            backgroundColor: getColorForScore(
                              datasetGroupName,
                              scorerGroupName,
                              metricPathGroupName,
                              value
                            ),
                          }}
                          onClick={() => record && onCellClick(record)}>
                          {inner}
                        </div>
                      );
                    },
                  };
                }
              );
            }
          )
      ),
    ],
    [columnStats.datasetGroups, entity, getColorForScore, onCellClick, project]
  );

  const groupingModel: GridColumnGroup[] = useMemo(() => {
    const datasetGroups: GridColumnGroup[] = [];
    Object.entries(columnStats.datasetGroups).forEach(
      ([datasetGroupName, datasetGroup]) => {
        const datasetColGroup: GridColumnGroup = {
          groupId: datasetGroupName,
          headerName: datasetGroupName,
          children: [],
          renderHeaderGroup: params => {
            const ref = parseRefMaybe(
              `weave:///${entity}/${project}/object/${datasetGroupName}` ?? ''
            );
            if (ref) {
              return <SmallRef objRef={ref} />;
            }
            return <div>{datasetGroupName}</div>;
          },
        };
        datasetGroups.push(datasetColGroup);
        Object.entries(datasetGroup.scorerGroups).forEach(
          ([scorerGroupName, scorerGroup]) => {
            const scorerColGroup: GridColumnGroup = {
              groupId: `${datasetGroupName}--${scorerGroupName}`,
              headerName: scorerGroupName,
              children: [],
              renderHeaderGroup: params => {
                const ref = parseRefMaybe(
                  `weave:///${entity}/${project}/op/${scorerGroupName}` ?? ''
                );
                // console.log(node.headerName, ref);
                if (ref) {
                  return <SmallRef objRef={ref} />;
                }
                return <div>{scorerGroupName}</div>;
              },
            };
            datasetColGroup.children.push(scorerColGroup);
            Object.entries(scorerGroup.metricPathGroups).forEach(
              ([metricPathGroupName, metricPathGroup]) => {
                // const prefix = `${datasetGroupName}--${scorerGroupName}--`
                // const metricPathParts = metricPathGroupName.split('.');
                const targetParentGroup = scorerColGroup;
                // for (let i = 0; i < metricPathParts.length - 2; i++) {
                //   const part = metricPathParts[i];
                //   let existingChild = targetParentGroup.children.find(
                //     child => 'groupId' in child && child.groupId === part
                //   );
                //   if (!existingChild) {
                //     existingChild = {
                //       groupId: part,
                //       headerName: part,
                //       children: [],
                //     };
                //     targetParentGroup.children.push(existingChild);
                //   }
                //   targetParentGroup = existingChild as GridColumnGroup;
                // }
                // const finalPart = metricPathParts[metricPathParts.length - 1];
                const metricPathColGroup: GridLeafColumn = {
                  field: `${datasetGroupName}--${scorerGroupName}--${metricPathGroupName}`,
                };
                targetParentGroup.children.push(metricPathColGroup);
              }
            );

            // scorerColGroup.children = splitCommonRootLeafColumns(scorerColGroup.children as GridLeafColumn[], scorerColGroup.groupId);
          }
        );
      }
    );

    const finalGroupingModel = datasetGroups;

    // let finalGroupingModel: GridColumnGroupingModel = datasetGroups.filter(
    //   c => 'groupId' in c
    // ) as GridColumnGroup[];
    // finalGroupingModel = walkGroupingModel(finalGroupingModel, node => {
    //   if ('groupId' in node) {
    //     if (node.children.length === 1) {
    //       if (
    //         'groupId' in node.children[0] &&
    //         !node.headerName?.includes(':') &&
    //         !node.children[0].headerName?.includes(':')
    //       ) {
    //         const currNode = node;
    //         node = node.children[0];
    //         node.headerName = currNode.headerName + '.' + node.headerName;
    //       } else {
    //         // pass
    //         // node = node.children[0];
    //       }
    //     }
    //   }
    //   return node;
    // }) as GridColumnGroup[];
    // finalGroupingModel = walkGroupingModel(finalGroupingModel, node => {
    //   if ('groupId' in node) {
    //     node.renderHeaderGroup = params => {
    //       const ref = parseRefMaybe(
    //         `weave:///${entity}/${project}/object/${node.headerName}` ?? ''
    //       );
    //       // console.log(node.headerName, ref);
    //       if (ref) {
    //         return <SmallRef objRef={ref} />;
    //       }
    //       return <div>{node.headerName}</div>;
    //     };
    //   }
    //   return node;
    // }) as GridColumnGroup[];

    return finalGroupingModel;
  }, [columnStats.datasetGroups, entity, project]);

  const [sortModel, setSortModel] = useState<GridSortItem[]>([]);

  useEffect(() => {
    if (sortModel.length === 0 && columns.length > 1 && !loading) {
      setSortModel([{field: columns[1].field, sort: 'desc'}]);
    }
  }, [columns, loading, sortModel]);

  return (
    <Box
      sx={{
        height: '100%',
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}>
      <StyledDataGrid
        rows={rows}
        columns={columns}
        columnGroupingModel={groupingModel}
        disableRowSelectionOnClick
        hideFooterSelectedRowCount
        disableMultipleColumnsSorting={false}
        columnHeaderHeight={40}
        loading={loading}
        sortModel={sortModel}
        onSortModelChange={setSortModel}
        sx={{
          borderRadius: 0,
          '& .MuiDataGrid-footerContainer': {
            justifyContent: 'flex-start',
          },
          '& .MuiDataGrid-cell': {
            cursor: 'pointer',
          },
          flexGrow: 1,
          width: 'calc(100% + 1px)', // Add 1px to account for the right border
          '& .MuiDataGrid-main': {
            overflow: 'hidden',
          },
          '& .MuiDataGrid-virtualScroller': {
            overflow: 'auto',
          },
          '& .MuiDataGrid-columnHeaders': {
            overflow: 'hidden',
          },
        }}
        slots={{
          pagination: PaginationButtons,
        }}
      />
    </Box>
  );
};

type ColumnStats = {
  datasetGroups: {
    [datasetGroup: string]: {
      scorerGroups: {
        [scorerGroup: string]: {
          metricPathGroups: {
            [metricPathGroup: string]: {
              min: number;
              max: number;
              count: number;
            };
          };
        };
      };
    };
  };
};
const getColumnStats = (data: GroupedLeaderboardData): ColumnStats => {
  const stats: ColumnStats = {
    datasetGroups: {},
  };

  Object.values(data.modelGroups).forEach(modelGroup => {
    Object.entries(modelGroup.datasetGroups).forEach(
      ([datasetGroupName, datasetGroup]) => {
        if (stats.datasetGroups[datasetGroupName] == null) {
          stats.datasetGroups[datasetGroupName] = {
            scorerGroups: {},
          };
        }
        const currDatasetGroup = stats.datasetGroups[datasetGroupName];

        Object.entries(datasetGroup.scorerGroups).forEach(
          ([scorerGroupName, scorerGroup]) => {
            if (currDatasetGroup.scorerGroups[scorerGroupName] == null) {
              currDatasetGroup.scorerGroups[scorerGroupName] = {
                metricPathGroups: {},
              };
            }
            const currScorerGroup =
              currDatasetGroup.scorerGroups[scorerGroupName];
            Object.entries(scorerGroup.metricPathGroups).forEach(
              ([metricPathGroupName, metricPathGroup]) => {
                if (metricPathGroup.length === 0) {
                  return;
                }
                const metricValue = getAggregatedResults(metricPathGroup)
                  ?.metricValue as number;
                if (
                  currScorerGroup.metricPathGroups[metricPathGroupName] == null
                ) {
                  currScorerGroup.metricPathGroups[metricPathGroupName] = {
                    min: metricValue,
                    max: metricValue,
                    count: metricPathGroup.length,
                  };
                } else {
                  currScorerGroup.metricPathGroups[metricPathGroupName].min =
                    Math.min(
                      currScorerGroup.metricPathGroups[metricPathGroupName].min,
                      metricValue
                    );
                  currScorerGroup.metricPathGroups[metricPathGroupName].max =
                    Math.max(
                      currScorerGroup.metricPathGroups[metricPathGroupName].max,
                      metricValue
                    );
                  currScorerGroup.metricPathGroups[
                    metricPathGroupName
                  ].count += 1;
                }
              }
            );
          }
        );
      }
    );
  });

  return stats;
};

const valueFromRowData = (
  rowData: RowData,
  datasetGroupName: string,
  scorerGroupName: string,
  metricPathGroupName: string
): number | string | boolean | null | undefined | Date => {
  return getAggregatedResults(
    recordsFromRowData(
      rowData,
      datasetGroupName,
      scorerGroupName,
      metricPathGroupName
    )
  )?.metricValue;
};

const recordFromRowData = (
  rowData: RowData,
  datasetGroupName: string,
  scorerGroupName: string,
  metricPathGroupName: string
): LeaderboardValueRecord | null => {
  return getAggregatedResults(
    recordsFromRowData(
      rowData,
      datasetGroupName,
      scorerGroupName,
      metricPathGroupName
    )
  );
};

const recordsFromRowData = (
  rowData: RowData,
  datasetGroupName: string,
  scorerGroupName: string,
  metricPathGroupName: string
): LeaderboardValueRecord[] => {
  return (
    rowData.modelGroup.datasetGroups[datasetGroupName]?.scorerGroups[
      scorerGroupName
    ]?.metricPathGroups[metricPathGroupName] ?? []
  );
};

const getAggregatedResults = (
  data: null | LeaderboardValueRecord[]
): LeaderboardValueRecord | null => {
  if (data == null || data.length === 0) {
    return null;
  }
  if (data.length === 1) {
    return data[0];
  }
  return data.sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime())[0];
};

const defaultGetSortComparator =
  (dir: GridSortDirection) => (a: any, b: any) => {
    const aValue = a;
    const bValue = b;
    if (aValue == null && bValue == null) {
      return 0;
    }
    // Ignoring direction here allows nulls to always sort to the end
    if (aValue == null) {
      return 1;
    }
    if (bValue == null) {
      return -1;
    }
    if (typeof aValue === 'number' && typeof bValue === 'number') {
      if (dir === 'asc') {
        return aValue - bValue;
      } else {
        return bValue - aValue;
      }
    }
    return aValue.localeCompare(bValue);
  };

// const walkGroupingModel = (
//   nodes: GridColumnNode[],
//   fn: (node: GridColumnNode) => GridColumnNode
// ) => {
//   return nodes.map(node => {
//     if ('children' in node) {
//       node.children = walkGroupingModel(node.children, fn);
//     }
//     return fn(node);
//   });
// };

// // TODO: refactor to accumulate common root columns in a single pass
//   const splitCommonRootLeafColumns = (columns: GridLeafColumn[], groupIdPrefix: string, depth: number = 0): GridColumnNode[] => {
//     if (columns.length < 2) {
//       return columns;
//     }
//     const groups: {[key: string]: GridLeafColumn[]} = {};
//     columns.forEach(col => {
//       const key = col.field.split('.')[depth];
//       if (groups[key] == null) {
//         groups[key] = [];
//       }
//       groups[key].push(col);
//     });

//     return Object.entries(groups).map(([key, group]) => {
//       if (group.length === 1) {
//         return group[0];
//       }
//       const newGroupId = `${groupIdPrefix}.${key}`

//       const groupCol: GridColumnGroup = {
//         groupId: newGroupId,
//         headerName: key,
//         renderHeaderGroup: params => {
//           return <div>{key}</div>
//         },
//         children: splitCommonRootLeafColumns(group, newGroupId, depth + 1),
//       };
//       return groupCol;
//     });
//   }

// TODO:
// Trials Column
// Cost Column
// Date column
