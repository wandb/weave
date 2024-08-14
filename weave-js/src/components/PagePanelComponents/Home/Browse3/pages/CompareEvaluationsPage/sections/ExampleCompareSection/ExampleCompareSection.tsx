import {Box, Tooltip} from '@material-ui/core';
import {Circle, WarningAmberOutlined} from '@mui/icons-material';
import _ from 'lodash';
import React, {useCallback, useEffect, useMemo, useRef} from 'react';
import styled from 'styled-components';

import {
  MOON_100,
  MOON_200,
  MOON_300,
  MOON_800,
} from '../../../../../../../../common/css/color.styles';
import {parseRef, WeaveObjectRef} from '../../../../../../../../react';
import {Button} from '../../../../../../../Button';
import {CellValue} from '../../../../../Browse2/CellValue';
import {NotApplicable} from '../../../../../Browse2/NotApplicable';
import {parseRefMaybe, SmallRef} from '../../../../../Browse2/SmallRef';
import {ValueViewNumber} from '../../../CallPage/ValueViewNumber';
import {CallLink} from '../../../common/Links';
import {isRef} from '../../../common/util';
import {useCompareEvaluationsState} from '../../compareEvaluationsContext';
import {
  buildCompositeMetricsMap,
  CompositeSummaryMetricGroupForKeyPath,
  resolvePeerDimension,
} from '../../compositeMetricsUtil';
import {DERIVED_SCORER_REF_PLACEHOLDER} from '../../compositeMetricsUtil';
import {CIRCLE_SIZE, SIGNIFICANT_DIGITS} from '../../ecpConstants';
import {EvaluationComparisonState} from '../../ecpState';
import {MetricDefinition, MetricValueType} from '../../ecpTypes';
import {metricDefinitionId} from '../../ecpUtil';
import {getMetricIds} from '../../ecpUtil';
import {dimensionUnit, flattenedDimensionPath} from '../../ecpUtil';
import {usePeekCall} from '../../hooks';
import {HorizontalBox, VerticalBox} from '../../Layout';
import {
  ComparisonPill,
  SCORER_VARIATION_WARNING_EXPLANATION,
  SCORER_VARIATION_WARNING_TITLE,
} from '../ScorecardSection/ScorecardSection';
import {
  PivotedRow,
  useFilteredAggregateRows,
} from './exampleCompareSectionUtil';

const SIDEBAR_WIDTH_PX = 250;
const MIN_EVAL_WIDTH_PX = 350;
const HEADER_HEIGHT_PX = 38;
const TOP_CELL_PADDING_PX = 4;
const SHOW_INPUT_HEADER = true;

const PropKey = styled.div`
  position: sticky;
  top: ${TOP_CELL_PADDING_PX}px;
  overflow: auto;
  text-align: right;
  scrollbar-width: none;
`;

const GridCell = styled.div<{
  colSpan?: number;
  rowSpan?: number;
  button?: boolean;
}>`
  border: 1px solid ${MOON_200};
  grid-column-end: span ${props => props.colSpan || 1};
  grid-row-end: span ${props => props.rowSpan || 1};
  padding: ${TOP_CELL_PADDING_PX}px 8px;
  background-color: white;
  // Hover should show click mouse icon
  // and slowly highlight blue like a button
  ${props =>
    props.button &&
    `
    cursor: pointer;
    transition: background-color 0.2s;
    &:hover {
      background-color: ${MOON_300};
    }
  `}
`;

const GridCellSubgrid = styled.div<{
  colSpan?: number;
  rowSpan?: number;
  colsTemp?: string;
  rowsTemp?: string;
}>`
  grid-column-end: span ${props => props.colSpan || 1};
  grid-row-end: span ${props => props.rowSpan || 1};
  padding: 0px;
  background-color: white;
  display: grid;
  grid-template-rows: ${props => props.rowsTemp || 'subgrid'};
  grid-template-columns: ${props => props.colsTemp || 'subgrid'};
  overflow: auto;
`;

const GridContainer = styled.div<{colsTemp: string; rowsTemp: string}>`
  display: grid;
  overflow: auto;
  grid-template-columns: ${props => props.colsTemp};
  grid-template-rows: ${props => props.rowsTemp};
`;

const centeredTextStyleMixin: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  textAlign: 'center',
};

const stickyHeaderStyleMixin: React.CSSProperties = {
  ...centeredTextStyleMixin,
  position: 'sticky',
  top: 0,
  zIndex: 1,
  backgroundColor: MOON_100,
  fontWeight: 'bold',
};

const stickySidebarStyleMixin: React.CSSProperties = {
  position: 'sticky',
  left: 0,
  zIndex: 1,
  backgroundColor: MOON_100,
  fontWeight: 'bold',
};

const stickySidebarHeaderMixin: React.CSSProperties = {
  ...stickyHeaderStyleMixin,
  ...stickySidebarStyleMixin,
  zIndex: 2,
};

/**
 * This component will occupy the entire space provided by the parent container.
 * It is intended to be used in teh CompareEvaluations page, as it depends on
 * the EvaluationComparisonState. However, in principle, it is a general purpose
 * model-output comparison tool. It allows the user to view inputs, then compare
 * model outputs and evaluation metrics across multiple trials.
 *
 * The UX design is quite complex and particular. It uses a series of nested
 * grids to achieve the desired layout, which contains many rules for stickiness
 * and scrolling. Getting this to work correctly was a significant challenge.
 * The basic idea is:
 *    * There are 3 main sections, stacked vertically: Input, Model Outputs, and
 *      Metrics
 *        * Each of these sections has a sticky header
 *    * The left sticky sidebar contains the property keys for each section.
 *        * A special case are the metrics, which are grouped by the scoring
 *          function
 *    * The input section only has one "value" column. It should scroll
 *      vertically, but not horizontally
 *    * The model outputs section has a column for each evaluation/model. These
 *      will scroll vertically and horizontally
 *    * The metrics section has a column for each evaluation (aligned with the
 *      model outputs) and then further subdivides into a column for each trial
 *
 *       * THe nested inner trial grid needs to also scroll horizontally and
 *         vertically with it's own inner nested sticky header and sidebar
 *    * The Input and Metrics section are designed to be as small as possible,
 *      with extra space given to the Model Outputs section
 *       * When there is not enough vertical space, all sections should flex
 *         down equally, sharing the space - resulting in all panels always in
 *         view.
 *
 * Since grid system layouts often are not as easy to iterate, I pulled out all
 * the data lookup logic into their own functions so future devs can just focus
 * on the layout, without mixing in the data logic.
 *
 * As of this writing, there are 2 remaining style/UX challenges for this
 * component: There are 2 remaining style/UX challenges for this component:
 *
 * 1. "Fixed-Width Sidebar" - Due the how the grid system works, we cannot have
 *    a sidebar width that responds to the content. It must be fixed.
 *    * Options: allow the users to drag the sidebar width; use a ref to get the
 *      largest width of the sidebar and set all to that width
 * 2. "Sticky Metric Trial Headers": Due to how the grid system works, I could
 *    not get the metric headers to be sticky. I tried many things, but could
 *    not get it to work, while maintaining the desired layout. Challenge for
 *    future devs.
 *    * Example. Go here and make the screen quite small - notice the 3rd eval's trials don't have sticky headers
 *      https://wandb.ai/shawn/humaneval6/weave/compare-evaluations?evaluationCallIds=%5B%2258c9db2c-c1f8-4643-a79d-7a13c55fbc72%22%2C%228563f89b-07e8-4042-9417-e22b4257bf95%22%2C%2232f3e6bc-5488-4dd4-b9c4-801929f2c541%22%2C%2234c0a20f-657f-407e-bb33-277abbb9997f%22%5D
 */

export const ExampleCompareSection: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  const {
    filteredRows,
    outputColumnKeys,
    leafDims: orderedCallIds,
  } = useFilteredAggregateRows(props.state);
  const {setSelectedInputDigest} = useCompareEvaluationsState();
  const targetIndex = useMemo(() => {
    const selectedDigest = props.state.selectedInputDigest;
    if (selectedDigest) {
      const found = filteredRows.findIndex(
        row => row.inputDigest === selectedDigest
      );
      if (found !== -1) {
        return found;
      }
    }
    return 0;
  }, [filteredRows, props.state.selectedInputDigest]);

  const target = useMemo(() => {
    return filteredRows[targetIndex];
  }, [filteredRows, targetIndex]);

  const [selectedTrials, setSelectedTrials] = React.useState<{
    [evalCallId: string]: number;
  }>({});

  const onScorerClick = usePeekCall(
    props.state.data.entity,
    props.state.data.project
  );

  const {ref1, ref2} = useLinkHorizontalScroll();

  const compositeScoreMetrics = useMemo(
    () => buildCompositeMetricsMap(props.state.data, 'score'),
    [props.state.data]
  );

  if (target == null) {
    return <div>Filter resulted in 0 rows</div>;
  }

  // This section contains the primary helper variable for laying out the grid
  const metricGroupNames = Object.keys(compositeScoreMetrics).filter(
    k => k !== DERIVED_SCORER_REF_PLACEHOLDER
  );

  const inputRef = parseRef(target.inputRef) as WeaveObjectRef;
  const inputColumnKeys = Object.keys(target.input);
  const numInputProps = inputColumnKeys.length;
  const numOutputKeys = outputColumnKeys.length;

  const numTrials = orderedCallIds.map(leafId => {
    return target.originalRows.filter(row => row.evaluationCallId === leafId)
      .length;
  });
  const numEvals = numTrials.length;
  const derivedScores = Object.values(
    getMetricIds(props.state.data, 'score', 'derived')
  );
  const numMetricScorers = metricGroupNames.length;
  const numDerivedScores = derivedScores.length;
  const numMetricsPerScorer = [
    ...metricGroupNames.map(groupName => {
      return Object.keys(compositeScoreMetrics[groupName].metrics).length;
    }),
    numDerivedScores,
  ];
  const totalMetrics = _.sum(numMetricsPerScorer);

  // This section contains a bunch of helper functions used to lookup
  // data for the grid layout. Originally all this stuff was inlined
  // in the JSX, but it was a mess and hard to iterate on. This way
  // we can focus on the layout and not the data.
  //
  // A few conventions:
  //   * Pretty much everything operates on indexes of the different dimensions:
  //      `inputProp`: A single input property
  //      `outputProp`: A single output property
  //      `eval`: A single evaluation
  //      `trial`: A single trial (index is within an evaluation)
  //      `scorer`: A single scorer
  //      `metric`: A single metric (index is within a scorer)
  //   * `lookup*` helper functions to get the data for a specific dimension
  //   * `[DIMENSION]MapKey` is used to get the key for a component when mapping.
  //   * `[DIMENSION][PROP]Comp` specific component for a dimension's property
  const BASELINE_EVAL_INDEX = 0;

  const lookupIsDerivedMetric = (scorerIndex: number): boolean => {
    return scorerIndex === numMetricScorers;
  };

  const lookupTrialsForEval = (evalIndex: number): PivotedRow[] => {
    const currEvalCallId = orderedCallIds[evalIndex];
    return target.originalRows.filter(
      row => row.evaluationCallId === currEvalCallId
    );
  };

  const lookupSelectedTrialIndexForEval = (evalIndex: number): number => {
    const currEvalCallId = orderedCallIds[evalIndex];
    return selectedTrials[currEvalCallId] || 0;
  };

  const lookupSelectedTrialForEval = (
    evalIndex: number
  ): PivotedRow | undefined => {
    const trialsForThisEval = lookupTrialsForEval(evalIndex);
    return trialsForThisEval[lookupSelectedTrialIndexForEval(evalIndex)];
  };

  const lookupScoreGroupForScorerIndex = (scorerIndex: number) => {
    return compositeScoreMetrics[metricGroupNames[scorerIndex]];
  };

  const lookupScoreGroupMetricsForScorerIndex = (scorerIndex: number) => {
    return lookupScoreGroupForScorerIndex(scorerIndex).metrics;
  };

  const lookupUniqueScorerRefsForScorerIndex = (
    scorerIndex: number
  ): string[] => {
    return lookupScoreGroupForScorerIndex(scorerIndex).scorerRefs;
  };

  const lookupDimensionsForScorer = (
    scorerIndex: number
  ): MetricDefinition[] => {
    const isDerivedMetric = lookupIsDerivedMetric(scorerIndex);
    const lookupAnyDimensionForMetric = (
      sm: CompositeSummaryMetricGroupForKeyPath
    ) => {
      return Object.values(sm.scorerRefs)[0].metric;
    };

    if (isDerivedMetric) {
      return derivedScores;
    }
    return Object.values(
      lookupScoreGroupMetricsForScorerIndex(scorerIndex)
    ).map(lookupAnyDimensionForMetric);
  };

  const lookupDimension = (
    scorerIndex: number,
    metricIndex: number
  ): MetricDefinition => {
    const dimensionsForThisScorer = lookupDimensionsForScorer(scorerIndex);
    return dimensionsForThisScorer[metricIndex];
  };

  const lookupDimensionId = (
    scorerIndex: number,
    metricIndex: number
  ): string => {
    return metricDefinitionId(lookupDimension(scorerIndex, metricIndex));
  };

  const lookupTargetTrial = (
    evalIndex: number,
    trialIndex: number
  ): PivotedRow => {
    const trialsForThisEval = lookupTrialsForEval(evalIndex);
    return trialsForThisEval[trialIndex];
  };

  const lookupMetricValue = (
    evalIndex: number,
    trialIndex: number,
    scorerIndex: number,
    metricIndex: number
  ): MetricValueType | undefined => {
    const targetTrial = lookupTargetTrial(evalIndex, trialIndex);
    const currEvalCallId = orderedCallIds[evalIndex];
    const resolvedScoreId = resolvePeerDimension(
      compositeScoreMetrics,
      currEvalCallId,
      lookupDimension(scorerIndex, metricIndex)
    );

    if (resolvedScoreId == null) {
      return undefined;
    }

    return targetTrial.scores[metricDefinitionId(resolvedScoreId)][
      currEvalCallId
    ];
  };

  const lookupAggScorerMetricValue = (
    evalIndex: number,
    scorerIndex: number,
    metricIndex: number
  ): MetricValueType | undefined => {
    const currEvalCallId = orderedCallIds[evalIndex];
    const resolvedScoreId = resolvePeerDimension(
      compositeScoreMetrics,
      currEvalCallId,
      lookupDimension(scorerIndex, metricIndex)
    );

    if (resolvedScoreId == null) {
      return undefined;
    }

    return target.scores[metricDefinitionId(resolvedScoreId)][currEvalCallId];
  };

  const lookupOutputValue = (
    evalIndex: number,
    outputPropIndex: number
  ): any => {
    const currEvalCallId = orderedCallIds[evalIndex];
    const selectedTrial = lookupSelectedTrialForEval(evalIndex);

    return (selectedTrial?.output?.[outputColumnKeys[outputPropIndex]] ?? {})[
      currEvalCallId
    ];
  };

  // End helpers, start layout

  const inputPropMapKey = (inputPropIndex: number) => {
    return inputColumnKeys[inputPropIndex];
  };

  const inputPropKeyComp = (inputPropIndex: number) => {
    return (
      <PropKey
        style={{
          top:
            TOP_CELL_PADDING_PX +
            (SHOW_INPUT_HEADER ? 1 + HEADER_HEIGHT_PX : 0),
        }}>
        {removePrefix(inputColumnKeys[inputPropIndex], 'input.')}
      </PropKey>
    );
  };

  const inputPropValComp = (inputPropIndex: number) => {
    return (
      <ICValueView value={target.input[inputColumnKeys[inputPropIndex]]} />
    );
  };

  const outputPropMapKey = (outputPropIndex: number) => {
    return outputColumnKeys[outputPropIndex];
  };

  const outputKeyComp = (outputPropIndex: number) => {
    return (
      <PropKey
        style={{
          top: TOP_CELL_PADDING_PX + 1 + HEADER_HEIGHT_PX,
        }}>
        {removePrefix(outputPropMapKey(outputPropIndex), 'output.')}
      </PropKey>
    );
  };

  const evalMapKey = (evalIndex: number) => {
    return orderedCallIds[evalIndex];
  };

  const evalSelectedTrialPredictCallComp = (evalIndex: number) => {
    const currEvalCallId = orderedCallIds[evalIndex];
    const selectedTrial = lookupSelectedTrialForEval(evalIndex);
    if (selectedTrial == null) {
      return null;
    }
    const trialPredict = selectedTrial.predictAndScore._rawPredictTraceData;
    const [trialEntity, trialProject] =
      trialPredict?.project_id.split('/') ?? [];
    const trialOpName = parseRefMaybe(
      trialPredict?.op_name ?? ''
    )?.artifactName;
    const trialCallId = trialPredict?.id;
    const evaluationCall = props.state.data.evaluationCalls[currEvalCallId];
    if (trialEntity && trialProject && trialOpName && trialCallId) {
      return (
        <Box
          style={{
            overflow: 'hidden',
          }}>
          <CallLink
            entityName={trialEntity}
            projectName={trialProject}
            opName={trialOpName}
            callId={trialCallId}
            icon={
              <Circle
                sx={{
                  color: evaluationCall.color,
                  height: CIRCLE_SIZE,
                }}
              />
            }
            color={MOON_800}
          />
        </Box>
      );
    }
    return null;
  };

  const evalOutputValueComp = (evalIndex: number, outputPropIndex: number) => {
    const value = lookupOutputValue(evalIndex, outputPropIndex);
    return <ICValueView value={value} />;
  };

  const evalTrialSelectComp = (evalIndex: number, trialIndex: number) => {
    const currEvalCallId = orderedCallIds[evalIndex];
    const selectedTrialNdx = lookupSelectedTrialIndexForEval(evalIndex);
    return (
      <Button
        size="small"
        variant={selectedTrialNdx === trialIndex ? 'primary' : 'secondary'}
        onClick={() => {
          setSelectedTrials(curr => {
            return {
              ...curr,
              [currEvalCallId]: trialIndex,
            };
          });
        }}
        icon="show-visible">
        {trialIndex.toString()}
      </Button>
    );
  };

  const evalAggScorerMetricComp = (
    evalIndex: number,
    scorerIndex: number,
    metricIndex: number
  ) => {
    const dimension = lookupDimension(scorerIndex, metricIndex);
    const unit = dimensionUnit(dimension, true);
    const isBinary = dimension.scoreType === 'binary';
    const summaryMetric = adjustValueForDisplay(
      lookupAggScorerMetricValue(evalIndex, scorerIndex, metricIndex),
      isBinary
    );
    const baseline = adjustValueForDisplay(
      lookupAggScorerMetricValue(BASELINE_EVAL_INDEX, scorerIndex, metricIndex),
      isBinary
    );

    const lowerIsBetter = dimension.shouldMinimize ?? false;

    if (summaryMetric == null) {
      return <NotApplicable />;
    }

    return (
      <HorizontalBox
        style={{
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
        <HorizontalBox
          style={{
            alignItems: 'center',
            gap: '1px',
          }}>
          <ValueViewNumber
            fractionDigits={SIGNIFICANT_DIGITS}
            value={summaryMetric}
          />
          {unit}
        </HorizontalBox>
        <ComparisonPill
          value={summaryMetric}
          baseline={baseline}
          metricUnit={unit}
          metricLowerIsBetter={lowerIsBetter}
        />
      </HorizontalBox>
    );
  };

  const evalTrialScorerMetricValueComp = (
    evalIndex: number,
    trialIndex: number,
    scorerIndex: number,
    metricIndex: number
  ) => {
    const metricValue = lookupMetricValue(
      evalIndex,
      trialIndex,
      scorerIndex,
      metricIndex
    );
    if (metricValue == null) {
      return <NotApplicable />;
    }

    return <CellValue value={metricValue} />;
  };

  const evalTrialScorerMetricOnClick = (
    evalIndex: number,
    trialIndex: number,
    scorerIndex: number,
    metricIndex: number
  ) => {
    const scoreId = lookupDimensionId(scorerIndex, metricIndex);
    const targetTrial = lookupTargetTrial(evalIndex, trialIndex);

    if (lookupIsDerivedMetric(scorerIndex)) {
      return undefined;
    }
    return () =>
      onScorerClick(
        targetTrial.predictAndScore.scoreMetrics[scoreId].sourceCallId
      );
  };

  const scorerComp = (scorerIndex: number) => {
    if (lookupIsDerivedMetric(scorerIndex)) {
      return null;
    }
    const scorerRefs = lookupUniqueScorerRefsForScorerIndex(scorerIndex);

    let inner: JSX.Element | null = null;
    if (scorerRefs.length === 0) {
      inner = null;
    } else if (scorerRefs.length === 1) {
      const parsedRef = parseRef(scorerRefs[0]);
      inner = <SmallRef objRef={parsedRef as WeaveObjectRef} iconOnly />;
    } else {
      inner = (
        <Tooltip
          title={
            SCORER_VARIATION_WARNING_TITLE +
            ': ' +
            SCORER_VARIATION_WARNING_EXPLANATION
          }>
          <WarningAmberOutlined color="warning" />
        </Tooltip>
      );
    }

    return (
      <VerticalBox
        style={{
          alignItems: 'center',
          justifyContent: 'center',
          width: '100%',
          height: '100%',
          paddingLeft: '2px',
        }}>
        {inner}
      </VerticalBox>
    );
  };

  const scorerMetricKeyComp = (scorerIndex: number, metricIndex: number) => {
    const dimensionsForThisScorer = lookupDimensionsForScorer(scorerIndex);
    return (
      <PropKey>
        {flattenedDimensionPath(dimensionsForThisScorer[metricIndex])}
      </PropKey>
    );
  };

  const header = (
    <HorizontalBox
      sx={{
        justifyContent: 'space-between',
        alignItems: 'center',
        bgcolor: MOON_100,
        padding: '16px',
        borderBottom: '1px solid #ccc',
      }}>
      <HorizontalBox
        sx={{
          alignItems: 'center',
          flex: 1,
        }}>
        <Box
          style={{
            flex: 0,
          }}>
          <SmallRef objRef={inputRef} iconOnly />
        </Box>
        <Box
          style={{
            flex: 1,
          }}>
          {`Example ${targetIndex + 1} of ${filteredRows.length}`}
        </Box>
      </HorizontalBox>
      <Box>
        <Button
          className="mx-16"
          style={{
            marginLeft: '0px',
          }}
          size="small"
          disabled={targetIndex === 0}
          onClick={() => {
            setSelectedInputDigest(filteredRows[targetIndex - 1].inputDigest);
          }}
          icon="chevron-back"
        />

        <Button
          style={{
            marginLeft: '0px',
          }}
          disabled={targetIndex === filteredRows.length - 1}
          size="small"
          onClick={() => {
            setSelectedInputDigest(filteredRows[targetIndex + 1].inputDigest);
          }}
          icon="chevron-next"
        />
      </Box>
    </HorizontalBox>
  );

  return (
    // The outermost container
    <VerticalBox
      sx={{
        height: '100%',
        width: '100%',
        gridGap: '0px',
      }}>
      {/* Insert the header */}
      {header}
      {/* Setup the outermost grid. Notice the rowsTemp - this is key to having
      the input and metric sections flex down when there is not enough space, and
      the model outputs get the extra space.
       */}
      <GridContainer
        colsTemp={'auto'}
        rowsTemp={`fit-content(100%) auto fit-content(100%)`}
        style={{
          height: '100%',
          flex: 1,
        }}>
        {/* INPUT SECTION */}
        <GridCellSubgrid
          rowSpan={1}
          colSpan={1}
          rowsTemp={`repeat(${
            numInputProps + (SHOW_INPUT_HEADER ? 1 : 0)
          }, auto)`}
          colsTemp={`${SIDEBAR_WIDTH_PX}px auto`}>
          {/* INPUT HEADER */}
          {SHOW_INPUT_HEADER && (
            <React.Fragment>
              <GridCell style={{...stickySidebarHeaderMixin}}>Input</GridCell>
              <GridCell style={{...stickyHeaderStyleMixin}}>Value</GridCell>
            </React.Fragment>
          )}
          {/* INPUT ROWS */}
          {_.range(numInputProps).map(inputPropIndex => {
            return (
              <React.Fragment key={inputPropMapKey(inputPropIndex)}>
                <GridCell style={{...stickySidebarStyleMixin}}>
                  {inputPropKeyComp(inputPropIndex)}
                </GridCell>
                <GridCell>{inputPropValComp(inputPropIndex)}</GridCell>
              </React.Fragment>
            );
          })}
        </GridCellSubgrid>
        {/* OUTPUT SECTION */}
        <GridCellSubgrid
          ref={ref1}
          rowSpan={1}
          colSpan={1}
          rowsTemp={`${HEADER_HEIGHT_PX}px repeat(${numOutputKeys}, auto)`}
          colsTemp={`${SIDEBAR_WIDTH_PX}px repeat(${numEvals}, minmax(${MIN_EVAL_WIDTH_PX}px, 1fr))`}
          style={{
            scrollbarWidth: 'none',
          }}>
          {/* OUTPUT HEADER */}
          <React.Fragment>
            <GridCell style={{...stickySidebarHeaderMixin}}>
              Model Outputs
            </GridCell>
            {_.range(numEvals).map(evalIndex => {
              return (
                <GridCell
                  key={evalMapKey(evalIndex)}
                  style={{...stickyHeaderStyleMixin}}>
                  {evalSelectedTrialPredictCallComp(evalIndex)}
                </GridCell>
              );
            })}
          </React.Fragment>
          {/* OUTPUT ROWS */}
          {_.range(numOutputKeys).map(outputPropIndex => {
            return (
              <React.Fragment key={outputPropMapKey(outputPropIndex)}>
                <GridCell style={{...stickySidebarStyleMixin}}>
                  {outputKeyComp(outputPropIndex)}
                </GridCell>
                {_.range(numEvals).map(evalIndex => {
                  return (
                    <GridCell key={evalMapKey(evalIndex)}>
                      {evalOutputValueComp(evalIndex, outputPropIndex)}
                    </GridCell>
                  );
                })}
              </React.Fragment>
            );
          })}
        </GridCellSubgrid>
        {/* METRIC SECTION */}
        <GridCellSubgrid
          ref={ref2}
          rowSpan={1}
          colSpan={1}
          rowsTemp={`${HEADER_HEIGHT_PX}px repeat(${totalMetrics}, auto)`}
          colsTemp={`${SIDEBAR_WIDTH_PX}px repeat(${numEvals}, minmax(${MIN_EVAL_WIDTH_PX}px, 1fr))`}>
          {/* METRIC HEADER */}
          <React.Fragment>
            <GridCell
              style={{
                // in a perfect world, this would be STICKY_SIDEBAR_HEADER,
                // but I can't get the eval metric headers to be sticky. I
                // have spent many hours trying to pull this one off and need
                // to move on. The result is that the metrics headers (and trial selection
                // buttons) will scroll off the screen. Not horrible, but a defeat.
                ...stickySidebarStyleMixin,
                ...centeredTextStyleMixin,
                zIndex: 3,
              }}>
              Metrics
            </GridCell>
            {/* METRIC VALUES */}
            {_.range(numEvals).map(evalIndex => {
              const TRIALS_FOR_EVAL = numTrials[evalIndex];

              // EVAL METRIC SUBGRID
              return (
                <GridCellSubgrid
                  key={evalMapKey(evalIndex)}
                  rowSpan={totalMetrics + 1}
                  colSpan={1}
                  colsTemp={`min-content repeat(${TRIALS_FOR_EVAL} , auto)`}>
                  {/* TRIALS HEADER */}
                  <GridCell style={{...stickySidebarHeaderMixin}}>
                    Trials
                  </GridCell>
                  {_.range(TRIALS_FOR_EVAL).map(trialIndex => {
                    return (
                      <GridCell
                        key={trialIndex}
                        style={{...stickyHeaderStyleMixin}}>
                        {evalTrialSelectComp(evalIndex, trialIndex)}
                      </GridCell>
                    );
                  })}

                  {/* TRIALS VALUES */}
                  {numMetricsPerScorer.map((numMetrics, scorerIndex) => {
                    return _.range(numMetrics).map(metricIndex => {
                      return (
                        <React.Fragment
                          key={
                            scorerIndex.toString() +
                            '.' +
                            metricIndex.toString()
                          }>
                          <GridCell style={{...stickySidebarStyleMixin}}>
                            {evalAggScorerMetricComp(
                              evalIndex,
                              scorerIndex,
                              metricIndex
                            )}
                          </GridCell>
                          {_.range(TRIALS_FOR_EVAL).map(trialIndex => {
                            const onClick = evalTrialScorerMetricOnClick(
                              evalIndex,
                              trialIndex,
                              scorerIndex,
                              metricIndex
                            );

                            return (
                              <GridCell
                                key={trialIndex}
                                button={onClick != null}
                                onClick={onClick}>
                                {evalTrialScorerMetricValueComp(
                                  evalIndex,
                                  trialIndex,
                                  scorerIndex,
                                  metricIndex
                                )}
                              </GridCell>
                            );
                          })}
                        </React.Fragment>
                      );
                    });
                  })}
                </GridCellSubgrid>
              );
            })}
          </React.Fragment>

          {/* SCORER / METRIC KEYS */}
          <GridCellSubgrid
            rowSpan={totalMetrics}
            colSpan={1}
            colsTemp={`45px ${SIDEBAR_WIDTH_PX - 45}px`}
            style={{...stickySidebarStyleMixin}}>
            {numMetricsPerScorer.map((NUM_METRICS_FOR_SCORER, scorerIndex) => {
              return (
                <React.Fragment key={scorerIndex}>
                  <GridCell
                    style={{...stickySidebarStyleMixin}}
                    rowSpan={NUM_METRICS_FOR_SCORER}>
                    {scorerComp(scorerIndex)}
                  </GridCell>
                  {_.range(NUM_METRICS_FOR_SCORER).map(metricIndex => {
                    return (
                      <GridCell
                        key={metricIndex}
                        style={{
                          backgroundColor: MOON_100,
                        }}>
                        {scorerMetricKeyComp(scorerIndex, metricIndex)}
                      </GridCell>
                    );
                  })}
                </React.Fragment>
              );
            })}
          </GridCellSubgrid>
        </GridCellSubgrid>
      </GridContainer>
    </VerticalBox>
  );
};

const removePrefix = (key: string, prefix: string) => {
  if (key.startsWith(prefix)) {
    return key.slice(prefix.length);
  }
  return key;
};

const ICValueView: React.FC<{value: any}> = ({value}) => {
  let text = '';
  if (value == null) {
    return <NotApplicable />;
  } else if (typeof value === 'object') {
    text = JSON.stringify(value || {}, null, 2);
  } else if (typeof value === 'string' && isRef(value)) {
    return <SmallRef objRef={parseRef(value)} />;
  } else {
    text = value.toString();
  }

  text = trimWhitespace(text);

  return (
    <pre
      style={{
        whiteSpace: 'pre-wrap',
        textAlign: 'left',
        wordBreak: 'break-all',
        padding: 0,
        margin: 0,
      }}>
      {text}
    </pre>
  );
};
const trimWhitespace = (str: string) => {
  // Trim leading and trailing whitespace
  return str.replace(/^\s+|\s+$/g, '');
};

/**
 * Allows 2 divs to scroll horizontally in sync. The user
 * should be able to scroll either div and the other should
 * scroll as well.
 */
const useLinkHorizontalScroll = () => {
  const ref1 = useRef<HTMLDivElement>(null);
  const ref2 = useRef<HTMLDivElement>(null);

  const scroll1Handler = useCallback(() => {
    if (ref1.current && ref2.current) {
      ref2.current.scrollLeft = ref1.current.scrollLeft;
    }
  }, []);

  const scroll2Handler = useCallback(() => {
    if (ref1.current && ref2.current) {
      ref1.current.scrollLeft = ref2.current.scrollLeft;
    }
  }, []);

  useEffect(() => {
    const ref1Current = ref1.current;
    const ref2Current = ref2.current;

    if (ref1Current) {
      ref1Current.addEventListener('scroll', scroll1Handler);
    }

    if (ref2Current) {
      ref2Current.addEventListener('scroll', scroll2Handler);
    }

    return () => {
      if (ref1Current) {
        ref1Current.removeEventListener('scroll', scroll1Handler);
      }
      if (ref2Current) {
        ref2Current.removeEventListener('scroll', scroll2Handler);
      }
    };
  }, [scroll1Handler, scroll2Handler]);

  return {ref1, ref2};
};

const adjustValueForDisplay = (
  value: number | boolean | undefined,
  isBooleanAggregate?: boolean
): number | undefined => {
  if (value === undefined) {
    return undefined;
  }
  if (typeof value === 'boolean') {
    return value ? 100 : 0;
  } else if (isBooleanAggregate) {
    return value * 100;
  } else {
    return value;
  }
};
