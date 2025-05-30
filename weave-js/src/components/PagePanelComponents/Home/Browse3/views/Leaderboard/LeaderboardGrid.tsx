import {Alert, Box, Tooltip} from '@mui/material';
import {
  GridColDef,
  GridColumnGroup,
  GridLeafColumn,
  GridRenderCellParams,
  GridSortDirection,
  GridSortItem,
} from '@mui/x-data-grid-pro';
import {Loading} from '@wandb/weave/components/Loading';
import {Timestamp} from '@wandb/weave/components/Timestamp';
import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {useHistory} from 'react-router-dom';

import {parseRefMaybe} from '../../../../../../react';
import {useWeaveflowRouteContext} from '../../context';
import {NotApplicable} from '../../NotApplicable';
import {PaginationButtons} from '../../pages/CallsPage/CallsTableButtons';
import {Empty} from '../../pages/common/Empty';
import {EMPTY_PROPS_LEADERBOARD} from '../../pages/common/EmptyContent';
import {SmallRef} from '../../smallRef/SmallRef';
import {StyledDataGrid} from '../../StyledDataGrid';
import {
  GroupedLeaderboardData,
  GroupedLeaderboardModelGroup,
  LeaderboardValueRecord,
} from './query/leaderboardQuery';

const USE_COMPARE_EVALUATIONS_PAGE = true;
export type LeaderboardColumnOrderType = Array<{
  datasetGroup: string;
  scorerGroup: string;
  metricGroup: string;
  minimize: boolean;
}>;
interface LeaderboardGridProps {
  entity: string;
  project: string;
  data: GroupedLeaderboardData;
  columnOrder?: LeaderboardColumnOrderType;
  loading: boolean;
  hideFooter?: boolean;
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
  columnOrder,
  hideFooter,
}) => {
  const {peekingRouter} = useWeaveflowRouteContext();
  const history = useHistory();
  const onCellClick = useCallback(
    (record: LeaderboardValueRecord) => {
      const sourceCallId = record.sourceEvaluationCallId;
      if (sourceCallId) {
        let to: string;
        if (USE_COMPARE_EVALUATIONS_PAGE) {
          to = peekingRouter.compareEvaluationsUri(
            entity,
            project,
            [sourceCallId],
            null
          );
        } else {
          to = peekingRouter.callUIUrl(entity, project, '', sourceCallId);
        }
        history.push(to);
      }
    },
    [entity, history, peekingRouter, project]
  );

  // Process data to group scorers by name only (without version)
  const processedData = useMemo(() => {
    const newData: GroupedLeaderboardData = {modelGroups: {}};
    const scorerVersionMap: {[datasetGroup: string]: {[scorerName: string]: Set<string>}} = {};
    const scorerLatestVersionMap: {[datasetGroup: string]: {[scorerName: string]: string}} = {};
    
    // Process each model group
    Object.entries(data.modelGroups).forEach(([modelGroup, modelData]) => {
      newData.modelGroups[modelGroup] = {datasetGroups: {}};
      
      Object.entries(modelData.datasetGroups).forEach(([datasetGroup, datasetData]) => {
        newData.modelGroups[modelGroup].datasetGroups[datasetGroup] = {scorerGroups: {}};
        if (!scorerVersionMap[datasetGroup]) {
          scorerVersionMap[datasetGroup] = {};
        }
        if (!scorerLatestVersionMap[datasetGroup]) {
          scorerLatestVersionMap[datasetGroup] = {};
        }
        
        Object.entries(datasetData.scorerGroups).forEach(([scorerGroup, scorerData]) => {
          // Extract scorer name and version from scorerGroup (format: "name:version" or just "name")
          const colonIndex = scorerGroup.lastIndexOf(':');
          let scorerName: string;
          let scorerVersion: string;
          
          if (colonIndex !== -1 && scorerGroup !== 'Summary') {
            scorerName = scorerGroup.substring(0, colonIndex);
            scorerVersion = scorerGroup.substring(colonIndex + 1);
          } else {
            // No version found (e.g., "Summary" scorer)
            scorerName = scorerGroup;
            scorerVersion = '';
          }
          
          // Track scorer versions
          if (!scorerVersionMap[datasetGroup][scorerName]) {
            scorerVersionMap[datasetGroup][scorerName] = new Set();
          }
          if (scorerVersion) {
            scorerVersionMap[datasetGroup][scorerName].add(scorerVersion);
            // Store the latest version we've seen (this will be overwritten as we process more)
            scorerLatestVersionMap[datasetGroup][scorerName] = scorerVersion;
          }
          
          // Group by scorer name only
          if (!newData.modelGroups[modelGroup].datasetGroups[datasetGroup].scorerGroups[scorerName]) {
            newData.modelGroups[modelGroup].datasetGroups[datasetGroup].scorerGroups[scorerName] = {
              metricPathGroups: {}
            };
          }
          
          // Merge metric path groups
          Object.entries(scorerData.metricPathGroups).forEach(([metricPath, records]) => {
            const targetScorerGroup = newData.modelGroups[modelGroup].datasetGroups[datasetGroup].scorerGroups[scorerName];
            if (!targetScorerGroup.metricPathGroups[metricPath]) {
              targetScorerGroup.metricPathGroups[metricPath] = [];
            }
            targetScorerGroup.metricPathGroups[metricPath].push(...records);
          });
        });
      });
    });
    
    return {processedData: newData, scorerVersionMap, scorerLatestVersionMap};
  }, [data]);

  const columnStats = useMemo(() => getColumnStats(processedData.processedData), [processedData]);

  const getColorForScore = useCallback(
    (datasetGroup, scorerGroup, metricPathGroup, score) => {
      if (['Trials', 'Run Date'].includes(metricPathGroup)) {
        return 'transparent';
      }
      const shouldMinimize =
        ['Avg. Latency'].includes(metricPathGroup) ||
        columnStats.datasetGroups[datasetGroup].scorerGroups[scorerGroup]
          .metricPathGroups[metricPathGroup].shouldMinimize;
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
      return `hsl(${30 + 100 * normalizedScore}, 70%, 85%)`;
    },
    [columnStats.datasetGroups]
  );

  const rows: RowData[] = useMemo(() => {
    const rowData: RowData[] = [];
    Object.entries(processedData.processedData.modelGroups).forEach(([modelGroupName, modelGroup]) => {
      rowData.push({
        id: modelGroupName,
        modelGroupName,
        modelGroup,
      });
    });
    return rowData;
  }, [processedData]);

  const columns: Array<GridColDef<RowData>> = useMemo(
    () => [
      {
        field: 'modelGroupName',
        headerName: 'Model',
        minWidth: 150,
        flex: 1,
        renderCell: (params: GridRenderCellParams) => {
          const isOp = modelGroupIsOp((params.row as RowData).modelGroup);
          const modelRef = parseRefMaybe(
            `weave:///${entity}/${project}/${isOp ? 'op' : 'object'}/${
              params.value
            }` ?? ''
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
                  marginLeft: '10px',
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
                        if (
                          (0 < inner && inner < 1) ||
                          metricPathGroupName.includes('fraction')
                        ) {
                          inner = `${(inner * 100).toFixed(2)}%`;
                        } else {
                          inner = `${inner.toFixed(2)}`;
                        }
                      } else if (value instanceof Date) {
                        return (inner = (
                          <Timestamp
                            value={value.getTime() / 1000}
                            format="relative"
                          />
                        ));
                      } else {
                        inner = JSON.stringify(params.value);
                      }
                      return (
                        <div
                          className="noPad"
                          style={{
                            width: '100%',
                            height: '100%',
                            overflow: 'hidden',
                            padding: '2px',
                          }}
                          onClick={() => record && onCellClick(record)}>
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
                              borderRadius: '4px',
                              backgroundColor: getColorForScore(
                                datasetGroupName,
                                scorerGroupName,
                                metricPathGroupName,
                                value
                              ),
                            }}>
                            {inner}
                          </div>
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
          freeReordering: true,
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
              freeReordering: true,
              children: [],
              renderHeaderGroup: params => {
                // Check if there are multiple versions for this scorer
                const versions = processedData.scorerVersionMap[datasetGroupName]?.[scorerGroupName];
                const hasMultipleVersions = versions && versions.size > 1;
                const scorerVersion = processedData.scorerLatestVersionMap[datasetGroupName]?.[scorerGroupName];
                
                const ref = scorerVersion 
                  ? parseRefMaybe(`weave:///${entity}/${project}/op/${scorerGroupName}:${scorerVersion}`)
                  : null;
                
                return (
                  <div style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
                    {hasMultipleVersions ? (
                      <>
                        <div>{scorerGroupName}</div>
                        <Tooltip title={`This scorer has ${versions.size} different versions across evaluations. Take precaution when comparing results.`}>
                          <Alert
                            severity="warning"
                            style={{
                              padding: '2px 8px',
                              fontSize: '11px',
                            }}>
                            Scoring inconsistency detected
                          </Alert>
                        </Tooltip>
                      </>
                    ) : (
                      ref ? (
                        <SmallRef objRef={ref} />
                      ) : (
                        <div>{scorerGroupName}</div>
                      )
                    )}
                  </div>
                );
              },
            };
            datasetColGroup.children.push(scorerColGroup);
            Object.keys(scorerGroup.metricPathGroups).forEach(
              metricPathGroupName => {
                const metricPathColGroup: GridLeafColumn = {
                  field: `${datasetGroupName}--${scorerGroupName}--${metricPathGroupName}`,
                };
                scorerColGroup.children.push(metricPathColGroup);
              }
            );
          }
        );
      }
    );

    const finalGroupingModel = datasetGroups;

    return finalGroupingModel;
  }, [columnStats.datasetGroups, entity, project, processedData.scorerVersionMap, processedData.scorerLatestVersionMap]);

  const [sortModel, setSortModel] = useState<GridSortItem[]>([]);

  const orderedColumns = useMemo(() => {
    if (!columnOrder) {
      return columns;
    }
    const columnOrderKeys = columnOrder.map(
      c => `${c.datasetGroup}--${c.scorerGroup}--${c.metricGroup}`
    );
    return columns.sort((a, b) => {
      return (
        columnOrderKeys.indexOf(a.field) - columnOrderKeys.indexOf(b.field)
      );
    });
  }, [columns, columnOrder]);

  const defaultSortModel: GridSortItem[] = useMemo(() => {
    if (!columnOrder) {
      return columns.map(c => ({field: c.field, sort: 'desc'}));
    } else {
      return columnOrder.map(c => ({
        field: `${c.datasetGroup}--${c.scorerGroup}--${c.metricGroup}`,
        sort: c.minimize ? 'asc' : 'desc',
      }));
    }
  }, [columnOrder, columns]);

  useEffect(() => {
    if (columns.length > 1 && !loading) {
      setSortModel(defaultSortModel);
    }
  }, [columns, defaultSortModel, loading]);

  if (loading) {
    return <Loading centered />;
  }

  if (rows.length === 0) {
    return (
      <Box
        sx={{
          height: '100%',
          width: '100%',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}>
        <Empty {...EMPTY_PROPS_LEADERBOARD} />
      </Box>
    );
  }

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
        columns={orderedColumns}
        columnGroupingModel={groupingModel}
        disableRowSelectionOnClick
        disableColumnReorder
        hideFooterSelectedRowCount
        disableMultipleColumnsSorting={false}
        columnHeaderHeight={40}
        rowHeight={40}
        loading={loading}
        sortModel={sortModel}
        onSortModelChange={setSortModel}
        hideFooter={hideFooter}
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
          '& [role="gridcell"]': {
            padding: 0,
          },
        }}
        slots={{
          pagination: () => <PaginationButtons />,
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
              shouldMinimize: boolean;
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
                    shouldMinimize: metricPathGroup[0].shouldMinimize ?? false,
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

/**
 * Check if a model group is an op. This is a little hacky - we just look
 * at the first entry down the chain and see if it's an op.
 */
const modelGroupIsOp = (modelGroup: GroupedLeaderboardModelGroup) => {
  let isOp = false;
  try {
    isOp =
      Object.values(
        Object.values(
          Object.values(modelGroup.datasetGroups)[0].scorerGroups
        )[0].metricPathGroups
      )[0][0].modelType === 'op';
  } catch (e) {
    console.log(e);
  }
  return isOp;
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
