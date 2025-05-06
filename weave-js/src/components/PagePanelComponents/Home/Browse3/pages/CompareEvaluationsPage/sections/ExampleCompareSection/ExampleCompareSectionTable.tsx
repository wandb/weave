import {Box} from '@mui/material';
import {
  GridColDef,
  GridColumnGroupingModel,
  GridRenderCellParams,
} from '@mui/x-data-grid-pro';
import {CellValue} from '@wandb/weave/components/PagePanelComponents/Home/Browse2/CellValue';
import {parseRefMaybe} from '@wandb/weave/react';
import _ from 'lodash';
import React, {useMemo} from 'react';

import {StyledDataGrid} from '../../../../StyledDataGrid';
import {IdPanel} from '../../../common/Id';
import {CallLink} from '../../../common/Links';
import {EvaluationComparisonState} from '../../ecpState';
import {EvaluationModelLink} from '../ComparisonDefinitionSection/EvaluationDefinition';
import {
  PivotedRow,
  removePrefix,
  useExampleCompareData,
  useFilteredAggregateRows,
} from './ExampleCompareSectionUtil';
import { flattenedDimensionPath } from '../../ecpUtil';

type RowData = PivotedRow & {
  // simpleOutput: PivotedRow['output'][string]
};

export const ExampleCompareSectionTable: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  const {filteredRows, outputColumnKeys} = useFilteredAggregateRows(
    props.state
  );

  const firstExampleRow = useExampleCompareData(
    props.state,
    Object.keys(
      props.state.loadableComparisonResults.result?.resultRows ?? {}
    ).map(digest => ({
      inputDigest: digest,
    })),
    0
  );

  const rows: RowData[] = useMemo(() => {
    return filteredRows.flatMap(filteredRow => {
      return filteredRow.originalRows.flatMap(originalRow => {
        // return Object.entries(row.evaluations).flatMap(([evaluationCallId, evaluationRow]) => {
        //     return Object.entries(evaluationRow.predictAndScores).flatMap(([predictAndScoreCallId, predictAndScoreRow]) => {
        return {
          ...originalRow,
          // simpleOutput: Object.fromEntries(Object.entries(originalRow.output).map(([k, v]) => {
          //     return [k, v[originalRow.evaluationCallId]]
          // }))
        };
        // {
        //     predictAndScoreCallId,
        //     datasetRowDigest,
        //     evaluationCallId,
        //     trials: 1, // TODO: make this actually real. Probably want an expand button for this. Can it be done with a group maybe?
        //     // inputs: _.omit(predictAndScoreRow?._rawPredictTraceData?.inputs, 'self'),
        //     output: predictAndScoreRow?._rawPredictTraceData?.output,
        //     scores: predictAndScoreRow?.scoreMetrics,
        // }
        //     })
        // })
      });
    });
  }, [filteredRows]);

  const inputSubFields = useMemo(() => {
    const exampleRow = firstExampleRow.targetRowValue ?? {};

    if (_.isObject(exampleRow)) {
      return Object.keys(exampleRow);
    } else {
      return [''];
    }
  }, [firstExampleRow.targetRowValue]);

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

  const columns: GridColDef<RowData>[] = useMemo(() => {
    const res: GridColDef<RowData>[] = [
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
              }}>
              <span style={{flexShrink: 1}}>
                <IdPanel>{params.row.inputDigest.slice(-4)}</IdPanel>
              </span>
            </Box>
          );
        },
      },
      // ...inputSubFields.map(key => ({
      //     field: `inputs.${key}`,
      //     headerName: key,
      //     // width: 100,
      //     flex: 1,
      //     valueGetter: (value: any, row: RowData) => {
      //         if (key === '') {
      //             if (_.isObject(row.inputs)) {
      //                 return ''
      //             } else {
      //                 return row.inputs
      //             }
      //         }
      //         return row.inputs[key]
      //     },
      //     valueFormatter: (value: any, row: RowData) => {
      //         return <DatasetRowItemRenderer
      //             state={props.state}
      //             digest={row.datasetRowDigest}
      //             key={key}
      //         />
      //         // return JSON.stringify(value)
      //     }
      // })),
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
      {
        field: 'trialNdx',
        headerName: 'Trial',
        width: 60,
        // flex: 1,
        rowSpanValueGetter: (value: any, row: RowData) => {
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
        valueGetter: (value: any, row: RowData) => {
          // if (row.output === undefined) {
          //     return null;
          // }
          return row.output[key][row.evaluationCallId];
        },
        renderCell: (params: GridRenderCellParams<RowData>) => {
          // if (params.rowNode.type === 'group') {
          //     return null;
          // }
          return (
            <CellValue
              value={params.row.output[key][params.row.evaluationCallId]}
            />
          );
        },
        rowSpanValueGetter: (value: any, row: RowData) => {
          // disable row spanning for now
          return row.id;
        },
      })),
      ...scoreSubFields.map(key => ({
        field: `scores.${key}`,
        headerName: flattenedDimensionPath(props.state.summary.scoreMetrics[key]),
        // width: 100,
        flex: 1,
        valueGetter: (value: any, row: RowData) => {
          // if (key === '') {
          //     retuen
          // }
          //   if (row.scores === undefined) {
          //     return null;
          // }
          return row.scores[key][row.evaluationCallId];
        },
        renderCell: (params: GridRenderCellParams<RowData>) => {
          // if (params.rowNode.type === 'group') {
          //     return null;
          // }
          return (
            <CellValue
              value={params.row.scores[key][params.row.evaluationCallId]}
            />
          );
        },
        rowSpanValueGetter: (value: any, row: RowData) => {
          // disable row spanning for now
          return row.id;
        },
      })),
    ];
    return res;
  }, [outputSubFields, scoreSubFields, props.state]);

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

  console.log(props.state.summary.scoreMetrics)

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
      unstable_rowSpanning={true}
      columns={columns}
      rows={rows}
      columnGroupingModel={columnGroupingModel}
      disableRowSelectionOnClick
      sx={{
        '& .MuiDataGrid-row:hover': {
          backgroundColor: 'white',
        },
      }}
    />
  );
};
