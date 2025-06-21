import {Box, Tooltip} from '@mui/material';
import {
  GridColDef,
  GridColumnGroup,
  GridLeafColumn,
  GridRenderCellParams,
  GridSortDirection,
  GridSortItem,
} from '@mui/x-data-grid-pro';
import {Checkbox} from '@wandb/weave/components/Checkbox';
import {Loading} from '@wandb/weave/components/Loading';
import {Timestamp} from '@wandb/weave/components/Timestamp';
import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {useHistory} from 'react-router-dom';

import {parseRefMaybe} from '../../../../../../react';
import {useWeaveflowRouteContext} from '../../context';
import {NotApplicable} from '../../NotApplicable';
import {PaginationButtons} from '../../pages/CallsPage/CallsTableButtons';
import {Empty} from '../../pages/common/Empty';
import {EMPTY_PROPS_LEADERBOARD} from '../../pages/common/EmptyContent';
import {StatusChip} from '../../pages/common/StatusChip';
import {SmallRef} from '../../smallRef/SmallRef';
import {StyledDataGrid} from '../../StyledDataGrid';
import {
  GroupedLeaderboardData,
  GroupedLeaderboardModelGroup,
  LeaderboardValueRecord,
} from './query/leaderboardQuery';

const USE_COMPARE_EVALUATIONS_PAGE = true;
const MAX_SELECT = 100;

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
  selectedEvaluations?: string[];
  onSelectedEvaluationsChange?: (evaluations: string[]) => void;
  allRecords?: LeaderboardValueRecord[];
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
  selectedEvaluations: controlledSelectedEvaluations,
  onSelectedEvaluationsChange,
  allRecords = [],
}) => {
  const {peekingRouter} = useWeaveflowRouteContext();
  const history = useHistory();

  // Internal state for uncontrolled mode
  const [internalSelectedEvaluations, setInternalSelectedEvaluations] =
    useState<string[]>([]);

  // Use controlled value if provided, otherwise use internal state
  const isControlled = controlledSelectedEvaluations !== undefined;
  const selectedEvaluations = isControlled
    ? controlledSelectedEvaluations
    : internalSelectedEvaluations;

  const setSelectedEvaluations = useCallback(
    (evaluations: string[]) => {
      if (isControlled && onSelectedEvaluationsChange) {
        onSelectedEvaluationsChange(evaluations);
      } else {
        setInternalSelectedEvaluations(evaluations);
      }
    },
    [isControlled, onSelectedEvaluationsChange]
  );

  const onCellClick = useCallback(
    (record: LeaderboardValueRecord, event: React.MouseEvent) => {
      const sourceCallId = record.sourceEvaluationCallId;
      if (sourceCallId) {
        const isMultiSelect = event.altKey || event.metaKey;

        if (isMultiSelect) {
          // Toggle selection using alt/option key
          if (selectedEvaluations.includes(sourceCallId)) {
            // Remove from selection
            setSelectedEvaluations(
              selectedEvaluations.filter(id => id !== sourceCallId)
            );
          } else {
            // Add to selection (enforce MAX_SELECT limit)
            if (selectedEvaluations.length < MAX_SELECT) {
              setSelectedEvaluations([...selectedEvaluations, sourceCallId]);
            }
          }
        } else if (selectedEvaluations.length === 0) {
          // Single selection - navigate immediately only if no selections
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
      }
    },
    [
      entity,
      history,
      peekingRouter,
      project,
      selectedEvaluations,
      setSelectedEvaluations,
    ]
  );

  const columnStats = useMemo(() => getColumnStats(data), [data]);

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
    Object.entries(data.modelGroups).forEach(([modelGroupName, modelGroup]) => {
      rowData.push({
        id: modelGroupName,
        modelGroupName,
        modelGroup,
      });
    });
    return rowData;
  }, [data]);

  // Get all evaluation IDs from the current row data using allRecords
  const getAllEvaluationIds = useCallback(
    (row: RowData): string[] => {
      const modelGroupName = row.modelGroupName;

      // Split modelGroupName into name and version parts
      const [modelName, modelVersion] = modelGroupName.includes(':')
        ? modelGroupName.split(':')
        : [modelGroupName, undefined];

      // Filter records by both modelName and modelVersion
      const matchingRecords = allRecords.filter(record => {
        if (!record.sourceEvaluationCallId) return false;

        // Check if model name matches
        if (record.modelName !== modelName) return false;

        // If we have a version in the group name, check if it matches
        if (modelVersion && record.modelVersion !== modelVersion) return false;

        return true;
      });

      return [
        ...new Set(
          matchingRecords.map(record => record.sourceEvaluationCallId)
        ),
      ];
    },
    [allRecords]
  );

  // Get all available evaluation IDs from all rows
  const allAvailableEvaluationIds = useMemo(() => {
    return [
      ...new Set(
        allRecords.map(record => record.sourceEvaluationCallId).filter(Boolean)
      ),
    ];
  }, [allRecords]);

  const columns: Array<GridColDef<RowData>> = useMemo(
    () => [
      {
        minWidth: 35,
        width: 35,
        field: 'CustomCheckbox',
        sortable: false,
        disableColumnMenu: true,
        resizable: false,
        disableExport: true,
        display: 'flex',
        renderHeader: (params: any) => {
          const isAllSelected =
            selectedEvaluations.length === allAvailableEvaluationIds.length &&
            allAvailableEvaluationIds.length > 0;
          const isSomeSelected =
            selectedEvaluations.length > 0 &&
            selectedEvaluations.length < allAvailableEvaluationIds.length;

          return (
            <Checkbox
              size="small"
              checked={
                selectedEvaluations.length === 0
                  ? false
                  : selectedEvaluations.length ===
                    allAvailableEvaluationIds.length
                  ? true
                  : 'indeterminate'
              }
              onCheckedChange={() => {
                if (isAllSelected || isSomeSelected) {
                  // Deselect all
                  setSelectedEvaluations([]);
                } else {
                  // Select all (up to MAX_SELECT)
                  setSelectedEvaluations(
                    allAvailableEvaluationIds.slice(0, MAX_SELECT)
                  );
                }
              }}
            />
          );
        },
        renderCell: (params: GridRenderCellParams) => {
          const row = params.row as RowData;
          const rowEvaluationIds = getAllEvaluationIds(row);
          const isSelected = rowEvaluationIds.some(id =>
            selectedEvaluations.includes(id)
          );
          const disabled =
            !isSelected && selectedEvaluations.length >= MAX_SELECT;
          const tooltipText =
            selectedEvaluations.length >= MAX_SELECT && !isSelected
              ? `Selection limited to ${MAX_SELECT} items`
              : '';

          return (
            <Tooltip title={tooltipText} placement="right" arrow>
              {/* https://mui.com/material-ui/react-tooltip/ */}
              {/* By default disabled elements like <button> do not trigger user interactions */}
              {/* To accommodate disabled elements, add a simple wrapper element, such as a span. */}
              <span style={{marginLeft: 'auto', marginRight: 'auto'}}>
                <Checkbox
                  size="small"
                  disabled={disabled}
                  checked={isSelected}
                  onCheckedChange={() => {
                    if (isSelected) {
                      // Remove all evaluation IDs from this row
                      setSelectedEvaluations(
                        selectedEvaluations.filter(
                          id => !rowEvaluationIds.includes(id)
                        )
                      );
                    } else {
                      // Add all evaluation IDs from this row
                      const newSelection = [
                        ...selectedEvaluations,
                        ...rowEvaluationIds,
                      ];
                      setSelectedEvaluations(
                        [...new Set(newSelection)].slice(0, MAX_SELECT)
                      );
                    }
                  }}
                />
              </span>
            </Tooltip>
          );
        },
      },
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
            }`
          );

          // Check if any evaluation for this model is running
          const modelGroup = (params.row as RowData).modelGroup;
          const isRunning = modelHasRunningEvaluation(modelGroup);

          if (modelRef) {
            return (
              <div
                style={{
                  width: 'max-content',
                  height: '100%',
                  alignContent: 'center',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  lineHeight: '20px',
                  marginLeft: '10px',
                  gap: '8px',
                }}>
                <SmallRef objRef={modelRef} />
                {isRunning && (
                  <StatusChip
                    value="running"
                    iconOnly
                    tooltipOverride="Evaluation in progress"
                  />
                )}
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
                      const isSelected =
                        record?.sourceEvaluationCallId &&
                        selectedEvaluations.includes(
                          record.sourceEvaluationCallId
                        );
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
                          onClick={e => record && onCellClick(record, e)}>
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
                              cursor:
                                selectedEvaluations.length > 0
                                  ? 'default'
                                  : 'pointer',
                              border: isSelected ? '2px solid #13A9BA' : 'none',
                              boxSizing: 'border-box',
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
    [
      columnStats.datasetGroups,
      entity,
      getColorForScore,
      onCellClick,
      project,
      selectedEvaluations,
      allAvailableEvaluationIds,
      getAllEvaluationIds,
      setSelectedEvaluations,
    ]
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
              `weave:///${entity}/${project}/object/${datasetGroupName}`
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
                const ref = parseRefMaybe(
                  `weave:///${entity}/${project}/op/${scorerGroupName}`
                );
                if (ref) {
                  return <SmallRef objRef={ref} />;
                }
                return <div>{scorerGroupName}</div>;
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
  }, [columnStats.datasetGroups, entity, project]);

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

  const sortModelInitialized = useRef(false);

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
    if (columns.length > 1 && !loading && !sortModelInitialized.current) {
      setSortModel(defaultSortModel);
      sortModelInitialized.current = true;
    }
  }, [columns.length, defaultSortModel, loading]);

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
        rowHeight={38}
        loading={loading}
        sortModel={sortModel}
        onSortModelChange={setSortModel}
        pinnedColumns={{left: ['CustomCheckbox']}}
        sx={{
          borderRadius: 0,
          '& .MuiDataGrid-footerContainer': {
            justifyContent: 'flex-start',
          },
          '& .MuiDataGrid-main:focus-visible': {
            outline: 'none',
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

/**
 * Check if a model group has any running evaluations.
 */
const modelHasRunningEvaluation = (
  modelGroup: GroupedLeaderboardModelGroup
) => {
  try {
    for (const datasetGroup of Object.values(modelGroup.datasetGroups)) {
      for (const scorerGroup of Object.values(datasetGroup.scorerGroups)) {
        for (const metricPathGroup of Object.values(
          scorerGroup.metricPathGroups
        )) {
          for (const record of metricPathGroup) {
            if (record.isRunning) {
              return true;
            }
          }
        }
      }
    }
  } catch (e) {
    console.log(e);
  }
  return false;
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
