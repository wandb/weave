import {Box, FormControl} from '@material-ui/core';
import {Circle} from '@mui/icons-material';
import {Autocomplete} from '@mui/material';
import {
  GridColDef,
  GridColumnGroup,
  GridColumnGroupingModel,
  GridValueGetterParams,
} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {FC, useCallback, useContext, useMemo} from 'react';
import {useHistory} from 'react-router-dom';

import {parseRef, WeaveObjectRef} from '../../../../../../react';
import {Button} from '../../../../../Button';
import {Icon, IconNames} from '../../../../../Icon';
import {flattenObject} from '../../../Browse2/browse2Util';
import {SmallRef} from '../../../Browse2/SmallRef';
import {
  useWeaveflowCurrentRouteContext,
  WeaveflowPeekContext,
} from '../../context';
import {StyledDataGrid} from '../../StyledDataGrid';
import {StyledTextField} from '../../StyledTextField';
import {ValueViewNumber} from '../CallPage/ValueViewNumber';
import {useEvaluationsFilter} from '../CallsPage/CallsPage';
import {CallLink} from '../common/Links';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {
  CompareEvaluationsProvider,
  EvaluationComparisonState,
  useCompareEvaluationsState,
} from './compareEvaluationsContext';
import {
  BOX_RADIUS,
  CIRCLE_SIZE,
  PLOT_HEIGHT,
  PLOT_PADDING,
  SIGNIFICANT_DIGITS,
  STANDARD_BORDER,
  STANDARD_PADDING,
} from './constants';
import {EvaluationDefinition} from './EvaluationDefinition';
import {evaluationMetrics, ScoreDimension} from './evaluations';
import {RangeSelection, useEvaluationCallDimensions} from './initialize';
import {HorizontalBox, VerticalBox} from './Layout';
import {PlotlyBarPlot} from './PlotlyBarPlot';
import {PlotlyRadarPlot, RadarPlotData} from './PlotlyRadarPlot';
import {ScatterFilter} from './ScatterFilter';
import {moveItemToFront, ScoreCard} from './Scorecard';

type CompareEvaluationsPageProps = {
  entity: string;
  project: string;
  evaluationCallIds: string[];
};

export const CompareEvaluationsPage: React.FC<
  CompareEvaluationsPageProps
> = props => {
  const [baselineEvaluationCallId, setBaselineEvaluationCallId] =
    React.useState(
      props.evaluationCallIds.length > 0 ? props.evaluationCallIds[0] : null
    );
  // console.log(baselineEvaluationCallId);
  const [comparisonDimension, setComparisonDimension] =
    React.useState<ScoreDimension | null>(null);

  const [rangeSelection, setRangeSelection] = React.useState<RangeSelection>(
    {}
  );

  const setComparisonDimensionAndClearRange = useCallback(
    (
      dim:
        | ScoreDimension
        | null
        | ((prev: ScoreDimension | null) => ScoreDimension | null)
    ) => {
      if (typeof dim === 'function') {
        dim = dim(comparisonDimension);
      }
      setComparisonDimension(dim);
      setRangeSelection({});
    },
    [comparisonDimension]
  );

  if (props.evaluationCallIds.length === 0) {
    return <div>No evaluations to compare</div>;
  }

  return (
    <SimplePageLayout
      title={'Compare Evaluations'}
      hideTabsIfSingle
      tabs={[
        {
          label: 'All',
          content: (
            <CompareEvaluationsProvider
              entity={props.entity}
              project={props.project}
              evaluationCallIds={props.evaluationCallIds}
              baselineEvaluationCallId={baselineEvaluationCallId ?? undefined}
              comparisonDimension={comparisonDimension ?? undefined}
              rangeSelection={rangeSelection}
              setBaselineEvaluationCallId={setBaselineEvaluationCallId}
              setComparisonDimension={setComparisonDimensionAndClearRange}
              setRangeSelection={setRangeSelection}>
              <CompareEvaluationsPageInner />
            </CompareEvaluationsProvider>
          ),
        },
      ]}
      headerExtra={<HeaderExtra {...props} />}
    />
  );
};

const HeaderExtra: React.FC<CompareEvaluationsPageProps> = props => {
  const {isPeeking} = useContext(WeaveflowPeekContext);
  return (
    <>
      {!isPeeking ? (
        <ReturnToEvaluationsButton
          entity={props.entity}
          project={props.project}
        />
      ) : null}
    </>
  );
};

const ReturnToEvaluationsButton: FC<{entity: string; project: string}> = ({
  entity,
  project,
}) => {
  const history = useHistory();
  const router = useWeaveflowCurrentRouteContext();
  const evaluationsFilter = useEvaluationsFilter(entity, project);
  const onClick = useCallback(() => {
    history.push(router.callsUIUrl(entity, project, evaluationsFilter));
  }, [entity, evaluationsFilter, history, project, router]);
  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        alignItems: 'center',
      }}>
      <Button
        className="mx-16"
        style={{
          marginLeft: '0px',
        }}
        size="medium"
        variant="secondary"
        onClick={onClick}
        icon="back">
        Return to Evaluations
      </Button>
    </Box>
  );
};

const CompareEvaluationsPageInner: React.FC = props => {
  const {state} = useCompareEvaluationsState();

  return (
    <Box
      sx={{
        height: '100%',
        width: '100%',
        overflow: 'auto',
      }}>
      <VerticalBox
        sx={{
          paddingTop: STANDARD_PADDING,
          alignItems: 'flex-start',
        }}>
        <ComparisonDefinition state={state} />
        <SummaryPlots state={state} />
        <ScoreCard state={state} />
        {Object.keys(state.data.models).length === 2 && (
          <ScatterFilter state={state} />
        )}
        <CompareEvaluationsCallsTable state={state} />
      </VerticalBox>
    </Box>
  );
};

const SummaryPlots: React.FC<{state: EvaluationComparisonState}> = props => {
  const plotlyRadarData = useNormalizedRadarPlotDataFromMetrics(props.state);

  return (
    <HorizontalBox
      sx={{
        paddingLeft: STANDARD_PADDING,
        paddingRight: STANDARD_PADDING,
        flex: '1 1 auto',
        width: '100%',
      }}>
      <Box
        sx={{
          flex: '1 0 auto',
          height: PLOT_HEIGHT,
          // width: PLOT_HEIGHT * 2,
          borderRadius: BOX_RADIUS,
          border: STANDARD_BORDER,
          overflow: 'hidden',
          alignContent: 'center',
        }}>
        <PlotlyRadarPlot height={PLOT_HEIGHT} data={plotlyRadarData} />
        {/* <PlotlyRadarPlot /> */}
        {/* // <PlotlyRadialPlot /> */}
      </Box>
      <Box
        sx={{
          flex: '1 1 auto',
          height: PLOT_HEIGHT,
          width: '100%',
          overflow: 'hidden',
          borderRadius: BOX_RADIUS,
          border: STANDARD_BORDER,
          padding: PLOT_PADDING,
        }}>
        <PlotlyBarPlot height={PLOT_HEIGHT} data={plotlyRadarData} />
      </Box>
      {/* <RadarPlot plotlyRadarData={plotlyRadarData} />
      <BarPlots plotlyRadarData={plotlyRadarData}} /> */}
    </HorizontalBox>
  );
};

const normalizeValues = (values: number[]): number[] => {
  // find the max value
  // find the power of 2 that is greater than the max value
  // divide all values by that power of 2
  const maxVal = Math.max(...values);
  const maxPower = Math.ceil(Math.log2(maxVal));
  return values.map(val => val / 2 ** maxPower);
};

const useNormalizedRadarPlotDataFromMetrics = (
  state: EvaluationComparisonState
): RadarPlotData => {
  const metrics = useMemo(() => {
    return evaluationMetrics(state);
  }, [state]);

  return useMemo(() => {
    const normalizedMetrics = metrics.map(metric => {
      const keys = Object.keys(metric.values);
      const values = keys.map(key => metric.values[key]);
      const normalizedValues = normalizeValues(values);

      return {
        ...metric,
        values: Object.fromEntries(
          keys.map((key, i) => [key, normalizedValues[i]])
        ),
      };
    });
    return Object.fromEntries(
      Object.values(state.data.evaluationCalls).map(evalCall => {
        return [
          evalCall.callId,
          {
            name: evalCall.name,
            color: evalCall.color,
            metrics: Object.fromEntries(
              normalizedMetrics.map(metric => {
                return [metric.path, metric.values[evalCall.callId]];
              })
            ),
          },
        ];
      })
    );
  }, [metrics, state.data.evaluationCalls]);
};

const ComparisonDefinition: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  const evalCallIds = useMemo(() => {
    const all = Object.keys(props.state.data.evaluationCalls);
    // Make sure the baseline model is first
    moveItemToFront(all, props.state.baselineEvaluationCallId);
    return all;
  }, [props.state.baselineEvaluationCallId, props.state.data.evaluationCalls]);

  return (
    <HorizontalBox
      sx={{
        alignItems: 'center',
        paddingLeft: STANDARD_PADDING,
        paddingRight: STANDARD_PADDING,
      }}>
      {evalCallIds.map((key, ndx) => {
        return (
          <React.Fragment key={key}>
            {ndx !== 0 && <SwapPositionsButton callId={key} />}
            <EvaluationDefinition state={props.state} callId={key} />
          </React.Fragment>
        );
      })}
      <DefinitionText text="target metric " />
      <DimensionPicker {...props} />
    </HorizontalBox>
  );
};

const DefinitionText: React.FC<{text: string}> = props => {
  return <Box>{props.text}</Box>;
};

const dimensionToText = (dim: ScoreDimension): string => {
  return dim.scorerRef + '/' + dim.scoreKeyPath;
};

const DimensionPicker: React.FC<{state: EvaluationComparisonState}> = props => {
  const currDimension = props.state.comparisonDimension;
  const dimensions = useEvaluationCallDimensions(props.state);
  const {setComparisonDimension} = useCompareEvaluationsState();
  // console.log(dimensions);
  const dimensionMap = useMemo(() => {
    return Object.fromEntries(
      dimensions.map(dim => [dimensionToText(dim), dim])
    );
  }, [dimensions]);

  return (
    <FormControl>
      <Autocomplete
        size="small"
        disableClearable
        limitTags={1}
        value={dimensionToText(currDimension)}
        onChange={(event, newValue) => {
          // console.log('onChange', newValue);
          // TODO: THis is incorrect!
          // throw new Error('Not implemented');
          setComparisonDimension(dimensionMap[newValue]!);
        }}
        getOptionLabel={option => {
          // Not quite correct since there could be multiple scorers with the same name
          return dimensionMap[option]?.scoreKeyPath ?? option;
        }}
        options={Object.keys(dimensionMap)}
        renderInput={renderParams => (
          <StyledTextField
            {...renderParams}
            value={dimensionToText(currDimension)}
            label={'Dimension'}
            sx={{width: '300px'}}
          />
        )}
      />
    </FormControl>
  );
};

const SwapPositionsButton: React.FC<{callId: string}> = props => {
  const {setBaselineEvaluationCallId} = useCompareEvaluationsState();
  return (
    <Button
      size="medium"
      variant="quiet"
      onClick={() => {
        // console.log('setting', props.callId);
        setBaselineEvaluationCallId(props.callId);
      }}
      icon="retry"
    />
  );
};

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

const CompareEvaluationsCallsTable: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  const leafDims = useMemo(() => {
    const initial = Object.keys(props.state.data.evaluationCalls);
    moveItemToFront(initial, props.state.baselineEvaluationCallId);
    return initial;
  }, [props.state.baselineEvaluationCallId, props.state.data.evaluationCalls]);
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

  // const getTreeDataPath: DataGridProProps['getTreeDataPath'] = row => row.path;

  return (
    <Box sx={{height: '500px', width: '100%', overflow: 'hidden'}}>
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
        rowHeight={30}
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
        rowSelection={false}
        sx={{}}
      />
      {/* COMING SOON */}
      {/* <CallsTable
        entity={props.entity}
        project={props.project}
        frozenFilter={callsFilter}
        hideControls
      /> */}
    </Box>
  );
};

/**
 * TOOD:
 * - [ ] Allow user to select primary metric & save to local storage + URL
 * - [ ] Wireup the baseline replace button
 * - [ ] Fix Plot to show correct data
 * - [ ] Build grouping
 * - [ ] Add scorer links in scorecard
 * - [ ] Definition header does not scale small enough
 * - [ ] The data model has gotten messy - figure out a good way to include costs
 * - [ ] Auto-expand first-level properties (see prompt here: https://app.wandb.test/wandb-designers/signal-maven/weave/compare-evaluations?evaluationCallIds=%5B%22bf5188ba-48cd-4c6d-91ea-e25464570c13%22%2C%222f4544f3-9649-487e-b083-df6985e21b12%22%2C%228cbeccd6-6ff7-4eac-a305-6fb6450530f1%22%5D)
 * - [ ] The damn thing is slow with all the upfront loading
 * - [ ] // TODO: find all cases of the `_raw*` cases and remove them!'
 * - [ ] Support arbitrarily nested scorers
 * - [ ] Add latency and tokens (and cost) to the scoring / plotting system more generally
 * - [ ] Failed evals break!
 * - [ ] Objects/Arrays/Refs are not suppported. see https://app.wandb.test/wandb-smle/weave-rag-lc-demo/weave/compare-evaluations?evaluationCallIds=%5B%2221e8ea02-3109-434c-95d0-cb2c7c542f74%22%5D&peekPath=%2Fwandb-smle%2Fweave-rag-lc-demo%2Fcalls%2F21e8ea02-3109-434c-95d0-cb2c7c542f74
 * TEST:
 * - [ ] Single Case
 * - [ ] Dual Case
 * - [ ] Multi Case
 */
