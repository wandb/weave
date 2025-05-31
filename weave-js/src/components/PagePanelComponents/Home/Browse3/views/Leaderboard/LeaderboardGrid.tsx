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
import {StatusChip} from '../../pages/common/StatusChip';
import {useGetTraceServerClientContext} from '../../pages/wfReactInterface/traceServerClientContext';
import {ComputedCallStatusType} from '../../pages/wfReactInterface/traceServerClientTypes';
import {projectIdFromParts} from '../../pages/wfReactInterface/tsDataModelHooks';
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

// Hook to fetch call statuses for evaluation calls
const useEvaluationCallStatuses = (
  entity: string,
  project: string,
  data: GroupedLeaderboardData
): Record<string, ComputedCallStatusType> => {
  const getClient = useGetTraceServerClientContext();
  const [callStatuses, setCallStatuses] = useState<
    Record<string, ComputedCallStatusType>
  >({});

  useEffect(() => {
    // Extract all unique evaluation call IDs from the data
    const callIds = new Set<string>();
    Object.values(data.modelGroups).forEach(modelGroup => {
      Object.values(modelGroup.datasetGroups).forEach(datasetGroup => {
        Object.values(datasetGroup.scorerGroups).forEach(scorerGroup => {
          Object.values(scorerGroup.metricPathGroups).forEach(records => {
            records.forEach(record => {
              if (record.sourceEvaluationCallId) {
                callIds.add(record.sourceEvaluationCallId);
              }
            });
          });
        });
      });
    });

    if (callIds.size === 0) {
      setCallStatuses({});
      return;
    }

    const client = getClient();
    const fetchCallStatuses = async () => {
      try {
        const callIdsArray = Array.from(callIds);
        const response = await client.callsStreamQuery({
          project_id: projectIdFromParts({entity, project}),
          filter: {
            call_ids: callIdsArray,
          },
          limit: callIdsArray.length,
        });

        const statuses: Record<string, ComputedCallStatusType> = {};
        response.calls.forEach(call => {
          // Extract status from the call summary or default to 'success' if finished
          const status =
            call.summary?.status || (call.ended_at ? 'success' : 'running');
          statuses[call.id] = status;
        });

        setCallStatuses(statuses);
      } catch (error) {
        console.error('Error fetching call statuses:', error);
        setCallStatuses({});
      }
    };

    fetchCallStatuses();
  }, [entity, project, data, getClient]);

  return callStatuses;
};

// Helper function to get the latest evaluation status for a model
const getLatestEvaluationStatus = (
  modelGroup: GroupedLeaderboardModelGroup,
  callStatuses: Record<string, ComputedCallStatusType>
): ComputedCallStatusType | null => {
  let latestRecord: LeaderboardValueRecord | null = null;
  let latestCreatedAt = new Date(0);

  // Find the latest evaluation record for this model
  Object.values(modelGroup.datasetGroups).forEach(datasetGroup => {
    Object.values(datasetGroup.scorerGroups).forEach(scorerGroup => {
      Object.values(scorerGroup.metricPathGroups).forEach(records => {
        records.forEach(record => {
          if (record.createdAt.getTime() > latestCreatedAt.getTime()) {
            latestCreatedAt = record.createdAt;
            latestRecord = record;
          }
        });
      });
    });
  });

  if (latestRecord && latestRecord.sourceEvaluationCallId) {
    return callStatuses[latestRecord.sourceEvaluationCallId] || null;
  }

  return null;
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
  const callStatuses = useEvaluationCallStatuses(entity, project, data);
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

  // Process data to group scorers by name only (without version) and optionally group datasets
  const processedData = useMemo(() => {
    const newData: GroupedLeaderboardData = {modelGroups: {}};
    const scorerVersionMap: {
      [datasetGroup: string]: {[scorerName: string]: Set<string>};
    } = {};
    const scorerLatestVersionMap: {
      [datasetGroup: string]: {[scorerName: string]: string};
    } = {};
    const datasetVersionMap: {[datasetName: string]: Set<string>} = {};
    const datasetLatestVersionMap: {[datasetName: string]: string} = {};
    // Global scorer version tracking (since scorers are not dataset-specific)
    const globalScorerVersionMap: {[scorerName: string]: Set<string>} = {};
    const globalScorerLatestVersionMap: {[scorerName: string]: string} = {};
    // Track whether each scorer is an op or object
    const globalScorerTypeMap: {[scorerName: string]: 'op' | 'object'} = {};

    // Helper function to get the latest record from a list based on createdAt
    const getLatestRecord = (
      records: LeaderboardValueRecord[]
    ): LeaderboardValueRecord | null => {
      if (!records || records.length === 0) return null;
      return records.sort(
        (a, b) => b.createdAt.getTime() - a.createdAt.getTime()
      )[0];
    };

    // Helper function to get latest evaluation records per model for a specific metric
    const getLatestEvaluationsPerModel = (
      records: LeaderboardValueRecord[]
    ): LeaderboardValueRecord[] => {
      const modelGroups = new Map<string, LeaderboardValueRecord[]>();

      // Group by model
      records.forEach(record => {
        const modelKey = `${record.modelName}:${record.modelVersion}`;
        if (!modelGroups.has(modelKey)) {
          modelGroups.set(modelKey, []);
        }
        modelGroups.get(modelKey)!.push(record);
      });

      // Get latest evaluation for each model
      const latestRecords: LeaderboardValueRecord[] = [];
      modelGroups.forEach(modelRecords => {
        const latest = getLatestRecord(modelRecords);
        if (latest) {
          latestRecords.push(latest);
        }
      });

      return latestRecords;
    };

    // First pass: collect all dataset versions and determine grouping
    const datasetGroupToName: {[datasetGroup: string]: string} = {};
    Object.entries(data.modelGroups).forEach(([modelGroup, modelData]) => {
      Object.entries(modelData.datasetGroups).forEach(
        ([datasetGroup, datasetData]) => {
          // Extract dataset name and version from datasetGroup
          // Format can be either "name:version" or just "name" (when already grouped)
          const colonIndex = datasetGroup.lastIndexOf(':');
          let datasetName: string;

          if (colonIndex !== -1) {
            datasetName = datasetGroup.substring(0, colonIndex);
          } else {
            // Already grouped by name only
            datasetName = datasetGroup;
          }

          datasetGroupToName[datasetGroup] = datasetName;
        }
      );
    });

    // Collect all records across all models/datasets/scorers/metrics
    const allRecords: LeaderboardValueRecord[] = [];
    Object.entries(data.modelGroups).forEach(([modelGroup, modelData]) => {
      Object.entries(modelData.datasetGroups).forEach(
        ([datasetGroup, datasetData]) => {
          Object.entries(datasetData.scorerGroups).forEach(
            ([scorerGroup, scorerData]) => {
              Object.entries(scorerData.metricPathGroups).forEach(
                ([metricPath, records]) => {
                  allRecords.push(...records);
                }
              );
            }
          );
        }
      );
    });

    // First pass: collect scorer types and versions from ALL records
    // This ensures we capture scorers that might not be in the latest evaluations
    console.log('Total records to process:', allRecords.length);
    const scorerRecordCounts: {[key: string]: number} = {};
    allRecords.forEach(record => {
      const scorerName = record.scorerName;
      const scorerVersion = record.scorerVersion;
      const scorerType = record.scorerType;

      // Count records per scorer
      scorerRecordCounts[scorerName] =
        (scorerRecordCounts[scorerName] || 0) + 1;

      // Debug specific scorers
      if (
        (scorerName === 'ResponseQualityScorer' ||
          scorerName === 'tool_usage_scorer') &&
        scorerRecordCounts[scorerName] <= 3
      ) {
        console.log(`First pass - ${scorerName} record:`, {
          scorerName,
          scorerVersion,
          scorerType,
          hasVersion: !!scorerVersion,
          hasType: !!scorerType,
          metricType: record.metricType,
        });
      }

      // Track scorer versions and types globally
      if (scorerVersion && scorerType) {
        if (!globalScorerVersionMap[scorerName]) {
          globalScorerVersionMap[scorerName] = new Set();
        }
        globalScorerVersionMap[scorerName].add(scorerVersion);
        // Keep the latest version we see (by record date)
        if (
          !globalScorerLatestVersionMap[scorerName] ||
          record.createdAt >
            (allRecords.find(
              r =>
                r.scorerName === scorerName &&
                r.scorerVersion === globalScorerLatestVersionMap[scorerName]
            )?.createdAt || new Date(0))
        ) {
          globalScorerLatestVersionMap[scorerName] = scorerVersion;
        }

        // Track scorer type
        if (scorerType) {
          globalScorerTypeMap[scorerName] = scorerType;
        }
      }
    });

    // Filter to latest evaluations per model to check for inconsistencies
    const latestRecordsOnly = getLatestEvaluationsPerModel(allRecords);

    // Second pass: track dataset and scorer versions only from latest evaluations for inconsistency detection
    console.log('Processing latest records:', latestRecordsOnly.length);
    console.log('Global scorer versions found:', globalScorerVersionMap);
    console.log('Global scorer types found:', globalScorerTypeMap);
    latestRecordsOnly.forEach(record => {
      const datasetName = record.datasetName;
      const datasetVersion = record.datasetVersion;

      // Track dataset versions only from latest evaluations
      if (!datasetVersionMap[datasetName]) {
        datasetVersionMap[datasetName] = new Set();
      }
      if (datasetVersion) {
        datasetVersionMap[datasetName].add(datasetVersion);
        datasetLatestVersionMap[datasetName] = datasetVersion;
      }

      // Track scorer versions only from latest evaluations
      if (!scorerVersionMap[datasetName]) {
        scorerVersionMap[datasetName] = {};
      }
      if (!scorerLatestVersionMap[datasetName]) {
        scorerLatestVersionMap[datasetName] = {};
      }

      const scorerName = record.scorerName;
      const scorerVersion = record.scorerVersion;

      if (!scorerVersionMap[datasetName][scorerName]) {
        scorerVersionMap[datasetName][scorerName] = new Set();
      }
      if (scorerVersion) {
        scorerVersionMap[datasetName][scorerName].add(scorerVersion);
        // Track the latest version we see
        scorerLatestVersionMap[datasetName][scorerName] = scorerVersion;
      }
    });

    // Process each model group and group datasets by name
    Object.entries(data.modelGroups).forEach(([modelGroup, modelData]) => {
      newData.modelGroups[modelGroup] = {datasetGroups: {}};

      Object.entries(modelData.datasetGroups).forEach(
        ([datasetGroup, datasetData]) => {
          const datasetName = datasetGroupToName[datasetGroup];

          // Use dataset name as the group key (without version)
          if (!newData.modelGroups[modelGroup].datasetGroups[datasetName]) {
            newData.modelGroups[modelGroup].datasetGroups[datasetName] = {
              scorerGroups: {},
            };
          }

          Object.entries(datasetData.scorerGroups).forEach(
            ([scorerGroup, scorerData]) => {
              // Extract scorer name and version from scorerGroup (format: "name:version" or just "name")
              const colonIndex = scorerGroup.lastIndexOf(':');
              let scorerName: string;

              if (colonIndex !== -1 && scorerGroup !== 'Summary') {
                scorerName = scorerGroup.substring(0, colonIndex);
              } else {
                // No version found (e.g., "Summary" scorer)
                scorerName = scorerGroup;
              }

              // Group by scorer name only
              if (
                !newData.modelGroups[modelGroup].datasetGroups[datasetName]
                  .scorerGroups[scorerName]
              ) {
                newData.modelGroups[modelGroup].datasetGroups[
                  datasetName
                ].scorerGroups[scorerName] = {
                  metricPathGroups: {},
                };
              }

              // Merge metric path groups
              Object.entries(scorerData.metricPathGroups).forEach(
                ([metricPath, records]) => {
                  const targetScorerGroup =
                    newData.modelGroups[modelGroup].datasetGroups[datasetName]
                      .scorerGroups[scorerName];
                  if (!targetScorerGroup.metricPathGroups[metricPath]) {
                    targetScorerGroup.metricPathGroups[metricPath] = [];
                  }
                  targetScorerGroup.metricPathGroups[metricPath].push(
                    ...records
                  );
                }
              );
            }
          );
        }
      );
    });

    return {
      processedData: newData,
      scorerVersionMap,
      scorerLatestVersionMap,
      datasetVersionMap,
      datasetLatestVersionMap,
      globalScorerVersionMap,
      globalScorerLatestVersionMap,
      globalScorerTypeMap,
    };
  }, [data]);

  const columnStats = useMemo(
    () => getColumnStats(processedData.processedData),
    [processedData]
  );

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
    Object.entries(processedData.processedData.modelGroups).forEach(
      ([modelGroupName, modelGroup]) => {
        rowData.push({
          id: modelGroupName,
          modelGroupName,
          modelGroup,
        });
      }
    );
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
          const rowData = params.row as RowData;
          const isOp = modelGroupIsOp(rowData.modelGroup);
          const modelRef = parseRefMaybe(
            `weave:///${entity}/${project}/${isOp ? 'op' : 'object'}/${
              params.value
            }` ?? ''
          );

          // Get the latest evaluation status for this model
          const latestStatus = getLatestEvaluationStatus(
            rowData.modelGroup,
            callStatuses
          );
          const showStatusChip = latestStatus === 'running';

          if (modelRef) {
            return (
              <div
                style={{
                  width: 'max-content',
                  height: '100%',
                  alignContent: 'center',
                  display: 'flex',
                  alignItems: 'center',
                  lineHeight: '20px',
                  marginLeft: '10px',
                  gap: '8px',
                }}>
                <SmallRef objRef={modelRef} />
                {showStatusChip && (
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
    [
      columnStats.datasetGroups,
      entity,
      getColorForScore,
      onCellClick,
      project,
      callStatuses,
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
            // datasetGroupName is now just the dataset name (without version)
            const datasetName = datasetGroupName;

            // Check if there are multiple versions for this dataset
            const versions = processedData.datasetVersionMap[datasetName];
            const hasMultipleVersions = versions && versions.size > 1;
            const latestVersion =
              processedData.datasetLatestVersionMap[datasetName];

            // Try to create a ref using the latest version we've seen
            const ref = latestVersion
              ? parseRefMaybe(
                  `weave:///${entity}/${project}/object/${datasetName}:${latestVersion}`
                )
              : null;

            return (
              <div style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
                {hasMultipleVersions ? (
                  <>
                    <div>{datasetName}</div>
                    <Tooltip
                      title={`This dataset has ${versions.size} different versions across evaluations. Take precaution when comparing results.`}>
                      <Alert
                        severity="warning"
                        style={{
                          padding: '2px 8px',
                          fontSize: '11px',
                        }}>
                        Dataset inconsistency detected
                      </Alert>
                    </Tooltip>
                  </>
                ) : ref ? (
                  <SmallRef objRef={ref} />
                ) : (
                  <div>{datasetName}</div>
                )}
              </div>
            );
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
              renderHeaderGroup: () => {
                // Check if there are multiple versions for this scorer (using global map)
                const allVersions =
                  processedData.globalScorerVersionMap[scorerGroupName] ||
                  new Set<string>();
                const hasMultipleVersions = allVersions.size > 1;
                const scorerVersion =
                  processedData.globalScorerLatestVersionMap[scorerGroupName];
                const scorerType =
                  processedData.globalScorerTypeMap[scorerGroupName] || 'op';

                // Debug logging
                console.log(`Scorer ${scorerGroupName} render:`, {
                  scorerVersion,
                  scorerType,
                  hasMultipleVersions,
                  allVersions: Array.from(allVersions),
                  globalMaps: {
                    version: processedData.globalScorerLatestVersionMap,
                    type: processedData.globalScorerTypeMap,
                  },
                });

                // Construct a proper WeaveObjectRef for the scorer
                // The parseRefMaybe function needs the full URI format
                // Skip creating refs for Summary scorers which don't have versions
                const scorerUri =
                  scorerVersion && scorerGroupName !== 'Summary'
                    ? `weave:///${entity}/${project}/${scorerType}/${scorerGroupName}:${scorerVersion}`
                    : null;
                const ref = scorerUri ? parseRefMaybe(scorerUri) : null;

                console.log(`Scorer ${scorerGroupName} URI:`, {
                  scorerUri,
                  ref,
                  hasRef: !!ref,
                });

                return (
                  <div
                    style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
                    {hasMultipleVersions ? (
                      <>
                        <div>{scorerGroupName}</div>
                        <Tooltip
                          title={`This scorer has ${allVersions.size} different versions across evaluations. Take precaution when comparing results.`}>
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
                    ) : ref ? (
                      <SmallRef objRef={ref} />
                    ) : (
                      <div>{scorerGroupName}</div>
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
  }, [
    columnStats.datasetGroups,
    entity,
    project,
    processedData.datasetVersionMap,
    processedData.datasetLatestVersionMap,
    processedData.globalScorerVersionMap,
    processedData.globalScorerLatestVersionMap,
    processedData.globalScorerTypeMap,
  ]);

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

  // Group records by model and get the latest evaluation for each model
  const modelGroups = new Map<string, LeaderboardValueRecord[]>();
  data.forEach(record => {
    const modelKey = `${record.modelName}:${record.modelVersion}`;
    if (!modelGroups.has(modelKey)) {
      modelGroups.set(modelKey, []);
    }
    modelGroups.get(modelKey)!.push(record);
  });

  // Get latest evaluation for each model
  const latestRecords: LeaderboardValueRecord[] = [];
  modelGroups.forEach(modelRecords => {
    const latest = modelRecords.sort(
      (a, b) => b.createdAt.getTime() - a.createdAt.getTime()
    )[0];
    latestRecords.push(latest);
  });

  // If we have only one model's latest record, return it
  if (latestRecords.length === 1) {
    return latestRecords[0];
  }

  // If we have multiple models, return the most recent overall
  return latestRecords.sort(
    (a, b) => b.createdAt.getTime() - a.createdAt.getTime()
  )[0];
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
