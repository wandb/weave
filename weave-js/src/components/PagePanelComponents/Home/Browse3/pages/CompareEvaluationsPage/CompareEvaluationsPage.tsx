import {Box, FormControl} from '@material-ui/core';
import {Autocomplete} from '@mui/material';
import {DataGridProProps, GridColDef} from '@mui/x-data-grid-pro';
import React, {FC, useCallback, useContext, useMemo} from 'react';
import {useHistory} from 'react-router-dom';

import {Button} from '../../../../../Button';
import {flattenObject} from '../../../Browse2/browse2Util';
import {
  useWeaveflowCurrentRouteContext,
  WeaveflowPeekContext,
} from '../../context';
import {StyledDataGrid} from '../../StyledDataGrid';
import {StyledTextField} from '../../StyledTextField';
import {useEvaluationsFilter} from '../CallsPage/CallsPage';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {
  CompareEvaluationsProvider,
  EvaluationComparisonState,
  useCompareEvaluationsState,
} from './compareEvaluationsContext';
import {
  BOX_RADIUS,
  PLOT_HEIGHT,
  PLOT_PADDING,
  STANDARD_BORDER,
  STANDARD_PADDING,
} from './constants';
import {EvaluationDefinition} from './EvaluationDefinition';
import {PredictAndScoreCall} from './evaluationResults';
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

const CompareEvaluationsCallsTable: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  // TODO: Grouping / Nesting

  const scores = useEvaluationCallDimensions(props.state);
  const scoreMap = useMemo(() => {
    return Object.fromEntries(
      scores.map(score => [scoreIdFromScoreDimension(score), score])
    );
  }, [scores]);

  const flattenedRows = useMemo(() => {
    const rows: Array<{
      id: string;
      inputDigest: string;
      input: {[inputKey: string]: any};
      output: {[outputKey: string]: any};
      scores: {[scoreId: string]: number | boolean};
      latency: number;
      totalTokens: number;
      // path: string[];
    }> = [];
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
                  inputDigest: datasetRow.digest,
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
                  // path: [rowDigest, predictAndScoreRes.callId],
                });
              }
            }
          );
        });
      }
    );
    return rows;
  }, [props.state.data.inputs, props.state.data.resultRows, scoreMap]);

  console.log({flattenedRows, scoreMap});
  const pivotedRows = useMemo(() => {
    const leafDims = Object.keys(props.state.data.evaluationCalls);
  }, []);

  const filteredRows = useMemo(() => {
    if (props.state.rangeSelection) {
      // Do something special to determine if this row qualifies
      // throw new Error('Not implemented');
      console.log(props.state.rangeSelection);
    }
  }, [props.state.rangeSelection]);

  // console.log(flattenedRows);

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

  const columns = useMemo(() => {
    const cols: Array<GridColDef<(typeof flattenedRows)[number]>> = [];

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

    cols.push({
      field: 'rowDigest',
      headerName: 'Row ID',
      valueGetter: params => {
        if (params.rowNode.type === 'group') {
          const childrenRows = params.rowNode.children.map(params.api.getRow);
          return childrenRows[0].rowDigest;
        }
        return params.row.inputDigest;
      },
    });

    // cols.push({
    //   field: 'rowContent',
    //   headerName: 'Row ID',
    //   valueGetter: params => {
    //     // TODO: This needs to be flattened...
    //     return params.row.input;
    //   },
    // });
    inputColumnKeys.forEach(key => {
      cols.push({
        field: 'input.' + key,
        headerName: key,
        valueGetter: params => {
          if (params.rowNode.type === 'group') {
            const childrenRows = params.rowNode.children.map(params.api.getRow);
            return childrenRows[0].input[key];
          }
          return params.row.input[key];
        },
      });
    });

    outputColumnKeys.forEach(key => {
      cols.push({
        field: 'output.' + key,
        headerName: key,
        valueGetter: params => {
          if (params.rowNode.type === 'group') {
            const childrenRows = params.rowNode.children.map(params.api.getRow);
            return childrenRows[0].output[key];
          }
          return params.row.output[key];
        },
      });
    });

    cols.push({
      field: 'modelLatency',
      headerName: 'Latency',
      valueGetter: params => {
        if (params.rowNode.type === 'group') {
          const childrenRows = params.rowNode.children.map(params.api.getRow);
          return childrenRows[0].latency;
        }
        return params.row.latency;
      },
    });

    cols.push({
      field: 'totalTokens',
      headerName: 'Tokens',
      valueGetter: params => {
        if (params.rowNode.type === 'group') {
          const childrenRows = params.rowNode.children.map(params.api.getRow);
          return childrenRows[0].totalTokens;
        }
        return params.row.totalTokens;
      },
    });

    Object.keys(scoreMap).forEach(scoreId => {
      // HAXS!
      cols.push({
        field: 'scorer.' + scoreId,
        headerName: scoreMap[scoreId].scoreKeyPath,
        valueGetter: params => {
          // console.log({fullKey, params});
          if (params.rowNode.type === 'group') {
            const childrenRows = params.rowNode.children.map(params.api.getRow);
            return childrenRows[0].scores[scoreId];
          }
          return params.row.scores[scoreId];
        },
      });
    });

    return cols;
  }, [inputColumnKeys, outputColumnKeys, scoreMap]);

  const getTreeDataPath: DataGridProProps['getTreeDataPath'] = row => row.path;

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
        disableColumnPinning={true}
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
        rows={flattenedRows}
        columns={columns}
        // isGroupExpandedByDefault={node => {
        //   return expandedIds.includes(node.id);
        // }}
        columnHeaderHeight={38}
        rowHeight={30}
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
      COMING SOON
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
 * TEST:
 * - [ ] Single Case
 * - [ ] Dual Case
 * - [ ] Multi Case
 */
