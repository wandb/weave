import { GridColDef, GridColumnGroupingModel } from "@mui/x-data-grid-pro";
import React, { useMemo } from "react";

import { StyledDataGrid } from "../../../../StyledDataGrid";
import { EvaluationComparisonState } from "../../ecpState";
import _ from "lodash";
import { useExampleCompareData } from "./ExampleCompareSectionUtil";

type RowData = {
    predictAndScoreCallId: string;
    datasetRowDigest: string;
    evaluationCallId: string;
    inputs: any;
    output: any;
    scores: any;
}

const DatasetRowItemRenderer: React.FC<{
    state: EvaluationComparisonState;
    digest: string;
    key: string;
}> = props => {
    const firstExampleRow = useExampleCompareData(
        props.state,
        [{
            inputDigest: props.digest
        }],
        0
    )
    return <div>
        {JSON.stringify(firstExampleRow.targetRowValue?.[props.key])}
    </div>
}

export const ExampleCompareSectionTable: React.FC<{
    state: EvaluationComparisonState;
  }> = props => {
    console.log(props.state.loadableComparisonResults.result?.resultRows)

    const firstExampleRow = useExampleCompareData(
        props.state,
        Object.keys(props.state.loadableComparisonResults.result?.resultRows ?? {}).map(digest => ({
            inputDigest: digest
        })),
        0
    )
    console.log(firstExampleRow)
    const rows: RowData[] = useMemo(() => {
        return Object.entries(props.state.loadableComparisonResults.result?.resultRows ?? {}).flatMap(([datasetRowDigest, row]) => {
            return Object.entries(row.evaluations).flatMap(([evaluationCallId, evaluationRow]) => {
                return Object.entries(evaluationRow.predictAndScores).flatMap(([predictAndScoreCallId, predictAndScoreRow]) => {
                    return {
                        predictAndScoreCallId,
                        datasetRowDigest,
                        evaluationCallId,
                        trials: 1, // TODO: make this actually real. Probably want an expand button for this. Can it be done with a group maybe?
                        // inputs: _.omit(predictAndScoreRow?._rawPredictTraceData?.inputs, 'self'),
                        output: predictAndScoreRow?._rawPredictTraceData?.output,
                        scores: predictAndScoreRow?.scoreMetrics,
                    }
                })
            })
        })
    }, [props.state.loadableComparisonResults.result?.resultRows])

    const inputSubFields = useMemo(() => {
        const exampleRow = firstExampleRow.targetRowValue ?? {}

        if (_.isObject(exampleRow)) {
            return Object.keys(exampleRow)
        } else {
            return ['']
        }
    }, [firstExampleRow.targetRowValue])

    const scoreSubFields = useMemo(() => {
        const keys: string[] = []
        for (const row of rows) {
            if (_.isObject(row.scores)) {
                for (const key in row.scores) {
                    if (!keys.includes(key)) {
                        keys.push(key)  
                    }
                }
            } else {
                if (!keys.includes('')) {
                    keys.push('')
                }
            }
        }
        return keys
    }, [rows])
    
    const outputSubFields = useMemo(() => {
        const keys: string[] = []
        for (const row of rows) {
            if (_.isObject(row.output)) {
                for (const key in row.output) {
                    if (!keys.includes(key)) {
                        keys.push(key)
                    }
                }
            } else {
                if (!keys.includes('')) {
                    keys.push('')
                }
            }
        }
        return keys
    }, [rows])


    const columns: GridColDef<RowData>[] = useMemo(() => {
        return [
            {
                field: 'datasetRowDigest',
                headerName: 'Row Digest',
                // width: 100
                flex: 1
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
                headerName: 'Evaluation Call ID',
                // width: 100
                flex: 1
            },
            // {
            //     field: 'predictAndScoreCallId',
            //     headerName: 'Predict and Score Call ID',
            //     // width: 100
            //     flex: 1
            // }, 
            ...outputSubFields.map(key => ({
                field: `output.${key}`,
                headerName: key,
                // width: 100,
                flex: 1,
                valueGetter: (value: any, row: RowData) => {
                    if (key === '') {
                        if (_.isObject(row.output)) {
                            return ''
                        } else {
                            return row.output
                        }
                    }
                    return row.output[key]
                },
                valueFormatter: (value: any) => {
                    return JSON.stringify(value)
                }
            })),
            ...scoreSubFields.map(key => ({
                field: `scores.${key}`,
                headerName: key,
                // width: 100,
                flex: 1,
                valueGetter: (value: any, row: RowData) => {
                    if (key === '') {
                        if (_.isObject(row.scores)) {
                            return ''
                        } else {
                            return row.scores
                        }
                    }
                    return row.scores[key]
                },
                valueFormatter: (value: any) => {
                    return JSON.stringify(value.value)
                }
            })),
        ]
    }, [inputSubFields, outputSubFields, scoreSubFields, props.state])

    const columnGroupingModel: GridColumnGroupingModel = useMemo(() => {
        return [
            {
                groupId: 'inputs',
                headerName: 'Inputs',
                children: inputSubFields.map(key => ({
                    field: `inputs.${key}`,
                }))
            },
            {
                groupId: 'scores',
                headerName: 'Scores',
                children: scoreSubFields.map(key => ({
                    field: `scores.${key}`,
                }))
            },
            {
                groupId: 'output',
                headerName: 'Output',
                children: outputSubFields.map(key => ({
                    field: `output.${key}`,
                }))
            }
        ]
    }, [inputSubFields, scoreSubFields, outputSubFields])

    return <StyledDataGrid
        // treeData
        // getTreeDataPath={(row) => [row.datasetRowDigest, row.evaluationCallId, row.predictAndScoreCallId]}
        getRowId={(row) => row.predictAndScoreCallId}
        unstable_rowSpanning={true}
        columns={columns}
        rows={rows}
        columnGroupingModel={columnGroupingModel}
    />
  }