import {Box} from '@mui/material';
import {
  GridColDef,
  GridColumnGroupingModel,
  GridColumnHeaderParams,
  GridRenderCellParams,
} from '@mui/x-data-grid-pro';
import {Icon} from '@wandb/weave/components/Icon';
import {IconButton} from '@wandb/weave/components/IconButton';
import {CellValue} from '@wandb/weave/components/PagePanelComponents/Home/Browse2/CellValue';
import {parseRefMaybe} from '@wandb/weave/react';
import _ from 'lodash';
import React, {useMemo, useState} from 'react';

import {StyledDataGrid} from '../../../../StyledDataGrid';
import {IdPanel} from '../../../common/Id';
import {CallLink} from '../../../common/Links';
import {useCompareEvaluationsState} from '../../compareEvaluationsContext';
import {EvaluationComparisonState} from '../../ecpState';
import {flattenedDimensionPath} from '../../ecpUtil';
import {EvaluationModelLink} from '../ComparisonDefinitionSection/EvaluationDefinition';
import {evalAggScorerMetricCompGeneric} from './ExampleCompareSectionDetail';
import {
  PivotedRow,
  removePrefix,
  useExampleCompareData,
  useFilteredAggregateRows,
} from './ExampleCompareSectionUtil';

type ModelAsRowsRowDataBase = Pick<
  PivotedRow,
  'evaluationCallId' | 'inputDigest' | 'output' | 'scores' | 'predictAndScore'
> & {
  id: string;
  _expansionId: string;
};

type ModelsAsRowsRowDataTrial = ModelAsRowsRowDataBase & {
  _type: 'trial';
};

type ModelsAsRowsRowDataSummary = ModelAsRowsRowDataBase & {
  _type: 'summary';
  _numTrials: number;
};

type ModelsAsRowsRowData =
  | ModelsAsRowsRowDataTrial
  | ModelsAsRowsRowDataSummary;

const DatasetRowItemRenderer: React.FC<{
  state: EvaluationComparisonState;
  digest: string;
  inputKey: string;
}> = props => {
  const row = useExampleCompareData(
    props.state,
    [
      {
        inputDigest: props.digest,
      },
    ],
    0
  );
  return <CellValue value={row.targetRowValue?.[props.inputKey]} />;
};

export const ExampleCompareSectionTable: React.FC<{
  state: EvaluationComparisonState;
  modelsAsRows: boolean;
  shouldHighlightSelectedRow?: boolean;
  onShowSplitView: () => void;
}> = props => {
  if (props.modelsAsRows) {
    return (
      <ExampleCompareSectionTableModelsAsRows
        state={props.state}
        shouldHighlightSelectedRow={props.shouldHighlightSelectedRow}
        onShowSplitView={props.onShowSplitView}
      />
    );
  } else {
    return (
      <ExampleCompareSectionTableModelsAsColumns
        state={props.state}
        shouldHighlightSelectedRow={props.shouldHighlightSelectedRow}
        onShowSplitView={props.onShowSplitView}
      />
    );
  }
};

const useFirstExampleRow = (state: EvaluationComparisonState) => {
  return useExampleCompareData(
    state,
    Object.keys(state.loadableComparisonResults.result?.resultRows ?? {}).map(
      digest => ({
        inputDigest: digest,
      })
    ),
    0
  );
};

export const ExampleCompareSectionTableModelsAsRows: React.FC<{
  state: EvaluationComparisonState;
  shouldHighlightSelectedRow?: boolean;
  onShowSplitView: () => void;
}> = props => {
  const {filteredRows, outputColumnKeys} = useFilteredAggregateRows(
    props.state
  );
  const firstExampleRow = useFirstExampleRow(props.state);
  const [expandedIds, setExpandedIds] = useState<string[]>([]);

  const {rows, hasTrials} = useMemo(() => {
    let hasTrials = false;
    const returnRows = filteredRows.flatMap(filteredRow => {
      const evaluationCallIds = props.state.evaluationCallIdsOrdered;
      const finalRows: ModelsAsRowsRowData[] = [];
      for (const evaluationCallId of evaluationCallIds) {
        const matchingRows = filteredRow.originalRows.filter(
          row => row.evaluationCallId === evaluationCallId
        );
        const numTrials = matchingRows.length;
        const expansionId = filteredRow.inputDigest + ':' + evaluationCallId;
        const originalRows: ModelsAsRowsRowDataTrial[] = matchingRows.map(
          row => {
            return {
              _type: 'trial' as const,
              _expansionId: expansionId,
              ...row,
            };
          }
        );
        const digestEvalId = filteredRow.inputDigest + ':' + evaluationCallId;
        hasTrials = hasTrials || numTrials > 1;
        if (numTrials > 1 && !expandedIds.includes(digestEvalId)) {
          const summaryRow: ModelsAsRowsRowDataSummary = {
            ...originalRows[0],
            _type: 'summary' as const,
            _numTrials: numTrials,
            _expansionId: expansionId,
            id: digestEvalId,
            output: filteredRow.output,
            scores: filteredRow.scores,
          };
          finalRows.push(summaryRow);
        } else {
          finalRows.push(...originalRows);
        }
      }
      return finalRows;
    });
    return {rows: returnRows, hasTrials};
  }, [expandedIds, filteredRows, props.state.evaluationCallIdsOrdered]);

  const inputSubFields = useMemo(() => {
    const exampleRow = firstExampleRow.targetRowValue ?? {};

    if (_.isObject(exampleRow)) {
      return Object.keys(exampleRow);
    } else {
      return [''];
    }
  }, [firstExampleRow.targetRowValue]);
  // console.log(inputSubFields);

  const scoreSubFields = useMemo(() => {
    const keys: string[] = [];
    for (const row of rows) {
      if (_.isObject(row.scores)) {
        for (const key in row.scores) {
          if (!keys.includes(key)) {
            keys.push(key);
          }
        }
      } else {
        if (!keys.includes('')) {
          keys.push('');
        }
      }
    }
    return keys;
  }, [rows]);
  console.log(props.state);

  const outputSubFields = useMemo(() => {
    return outputColumnKeys;
    // const keys: string[] = []
    // for (const row of rows) {
    //     if (_.isObject(row.output)) {
    //         for (const key in row.output) {
    //             if (!keys.includes(key)) {
    //                 keys.push(key)
    //             }
    //         }
    //     } else {
    //         if (!keys.includes('')) {
    //             keys.push('')
    //         }
    //     }
    // }
    // return keys
  }, [outputColumnKeys]);
  const {setSelectedInputDigest} = useCompareEvaluationsState();

  const columns: GridColDef<ModelsAsRowsRowData>[] = useMemo(() => {
    const res: GridColDef<ModelsAsRowsRowData>[] = [
      {
        field: 'inputDigest',
        headerName: 'Row',
        width: 60,
        renderCell: params => {
          return (
            <Box
              style={{
                height: '100%',
                width: '100%',
                overflow: 'hidden',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
              }}
              onClick={() => {
                setSelectedInputDigest(params.row.inputDigest);
                props.onShowSplitView();
              }}>
              <span style={{flexShrink: 1}}>
                <IdPanel clickable>{params.row.inputDigest.slice(-4)}</IdPanel>
              </span>
            </Box>
          );
        },
      },
      ...inputSubFields.map(key => ({
        field: `inputs.${key}`,
        headerName: key,
        // width: 100,
        flex: 1,
        valueGetter: (value: any, row: ModelsAsRowsRowData) => {
          return row.inputDigest;
          // if (key === '') {
          //     if (_.isObject(row.dataRow)) {
          //         return ''
          //     } else {
          //         return row.dataRow
          //     }
          // }
          // return row.dataRow[key]
        },
        renderCell: (params: GridRenderCellParams<ModelsAsRowsRowData>) => {
          // console.log(key);
          return (
            <DatasetRowItemRenderer
              state={props.state}
              digest={params.row.inputDigest}
              inputKey={key}
            />
          );
        },
      })),
      {
        field: 'evaluationCallId',
        headerName: 'Model',
        // width: 100
        flex: 1,
        renderCell: params => {
          // if (params.rowNode.type === 'group') {
          //     return null;
          // }
          return (
            <EvaluationModelLink
              callId={params.row.evaluationCallId}
              state={props.state}
            />
          );
        },
      },
      ...(hasTrials
        ? [
            {
              field: 'expandTrials',
              headerName: '',
              width: 50,
              resizable: false,
              valueGetter: (value: any, row: ModelsAsRowsRowData) => {
                return row.evaluationCallId;
              },
              renderCell: (
                params: GridRenderCellParams<ModelsAsRowsRowData>
              ) => {
                // if (params.row._numTrials < 2) {
                //   return null;
                // }
                const isExpanded = expandedIds.includes(
                  params.row._expansionId
                );
                return (
                  <Box
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      height: '100%',
                      width: '100%',
                    }}>
                    <IconButton
                      onClick={() => {
                        setExpandedIds(prev => {
                          if (prev.includes(params.row._expansionId)) {
                            return prev.filter(
                              id => id !== params.row._expansionId
                            );
                          } else {
                            return [...prev, params.row._expansionId];
                          }
                        });
                      }}>
                      <Icon
                        name={isExpanded ? 'collapse' : 'expand-uncollapse'}
                      />
                    </IconButton>
                  </Box>
                );
              },
            },
          ]
        : []),
      {
        field: 'trialNdx',
        headerName: 'Trial',
        width: 60,
        // flex: 1,
        resizable: false,
        rowSpanValueGetter: (value: any, row: ModelsAsRowsRowData) => {
          // disable row spanning for now
          return row.id;
        },
        renderCell: params => {
          // if (params.rowNode.type === 'group') {
          //     return null;
          // }
          // const currEvalCallId = orderedCallIds[evalIndex];
          // const selectedTrial = lookupSelectedTrialForEval(evalIndex);
          // if (selectedTrial == null) {
          //   return null;
          // }
          if (params.row._type === 'summary') {
            return (
              <div
                style={{
                  height: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}>
                {params.row._numTrials}
              </div>
            );
          }
          const trialPredict = params.row.predictAndScore._rawPredictTraceData;
          const [trialEntity, trialProject] =
            trialPredict?.project_id.split('/') ?? [];
          const trialOpName = parseRefMaybe(
            trialPredict?.op_name ?? ''
          )?.artifactName;
          const trialCallId = params.row.predictAndScore.callId;
          if (trialEntity && trialProject && trialOpName && trialCallId) {
            return (
              <Box
                style={{
                  overflow: 'hidden',
                  height: '100%',
                  display: 'flex',
                  alignItems: 'center',
                }}>
                <CallLink
                  entityName={trialEntity}
                  projectName={trialProject}
                  opName={trialOpName}
                  callId={trialCallId}
                  noName
                />
              </Box>
            );
          }
          return null;
        },
      },
      // {
      //     field: 'predictAndScoreCallId',
      //     headerName: 'Prediction',
      //     // width: 100
      //     flex: 1,
      //     renderCell: (params) => {
      //         // const currEvalCallId = orderedCallIds[evalIndex];
      //         // const selectedTrial = lookupSelectedTrialForEval(evalIndex);
      //         // if (selectedTrial == null) {
      //         //   return null;
      //         // }
      //         const trialPredict = params.row.predictAndScore._rawPredictTraceData;
      //         const [trialEntity, trialProject] =
      //           trialPredict?.project_id.split('/') ?? [];
      //         const trialOpName = parseRefMaybe(
      //           trialPredict?.op_name ?? ''
      //         )?.artifactName;
      //         const trialCallId = trialPredict?.id;
      //         const evaluationCall = props.state.summary.evaluationCalls[params.row.evaluationCallId];
      //         if (trialEntity && trialProject && trialOpName && trialCallId) {
      //           return (
      //             <Box
      //               style={{
      //                 overflow: 'hidden',
      //               }}>
      //               <CallLink
      //                 entityName={trialEntity}
      //                 projectName={trialProject}
      //                 opName={trialOpName}
      //                 callId={trialCallId}
      //                 icon={<Icon name="filled-circle" color={evaluationCall.color} />}
      //                 color={MOON_800}
      //               />
      //             </Box>
      //           );
      //         }
      //         return null;
      //     }
      // },
      // {
      //     field: 'predictAndScoreCallId',
      //     headerName: 'Predict and Score Call ID',
      //     // width: 100
      //     flex: 1
      // },
      ...outputSubFields.map(key => ({
        field: `output.${key}`,
        headerName: removePrefix(key, 'output.'),
        // width: 100,
        flex: 1,
        valueGetter: (value: any, row: ModelsAsRowsRowData) => {
          // if (row.output === undefined) {
          //     return null;
          // }
          return row.output[key]?.[row.evaluationCallId];
        },
        renderCell: (params: GridRenderCellParams<ModelsAsRowsRowData>) => {
          // if (params.rowNode.type === 'group') {
          //     return null;
          // }
          if (params.row._type === 'summary') {
            // sad
            return null;
            // CODE COPY
            // const digestEvalId =
            //       params.row.inputDigest + ':' + params.row.evaluationCallId;
            //     const isExpanded = expandedDigestEvalIds.includes(digestEvalId);
            //     return (
            //       <Box
            //         style={{
            //           display: 'flex',
            //           alignItems: 'center',
            //           justifyContent: 'center',
            //           height: '100%',
            //           width: '100%',
            //         }}>
            //         <IconButton
            //           onClick={() => {
            //             setExpandedDigestEvalIds(prev => {
            //               if (prev.includes(digestEvalId)) {
            //                 return prev.filter(id => id !== digestEvalId);
            //               } else {
            //                 return [...prev, digestEvalId];
            //               }
            //             });
            //           }}>
            //           <Icon
            //             name={isExpanded ? 'collapse' : 'expand-uncollapse'}
            //           />
            //         </IconButton>
            //       </Box>
            //     );
          }
          return (
            <CellValue
              value={params.row.output[key]?.[params.row.evaluationCallId]}
            />
          );
        },
        rowSpanValueGetter: (value: any, row: ModelsAsRowsRowData) => {
          // disable row spanning for now
          return row.id;
        },
      })),
      ...scoreSubFields.map(key => ({
        field: `scores.${key}`,
        headerName: flattenedDimensionPath(
          props.state.summary.scoreMetrics[key]
        ),
        // width: 100,
        flex: 1,
        valueGetter: (value: any, row: ModelsAsRowsRowData) => {
          // if (key === '') {
          //     retuen
          // }
          //   if (row.scores === undefined) {
          //     return null;
          // }
          return row.scores[key][row.evaluationCallId];
        },
        renderCell: (params: GridRenderCellParams<ModelsAsRowsRowData>) => {
          // if (params.rowNode.type === 'group') {
          //     return null;
          // }
          if (params.row._type === 'summary') {
            return evalAggScorerMetricCompGeneric(
              props.state.summary.scoreMetrics[key],
              params.row.scores[key][params.row.evaluationCallId],
              params.row.scores[key][props.state.evaluationCallIdsOrdered[0]]
            );
          }

          return (
            <CellValue
              value={params.row.scores[key][params.row.evaluationCallId]}
            />
          );
        },
        rowSpanValueGetter: (value: any, row: ModelsAsRowsRowData) => {
          // disable row spanning for now
          return row.id;
        },
      })),
    ];
    return res;
  }, [
    inputSubFields,
    hasTrials,
    outputSubFields,
    scoreSubFields,
    setSelectedInputDigest,
    props,
    expandedIds,
  ]);

  const columnGroupingModel: GridColumnGroupingModel = useMemo(() => {
    return [
      {
        groupId: 'inputs',
        headerName: 'Inputs',
        children: inputSubFields.map(key => ({
          field: `inputs.${key}`,
        })),
      },
      {
        groupId: 'scores',
        headerName: 'Scores',
        children: scoreSubFields.map(key => ({
          field: `scores.${key}`,
        })),
      },
      {
        groupId: 'output',
        headerName: 'Output',
        children: outputSubFields.map(key => ({
          field: `output.${key}`,
        })),
      },
    ];
  }, [inputSubFields, scoreSubFields, outputSubFields]);

  // console.log(props.state.summary.scoreMetrics);

  const selectedRow = useMemo(() => {
    if (!props.shouldHighlightSelectedRow) {
      return [];
    }
    const assumedSelectedInputDigest =
      props.state.selectedInputDigest ?? rows[0].inputDigest;
    return rows
      .filter(row => row.inputDigest === assumedSelectedInputDigest)
      .map(row => row.id);
  }, [props.shouldHighlightSelectedRow, props.state.selectedInputDigest, rows]);

  return (
    <StyledDataGrid
      //   treeData
      //   getTreeDataPath={(row: RowData) => [row.inputDigest + row.evaluationCallId, row.id]}
      //   groupingColDef={{
      //     headerName: 'Row',
      //     width: 60,
      //     // flex: 1,
      //   }}
      //   getRowId={(row) => row.id}
      rowSelectionModel={selectedRow}
      unstable_rowSpanning={true}
      columns={columns}
      rows={rows}
      columnGroupingModel={columnGroupingModel}
      disableRowSelectionOnClick
      // slots={{
      //   footer: PivotModelButton,
      // }}
      // slotProps={{
      //   // footer: { status },
      // }}
      sx={{
        '& .MuiDataGrid-row:hover': {
          backgroundColor: 'white',
        },
        '& .MuiDataGrid-row.Mui-selected:hover': {
          // match the non-hover background color
          backgroundColor: 'rgba(169, 237, 242, 0.32)',
        },
        width: '100%',
      }}
    />
  );
};

type ModelAsColumnsRowDataBase = Pick<
  PivotedRow,
  'output' | 'scores' | 'inputDigest'
> & {
  id: string;
  _expansionId: string;
};

type ModelAsColumnsRowDataTrial = ModelAsColumnsRowDataBase & {
  _type: 'trial';
  _trialNdx: number;
};

type ModelAsColumnsRowDataSummary = ModelAsColumnsRowDataBase & {
  _type: 'summary';
  _numTrials: number;
};

type ModelAsColumnsRowData =
  | ModelAsColumnsRowDataTrial
  | ModelAsColumnsRowDataSummary;

export const ExampleCompareSectionTableModelsAsColumns: React.FC<{
  state: EvaluationComparisonState;
  shouldHighlightSelectedRow?: boolean;
  onShowSplitView: () => void;
}> = props => {
  const {filteredRows, outputColumnKeys} = useFilteredAggregateRows(
    props.state
  );

  const firstExampleRow = useFirstExampleRow(props.state);
  const [expandedIds, setExpandedIds] = useState<string[]>([]);
  // const rows = filteredRows;
  // const hasTrials = false;
  const {rows, hasTrials} = useMemo(() => {
    let hasTrials = false;
    const returnRows: ModelAsColumnsRowData[] = filteredRows.flatMap(
      (filteredRow): ModelAsColumnsRowData[] => {
        const groupedOriginalRows = _.groupBy(
          filteredRow.originalRows,
          row => row.evaluationCallId
        );
        const maxTrials = Math.max(
          ...Object.values(groupedOriginalRows).map(rows => rows.length)
        );

        const summaryRow: ModelAsColumnsRowDataSummary = {
          ...filteredRow,
          _type: 'summary' as const,
          _numTrials: maxTrials,
          _expansionId: filteredRow.inputDigest,
          id: filteredRow.inputDigest + ':summary',
          output: filteredRow.output,
          scores: filteredRow.scores,
        };

        hasTrials = hasTrials || maxTrials > 1;

        if (maxTrials > 1 && !expandedIds.includes(filteredRow.inputDigest)) {
          return [summaryRow];
        }

        return _.range(maxTrials).map(trialNdx => {
          const res: ModelAsColumnsRowDataTrial = {
            ...filteredRow,
            _type: 'trial' as const,
            _trialNdx: trialNdx,
            _expansionId: filteredRow.inputDigest,
            id: filteredRow.inputDigest + ':trial:' + trialNdx,
            // turn these into reducers
            output: Object.fromEntries(
              Object.entries(filteredRow.output).map(([key, value]) => {
                return [
                  key,
                  Object.fromEntries(
                    Object.values(groupedOriginalRows).map(evalVal => {
                      return [
                        evalVal[trialNdx]?.evaluationCallId,
                        evalVal[trialNdx]?.output?.[key]?.[
                          evalVal[trialNdx]?.evaluationCallId
                        ],
                      ];
                    })
                  ),
                ];
              })
            ),
            scores: Object.fromEntries(
              Object.entries(filteredRow.scores).map(([key, value]) => {
                return [
                  key,
                  Object.fromEntries(
                    Object.values(groupedOriginalRows).map(evalVal => {
                      return [
                        evalVal[trialNdx]?.evaluationCallId,
                        evalVal[trialNdx]?.scores?.[key]?.[
                          evalVal[trialNdx]?.evaluationCallId
                        ],
                      ];
                    })
                  ),
                ];
              })
            ),
          };
          return res;
        });
      }
    );

    return {rows: returnRows, hasTrials};
  }, [expandedIds, filteredRows]);

  // console.log(rows, hasTrials);

  // console.log(filteredRows);

  // const rows: RowData[] = useMemo(() => {
  //   // For each dataset + evaluation pair, add a summary over the trials.
  //   const rowsByEvalAndDataset = _.groupBy(flatRows, row => [row.inputDigest + row.evaluationCallId]);
  //   const rowsByEvalAndDatasetAndTrial = _.mapValues(rowsByEvalAndDataset, rows => {
  //     return {
  //       ...rows[0],
  //       _summary: {
  //         trials: rows.length,
  //       }
  //     };
  //   });

  //   // const finalRows: RowData[] = [];
  //   // for (const [key, rows] of Object.entries(rowsByEvalAndDatasetAndTrial)) {
  //   //   finalRows.push(...rows);
  //   // }
  //   return flatRows;
  // }, [flatRows]);

  const inputSubFields = useMemo(() => {
    const exampleRow = firstExampleRow.targetRowValue ?? {};

    if (_.isObject(exampleRow)) {
      return Object.keys(exampleRow);
    } else {
      return [''];
    }
  }, [firstExampleRow.targetRowValue]);
  // console.log(inputSubFields);

  const scoreSubFields = useMemo(() => {
    const keys: string[] = [];
    for (const row of rows) {
      if (_.isObject(row.scores)) {
        for (const key in row.scores) {
          if (!keys.includes(key)) {
            keys.push(key);
          }
        }
      } else {
        if (!keys.includes('')) {
          keys.push('');
        }
      }
    }
    return keys;
  }, [rows]);

  const outputSubFields = useMemo(() => {
    return outputColumnKeys;
    // const keys: string[] = []
    // for (const row of rows) {
    //     if (_.isObject(row.output)) {
    //         for (const key in row.output) {
    //             if (!keys.includes(key)) {
    //                 keys.push(key)
    //             }
    //         }
    //     } else {
    //         if (!keys.includes('')) {
    //             keys.push('')
    //         }
    //     }
    // }
    // return keys
  }, [outputColumnKeys]);
  const {setSelectedInputDigest} = useCompareEvaluationsState();

  const columns: GridColDef<ModelAsColumnsRowData>[] = useMemo(() => {
    const res: GridColDef<ModelAsColumnsRowData>[] = [
      {
        field: 'inputDigest',
        headerName: 'Row',
        width: 60,
        // flex: 1,
        renderCell: params => {
          // if (params.rowNode.type === 'group') {
          //     return null;
          // }
          return (
            <Box
              style={{
                height: '100%',
                width: '100%',
                overflow: 'hidden',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
              }}
              onClick={() => {
                setSelectedInputDigest(params.row.inputDigest);
                props.onShowSplitView();
              }}>
              <span style={{flexShrink: 1}}>
                <IdPanel clickable> {params.row.inputDigest.slice(-4)}</IdPanel>
              </span>
            </Box>
          );
        },
      },
      ...inputSubFields.map(key => ({
        field: `inputs.${key}`,
        headerName: key,
        // width: 100,
        flex: 1,
        valueGetter: (value: any, row: ModelAsColumnsRowData) => {
          return row.inputDigest;
          // if (key === '') {
          //     if (_.isObject(row.dataRow)) {
          //         return ''
          //     } else {
          //         return row.dataRow
          //     }
          // }
          // return row.dataRow[key]
        },
        renderCell: (params: GridRenderCellParams<ModelAsColumnsRowData>) => {
          // console.log(key);
          return (
            <DatasetRowItemRenderer
              state={props.state}
              digest={params.row.inputDigest}
              inputKey={key}
            />
          );
        },
      })),
      // {
      //   field: 'evaluationCallId',
      //   headerName: 'Model',
      //   // width: 100
      //   flex: 1,
      //   renderCell: params => {
      //     // if (params.rowNode.type === 'group') {
      //     //     return null;
      //     // }
      //     return (
      //       <EvaluationModelLink
      //         callId={params.row.evaluationCallId}
      //         state={props.state}
      //       />
      //     );
      //   },
      // },
      ...(hasTrials
        ? [
            {
              field: 'expandTrials',
              headerName: '',
              width: 50,
              resizable: false,
              valueGetter: (value: any, row: ModelAsColumnsRowData) => {
                return row.inputDigest;
              },
              renderCell: (
                params: GridRenderCellParams<ModelAsColumnsRowData>
              ) => {
                const isExpanded = expandedIds.includes(
                  params.row._expansionId
                );
                return (
                  <Box
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      height: '100%',
                      width: '100%',
                    }}>
                    <IconButton
                      onClick={() => {
                        setExpandedIds(prev => {
                          if (prev.includes(params.row._expansionId)) {
                            return prev.filter(
                              id => id !== params.row._expansionId
                            );
                          } else {
                            return [...prev, params.row._expansionId];
                          }
                        });
                      }}>
                      <Icon
                        name={isExpanded ? 'collapse' : 'expand-uncollapse'}
                      />
                    </IconButton>
                  </Box>
                );
              },
            },
          ]
        : []),
      // {
      //   field: 'trialNdx',
      //   headerName: 'Trial',
      //   width: 60,
      //   // flex: 1,
      //   resizable: false,
      //   rowSpanValueGetter: (value: any, row: RowData) => {
      //     // disable row spanning for now
      //     return row.id;
      //   },
      //   renderCell: params => {
      //     // if (params.rowNode.type === 'group') {
      //     //     return null;
      //     // }
      //     // const currEvalCallId = orderedCallIds[evalIndex];
      //     // const selectedTrial = lookupSelectedTrialForEval(evalIndex);
      //     // if (selectedTrial == null) {
      //     //   return null;
      //     // }
      //     if (params.row._type === 'summary') {
      //       return (
      //         <div
      //           style={{
      //             height: '100%',
      //             display: 'flex',
      //             alignItems: 'center',
      //             justifyContent: 'center',
      //           }}>
      //           {params.row._numTrials}
      //         </div>
      //       );
      //     }
      //     const trialPredict = params.row.predictAndScore._rawPredictTraceData;
      //     const [trialEntity, trialProject] =
      //       trialPredict?.project_id.split('/') ?? [];
      //     const trialOpName = parseRefMaybe(
      //       trialPredict?.op_name ?? ''
      //     )?.artifactName;
      //     const trialCallId = params.row.predictAndScore.callId;
      //     if (trialEntity && trialProject && trialOpName && trialCallId) {
      //       return (
      //         <Box
      //           style={{
      //             overflow: 'hidden',
      //             height: '100%',
      //             display: 'flex',
      //             alignItems: 'center',
      //           }}>
      //           <CallLink
      //             entityName={trialEntity}
      //             projectName={trialProject}
      //             opName={trialOpName}
      //             callId={trialCallId}
      //             noName
      //           />
      //         </Box>
      //       );
      //     }
      //     return null;
      //   },
      // },
      // {
      //     field: 'predictAndScoreCallId',
      //     headerName: 'Prediction',
      //     // width: 100
      //     flex: 1,
      //     renderCell: (params) => {
      //         // const currEvalCallId = orderedCallIds[evalIndex];
      //         // const selectedTrial = lookupSelectedTrialForEval(evalIndex);
      //         // if (selectedTrial == null) {
      //         //   return null;
      //         // }
      //         const trialPredict = params.row.predictAndScore._rawPredictTraceData;
      //         const [trialEntity, trialProject] =
      //           trialPredict?.project_id.split('/') ?? [];
      //         const trialOpName = parseRefMaybe(
      //           trialPredict?.op_name ?? ''
      //         )?.artifactName;
      //         const trialCallId = trialPredict?.id;
      //         const evaluationCall = props.state.summary.evaluationCalls[params.row.evaluationCallId];
      //         if (trialEntity && trialProject && trialOpName && trialCallId) {
      //           return (
      //             <Box
      //               style={{
      //                 overflow: 'hidden',
      //               }}>
      //               <CallLink
      //                 entityName={trialEntity}
      //                 projectName={trialProject}
      //                 opName={trialOpName}
      //                 callId={trialCallId}
      //                 icon={<Icon name="filled-circle" color={evaluationCall.color} />}
      //                 color={MOON_800}
      //               />
      //             </Box>
      //           );
      //         }
      //         return null;
      //     }
      // },
      // {
      //     field: 'predictAndScoreCallId',
      //     headerName: 'Predict and Score Call ID',
      //     // width: 100
      //     flex: 1
      // },
      ...outputSubFields.flatMap(key => {
        return props.state.evaluationCallIdsOrdered.map(evaluationCallId => {
          return {
            field: `output.${key}.${evaluationCallId}`,
            // headerName: evaluationCallId,
            renderHeader: (
              params: GridColumnHeaderParams<ModelAsColumnsRowData>
            ) => {
              return (
                <EvaluationModelLink
                  callId={evaluationCallId}
                  state={props.state}
                />
              );
            },
            // width: 100,
            flex: 1,
            valueGetter: (value: any, row: ModelAsColumnsRowData) => {
              // if (row.output === undefined) {
              //     return null;
              // }
              return row.output[key][evaluationCallId];
            },
            renderCell: (
              params: GridRenderCellParams<ModelAsColumnsRowData>
            ) => {
              // if (params.rowNode.type === 'group') {
              //     return null;
              // }
              return (
                <CellValue value={params.row.output[key][evaluationCallId]} />
              );
            },
            rowSpanValueGetter: (value: any, row: ModelAsColumnsRowData) => {
              // disable row spanning for now
              return row.id;
            },
          };
        });
      }),
      ...scoreSubFields.flatMap(key => {
        return props.state.evaluationCallIdsOrdered.map(evaluationCallId => {
          return {
            field: `scores.${key}.${evaluationCallId}`,
            renderHeader: (
              params: GridColumnHeaderParams<ModelAsColumnsRowData>
            ) => {
              return (
                <EvaluationModelLink
                  callId={evaluationCallId}
                  state={props.state}
                />
              );
            },
            // width: 100,
            flex: 1,
            valueGetter: (value: any, row: ModelAsColumnsRowData) => {
              // if (key === '') {
              //     retuen
              // }
              //   if (row.scores === undefined) {
              //     return null;
              // }
              return row.scores[key][evaluationCallId];
            },
            renderCell: (
              params: GridRenderCellParams<ModelAsColumnsRowData>
            ) => {
              // if (params.rowNode.type === 'group') {
              //     return null;
              // }

              return evalAggScorerMetricCompGeneric(
                props.state.summary.scoreMetrics[key],
                params.row.scores[key][evaluationCallId],
                // this compares directy to the peer
                params.row.scores[key][props.state.evaluationCallIdsOrdered[0]]
              );

              // return (
              //   <CellValue value={params.row.scores[key][evaluationCallId]} />
              // );
            },
            rowSpanValueGetter: (value: any, row: ModelAsColumnsRowData) => {
              // disable row spanning for now
              return row.id;
            },
          };
        });
      }),
    ];

    return res;
  }, [
    inputSubFields,
    hasTrials,
    outputSubFields,
    scoreSubFields,
    setSelectedInputDigest,
    props,
    expandedIds,
  ]);
  // console.log(columns);

  const columnGroupingModel: GridColumnGroupingModel = useMemo(() => {
    return [
      {
        groupId: 'inputs',
        headerName: 'Inputs',
        children: inputSubFields.map(key => ({
          field: `inputs.${key}`,
        })),
      },
      {
        groupId: 'output',
        headerName: 'Output',
        children: outputSubFields.map(key => {
          return {
            groupId: `output.${key}`,
            headerName: removePrefix(key, 'output.'),
            children: props.state.evaluationCallIdsOrdered.map(
              evaluationCallId => {
                return {
                  field: `output.${key}.${evaluationCallId}`,
                };
              }
            ),
          };
        }),
      },
      {
        groupId: 'scores',
        headerName: 'Scores',
        children: scoreSubFields.map(key => {
          return {
            groupId: `scores.${key}`,
            headerName: flattenedDimensionPath(
              props.state.summary.scoreMetrics[key]
            ),
            children: props.state.evaluationCallIdsOrdered.map(
              evaluationCallId => {
                return {
                  field: `scores.${key}.${evaluationCallId}`,
                };
              }
            ),
          };
        }),
      },
    ];
  }, [
    inputSubFields,
    outputSubFields,
    scoreSubFields,
    props.state.evaluationCallIdsOrdered,
    props.state.summary.scoreMetrics,
  ]);

  // console.log(props.state.summary.scoreMetrics);

  const selectedRow = useMemo(() => {
    if (!props.shouldHighlightSelectedRow) {
      return [];
    }
    const assumedSelectedInputDigest =
      props.state.selectedInputDigest ?? rows[0].inputDigest;
    return rows
      .filter(row => row.inputDigest === assumedSelectedInputDigest)
      .map(row => row.id);
  }, [props.shouldHighlightSelectedRow, props.state.selectedInputDigest, rows]);

  return (
    <StyledDataGrid
      //   treeData
      //   getTreeDataPath={(row: RowData) => [row.inputDigest + row.evaluationCallId, row.id]}
      //   groupingColDef={{
      //     headerName: 'Row',
      //     width: 60,
      //     // flex: 1,
      //   }}
      //   getRowId={(row) => row.id}
      rowSelectionModel={selectedRow}
      unstable_rowSpanning={true}
      columns={columns}
      rows={rows}
      columnGroupingModel={columnGroupingModel}
      disableRowSelectionOnClick
      // slots={{
      //   footer: PivotModelButton,
      // }}
      // slotProps={{
      //   // footer: { status },
      // }}
      sx={{
        '& .MuiDataGrid-row:hover': {
          backgroundColor: 'white',
        },
        '& .MuiDataGrid-row.Mui-selected:hover': {
          // match the non-hover background color
          backgroundColor: 'rgba(169, 237, 242, 0.32)',
        },
        width: '100%',
      }}
    />
  );
};

// export function PivotModelButton(
//   props: NonNullable<GridSlotsComponentsProps['footer']>,
// ) {
//   return <div>pivot</div>;
// };
