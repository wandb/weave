import {Box} from '@material-ui/core';
import {Circle} from '@mui/icons-material';
import {
  GridColDef,
  GridColumnGroup,
  GridColumnGroupingModel,
  GridValueGetterParams,
} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {useMemo} from 'react';

import {parseRef, WeaveObjectRef} from '../../../../../../react';
import {Icon, IconNames} from '../../../../../Icon';
import {flattenObject} from '../../../Browse2/browse2Util';
import {SmallRef} from '../../../Browse2/SmallRef';
import {StyledDataGrid} from '../../StyledDataGrid';
import {ValueViewNumber} from '../CallPage/ValueViewNumber';
import {CallLink} from '../common/Links';
import {useCompareEvaluationsState} from './compareEvaluationsContext';
import {CIRCLE_SIZE, SIGNIFICANT_DIGITS} from './constants';
import {getOrderedCallIds} from './evaluationResults';
import {ScoreDimension} from './evaluations';
import {useEvaluationCallDimensions} from './initialize';
import {HorizontalBox} from './Layout';
import {EvaluationComparisonState} from './types';

const scoreIdFromScoreDimension = (dim: ScoreDimension): string => {
  return dim.scorerRef + '@' + dim.scoreKeyPath;
};
type FlattenedRow = {
  id: string;
  evaluationCallId: string;
  inputDigest: string;
  inputRef: string;
  input: {[inputKey: string]: any};
  output: {[outputKey: string]: any};
  scores: {[scoreId: string]: number | boolean};
  latency: number;
  totalTokens: number;
  path: string[];
};
type PivotedRow = {
  id: string;
  inputDigest: string;
  inputRef: string;
  input: {[inputKey: string]: any};
  evaluationCallId: {[callId: string]: string};
  output: {[outputKey: string]: {[callId: string]: any}};
  scores: {[scoreId: string]: {[callId: string]: number | boolean}};
  latency: {[callId: string]: number};
  totalTokens: {[callId: string]: number};
  path: string[];
};
const aggregateGroupedNestedRows = (
  rows: PivotedRow[],
  field: keyof PivotedRow,
  aggFunc: (vals: any[]) => any
) => {
  return Object.fromEntries(
    Object.entries(
      rows.reduce<{
        [flatKey: string]: {[callId: string]: any[]};
      }>((acc, row) => {
        Object.entries(row[field]).forEach(([key, val]) => {
          Object.entries(val).forEach(([subKey, subVal]) => {
            if (acc[key] == null) {
              acc[key] = {};
            }
            if (acc[key][subKey] == null) {
              acc[key][subKey] = [];
            }
            acc[key][subKey].push(subVal);
          });
        });
        return acc;
      }, {})
    ).map(([key, val]) => {
      return [
        key,
        Object.fromEntries(
          Object.entries(val).map(([subKey, subVal]) => {
            return [subKey, aggFunc(subVal)];
          })
        ),
      ];
    })
  );
};
const aggregateGroupedRows = (
  rows: PivotedRow[],
  field: keyof PivotedRow,
  aggFunc: (vals: any[]) => any
) => {
  return Object.fromEntries(
    Object.entries(
      rows.reduce<{
        [flatKey: string]: any[];
      }>((acc, row) => {
        Object.entries(row[field]).forEach(([key, val]) => {
          if (acc[key] == null) {
            acc[key] = [];
          }
          acc[key].push(val);
        });

        return acc;
      }, {})
    ).map(([key, val]) => {
      return [key, aggFunc(val)];
    })
  );
};
const filterNones = (list: any[]) => {
  return list.filter(v => v != null);
};
export const CompareEvaluationsCallsTable: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  const leafDims = useMemo(() => getOrderedCallIds(props.state), [props.state]);
  const scores = useEvaluationCallDimensions(props.state);
  const scoreMap = useMemo(() => {
    return Object.fromEntries(
      scores.map(score => [scoreIdFromScoreDimension(score), score])
    );
  }, [scores]);

  const flattenedRows = useMemo(() => {
    const rows: FlattenedRow[] = [];
    Object.entries(props.state.data.resultRows).forEach(
      ([rowDigest, rowCollection]) => {
        Object.values(rowCollection.evaluations).forEach(modelCollection => {
          Object.values(modelCollection.predictAndScores).forEach(
            predictAndScoreRes => {
              const datasetRow =
                props.state.data.inputs[predictAndScoreRes.rowDigest];
              if (datasetRow != null) {
                const output = predictAndScoreRes.predictCall?.output;
                rows.push({
                  // ...predictAndScoreRes,
                  id: predictAndScoreRes.callId,
                  evaluationCallId: predictAndScoreRes.evaluationCallId,
                  inputDigest: datasetRow.digest,
                  inputRef: predictAndScoreRes.firstExampleRef,
                  input: flattenObject({input: datasetRow.val}),
                  output: flattenObject({output}),
                  latency: predictAndScoreRes.predictCall?.latencyMs ?? 0,
                  totalTokens:
                    predictAndScoreRes.predictCall?.totalUsageTokens ?? 0,
                  scores: Object.fromEntries(
                    Object.entries(scoreMap).map(([scoreKey, scoreVal]) => {
                      const hackKey = scoreVal.scoreKeyPath
                        .split('.')
                        .splice(1)
                        .join('.');
                      return [
                        scoreKey,
                        flattenObject(
                          predictAndScoreRes.scores[scoreVal.scorerRef]
                            ?.results ?? {}
                        )[hackKey],
                      ];
                    })
                  ),
                  path: [
                    rowDigest,
                    predictAndScoreRes.evaluationCallId,
                    predictAndScoreRes.callId,
                  ],
                });
              }
            }
          );
        });
      }
    );
    return rows;
  }, [props.state.data.inputs, props.state.data.resultRows, scoreMap]);

  // const filteredDigests = useMemo(() => {
  // }, []);
  // console.log({flattenedRows, scoreMap});
  const pivotedRows = useMemo(() => {
    // Ok, so in this step we are going to pivot -
    // id: string; - no change
    // inputDigest: string; - no change
    // input: {[inputKey: string]: any}; - no change
    // evaluationCallId: string; - Each key will be divided into new leafs
    // output: {[outputKey: string]: any}; - Each key will be divided into new leafs
    // scores: {[scoreId: string]: number | boolean}; - Each key will be divided into new leafs
    // latency: number; - Each key will be divided into new leafs
    // totalTokens: number; - Each key will be divided into new leafs
    // path: string[]; - no change
    const expandPrimitive = (obj: any, evaluationCallId: string) => {
      return Object.fromEntries(
        leafDims.map(d => {
          return [d, evaluationCallId === d ? obj : null];
        })
      );
    };

    const expandDict = (obj: any, evaluationCallId: string) => {
      return Object.fromEntries(
        Object.entries(obj).map(([key, val]) => {
          return [key, expandPrimitive(val, evaluationCallId)];
        })
      );
    };

    return flattenedRows.map(row => {
      return {
        ...row,
        evaluationCallId: expandPrimitive(
          row.evaluationCallId,
          row.evaluationCallId
        ),
        output: expandDict(row.output, row.evaluationCallId),
        scores: expandDict(row.scores, row.evaluationCallId),
        latency: expandPrimitive(row.latency, row.evaluationCallId),
        totalTokens: expandPrimitive(row.totalTokens, row.evaluationCallId),
      };
    }) as PivotedRow[];
  }, [flattenedRows, leafDims]);

  const aggregatedRows = useMemo(() => {
    const grouped = _.groupBy(pivotedRows, row => row.inputDigest);
    return Object.fromEntries(
      Object.entries(grouped).map(([inputDigest, rows]) => {
        return [
          inputDigest,
          {
            id: inputDigest, // required for the data grid
            count: rows.length,
            inputDigest,
            inputRef: rows[0].inputRef, // Should be the same for all,
            input: rows[0].input, // Should be the same for all
            output: aggregateGroupedNestedRows(
              rows,
              'output',
              vals => filterNones(vals)[0]
            ),
            scores: aggregateGroupedNestedRows(rows, 'scores', vals =>
              _.mean(
                filterNones(vals).map(v => {
                  if (typeof v === 'number') {
                    return v;
                  } else if (typeof v === 'boolean') {
                    return v ? 1 : 0;
                  } else {
                    return 0;
                  }
                })
              )
            ),
            latency: aggregateGroupedRows(rows, 'latency', vals =>
              _.mean(filterNones(vals))
            ),
            totalTokens: aggregateGroupedRows(rows, 'totalTokens', vals =>
              _.mean(filterNones(vals))
            ),
          },
        ];
      })
    );
  }, [pivotedRows]);

  const filteredRows = useMemo(() => {
    const aggregatedAsList = Object.values(aggregatedRows);
    if (props.state.rangeSelection) {
      const allowedDigests = Object.keys(aggregatedRows).filter(digest => {
        const values =
          aggregatedRows[digest].scores[
            scoreIdFromScoreDimension(props.state.comparisonDimension)
          ];
        return Object.entries(props.state.rangeSelection).every(
          ([key, val]) => {
            return val.min <= values[key] && values[key] <= val.max;
          }
        );
      });
      return aggregatedAsList.filter(row =>
        allowedDigests.includes(row.inputDigest)
      );
    }
    return aggregatedAsList;
  }, [
    aggregatedRows,
    props.state.comparisonDimension,
    props.state.rangeSelection,
  ]);

  const inputColumnKeys = useMemo(() => {
    const keys = new Set<string>();
    flattenedRows.forEach(row => {
      Object.keys(row.input).forEach(key => keys.add(key));
    });
    return keys;
  }, [flattenedRows]);

  const outputColumnKeys = useMemo(() => {
    const keys = new Set<string>();
    flattenedRows.forEach(row => {
      Object.keys(row.output).forEach(key => keys.add(key));
    });
    return keys;
  }, [flattenedRows]);

  const {cols: columns, grouping: groupingModel} = useMemo(() => {
    const cols: Array<GridColDef<(typeof flattenedRows)[number]>> = [];
    const grouping: GridColumnGroupingModel = [];
    // Columns:
    // 1. dataset row identifier
    // 2. dataset row contents (input)
    // (Grouped Aggregates - Model Outputs)
    // 3. Model Output (Grouping here is odd - likely just take last?)
    // 3.(n) -> split for each comparison
    // 4. Model Latency (average)
    // 4.(n) -> split for each comparison
    // 5. Model Tokens (average)
    // 5.(n) -> split for each comparison
    // (Grouped Aggregates - Scoring Function)
    // 6.(s) Each scoring key (average)
    // 6.(s).(n) -> split for each comparison
    const headerMap = Object.fromEntries(
      leafDims.map(dim => {
        const evalCall = props.state.data.evaluationCalls[dim];
        return [
          dim,
          <CallLink
            entityName={
              evalCall._rawEvaluationTraceData.project_id.split('/')[0]
            }
            projectName={
              evalCall._rawEvaluationTraceData.project_id.split('/')[1]
            }
            opName={evalCall._rawEvaluationTraceData.op_name}
            callId={dim}
            icon={<Circle sx={{color: evalCall.color, height: CIRCLE_SIZE}} />}
            noName
          />,
        ];
      })
    );

    const recursiveGetChildren = (
      params: GridValueGetterParams<(typeof flattenedRows)[number]>
    ) => {
      let rowNode = params.rowNode;
      while (rowNode.type === 'group') {
        rowNode = params.api.getRowNode(rowNode.children[0])!;
      }
      return params.api.getRow(rowNode.id);
    };

    const removePrefix = (key: string, prefix: string) => {
      if (key.startsWith(prefix)) {
        return key.slice(prefix.length);
      }
      return key;
    };

    const inputGroup: GridColumnGroup = {
      groupId: 'input',
      children: [],
    };

    cols.push({
      field: 'rowDigest',
      headerName: '',
      sortable: false,
      width: 30,
      renderHeader: params => {
        return (
          <HorizontalBox
            sx={{
              alignItems: 'center',
              justifyContent: 'center',
              width: '100%',
            }}>
            <Icon name={IconNames.LinkAlt} />
          </HorizontalBox>
        );
      },
      valueGetter: params => {
        return recursiveGetChildren(params).inputRef;
      },
      renderCell: params => {
        const refStr = params.value;
        const refParsed = parseRef(refStr) as WeaveObjectRef;
        return (
          <HorizontalBox
            sx={{
              alignItems: 'center',
              justifyContent: 'center',
              width: '100%',
            }}>
            <SmallRef objRef={refParsed} iconOnly />
          </HorizontalBox>
        );
      },
    });

    inputGroup.children.push({field: 'rowDigest'});

    inputColumnKeys.forEach(key => {
      cols.push({
        field: 'input.' + key,
        headerName: removePrefix(key, 'input.'),
        valueGetter: params => {
          return recursiveGetChildren(params).input[key];
        },
      });
      inputGroup.children.push({field: 'input.' + key});
    });
    grouping.push(inputGroup);

    const outputGroup: GridColumnGroup = {
      groupId: 'output',
      renderHeaderGroup: params => {
        return 'Output  (Last)';
      },
      children: [],
    };
    outputColumnKeys.forEach(key => {
      const outputSubGroup: GridColumnGroup = {
        groupId: 'output.' + key,
        renderHeaderGroup: params => {
          return removePrefix(key, 'output.');
        },
        children: [],
      };
      leafDims.forEach(dim => {
        cols.push({
          field: 'output.' + key + '.' + dim,
          flex: 1,
          // headerName: key + ' (Last)',
          // headerName: removePrefix(key, 'output.'),
          renderHeader: params => headerMap[dim],
          valueGetter: params => {
            return recursiveGetChildren(params).output[key][dim];
          },
        });
        outputSubGroup.children.push({field: 'output.' + key + '.' + dim});
      });
      outputGroup.children.push(outputSubGroup);
    });
    grouping.push(outputGroup);

    const latencyGroup: GridColumnGroup = {
      groupId: 'modelLatency',
      renderHeaderGroup: params => {
        return 'Latency (Avg)';
      },
      children: [],
    };
    leafDims.forEach(dim => {
      cols.push({
        field: 'modelLatency.' + dim,
        renderHeader: params => headerMap[dim],
        valueGetter: params => {
          return recursiveGetChildren(params).latency[dim];
        },
        renderCell: params => {
          return (
            <ValueViewNumber
              fractionDigits={SIGNIFICANT_DIGITS}
              value={params.value}
            />
          );
        },
      });
      latencyGroup.children.push({field: 'modelLatency.' + dim});
    });
    grouping.push(latencyGroup);

    const tokenGroup: GridColumnGroup = {
      groupId: 'totalTokens',
      renderHeaderGroup: params => {
        return 'Tokens (Avg)';
      },
      children: [],
    };
    leafDims.forEach(dim => {
      cols.push({
        field: 'totalTokens.' + dim,
        renderHeader: params => headerMap[dim],
        valueGetter: params => {
          return recursiveGetChildren(params).totalTokens[dim];
        },
        renderCell: params => {
          return (
            <ValueViewNumber
              fractionDigits={SIGNIFICANT_DIGITS}
              value={params.value}
            />
          );
        },
      });
      tokenGroup.children.push({field: 'totalTokens.' + dim});
    });
    grouping.push(tokenGroup);

    const scoresGroup: GridColumnGroup = {
      groupId: 'scores',
      renderHeaderGroup: params => {
        return 'Scores';
      },
      children: [],
    };
    Object.keys(scoreMap).forEach(scoreId => {
      const scoresSubGroup: GridColumnGroup = {
        groupId: 'scorer.' + scoreId,
        renderHeaderGroup: params => {
          const scorer = scoreMap[scoreId];
          const scorerRefParsed = parseRef(scorer.scorerRef) as WeaveObjectRef;

          return <SmallRef objRef={scorerRefParsed} />;
        },
        children: [],
      };
      leafDims.forEach(dim => {
        cols.push({
          field: 'scorer.' + scoreId + '.' + dim,
          renderHeader: params => headerMap[dim],
          valueGetter: params => {
            return recursiveGetChildren(params).scores[scoreId][dim];
          },
          renderCell: params => {
            return (
              <ValueViewNumber
                fractionDigits={SIGNIFICANT_DIGITS}
                value={params.value}
              />
            );
          },
        });
        scoresSubGroup.children.push({field: 'scorer.' + scoreId + '.' + dim});
      });
      scoresGroup.children.push(scoresSubGroup);
    });
    grouping.push(scoresGroup);

    return {cols, grouping};
  }, [
    inputColumnKeys,
    leafDims,
    outputColumnKeys,
    props.state.data.evaluationCalls,
    scoreMap,
  ]);

  const {setSelectedInputDigest} = useCompareEvaluationsState();

  // const getTreeDataPath: DataGridProProps['getTreeDataPath'] = row => row.path;
  return (
    <Box
      sx={{
        height: 'calc(100vh - 114px)',
        width: '100%',
        overflow: 'hidden',
      }}>
      <StyledDataGrid
        // Start Column Menu
        // ColumnMenu is only needed when we have other actions
        // such as filtering.
        disableColumnMenu={true}
        // In this context, we don't need to filter columns. I suppose
        // we can add this in the future, but we should be intentional
        // about what we enable.
        disableColumnFilter={true}
        disableMultipleColumnsFiltering={true}
        // ColumnPinning seems to be required in DataGridPro, else it crashes.
        disableColumnPinning={false}
        // There is no need to reorder the 2 columns in this context.
        disableColumnReorder={true}
        // Resizing columns might be helpful to show more data
        disableColumnResize={false}
        // There are only 2 columns, let's not confuse the user.
        disableColumnSelector={true}
        // We don't need to sort multiple columns.
        disableMultipleColumnsSorting={true}
        // End Column Menu
        // treeData
        // getTreeDataPath={row => row.path.toStringArray()}
        rows={filteredRows}
        columns={columns}
        // isGroupExpandedByDefault={node => {
        //   return expandedIds.includes(node.id);
        // }}
        columnHeaderHeight={38}
        rowHeight={60}
        experimentalFeatures={{columnGrouping: true}}
        columnGroupingModel={groupingModel}
        // groupingColDef={}
        // treeData
        // getTreeDataPath={getTreeDataPath}
        // getRowHeight={(params: GridRowHeightParams) => {
        //   const isNonRefString =
        //     params.model.valueType === 'string' && !isRef(params.model.value);
        //   const isArray = params.model.valueType === 'array';
        //   const isTableRef =
        //     isRef(params.model.value) &&
        //     (parseRefMaybe(params.model.value) as any).weaveKind === 'table';
        //   const {isCode} = params.model;
        //   if (
        //     isNonRefString ||
        //     (isArray && USE_TABLE_FOR_ARRAYS) ||
        //     isTableRef ||
        //     isCode
        //   ) {
        //     return 'auto';
        //   }
        //   return 38;
        // }}
        // hideFooter
        // rowSelection={false}
        // groupingColDef={groupingColDef}
        // rowSelection={true}
        // rowSelectionModel={
        //   props.state.selectedInputDigest
        //     ? [props.state.selectedInputDigest]
        //     : []
        // }
        // disableMultipleRowSelection
        // onRowSelectionModelChange={newSelection => {
        //   setSelectedInputDigest(newSelection[0].toString() ?? null);
        // }}
        sx={{
          '& .MuiDataGrid-cell': {
            textWrap: 'wrap !important',
            // whiteSpace: 'normal',
            overflow: 'auto !important',
            alignItems: 'flex-start',
            // textOverflow: 'ellipsis',
          },
        }}
      />
    </Box>
  );
};
