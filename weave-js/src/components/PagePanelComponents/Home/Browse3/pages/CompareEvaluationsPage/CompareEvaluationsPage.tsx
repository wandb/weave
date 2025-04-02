/**
 * This is the entrypoint for the Evaluation Comparison Page.
 */

import {Box} from '@material-ui/core';
import {Alert} from '@mui/material';
import {WaveLoader} from '@wandb/weave/components/Loaders/WaveLoader';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {maybePluralizeWord} from '@wandb/weave/core/util/string';
import React, {FC, useCallback, useContext, useMemo, useState} from 'react';
import {useHistory} from 'react-router-dom';
import {AutoSizer} from 'react-virtualized';

import {Button} from '../../../../../Button';
import {
  useWeaveflowCurrentRouteContext,
  WeaveflowPeekContext,
} from '../../context';
import {CustomWeaveTypeProjectContext} from '../../typeViews/CustomWeaveTypeDispatcher';
import {useEvaluationsFilter} from '../CallsPage/evaluationsFilter';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {
  CompareEvaluationsProvider,
  useCompareEvaluationsState,
} from './compareEvaluationsContext';
import {STANDARD_PADDING} from './ecpConstants';
import {EvaluationComparisonState} from './ecpState';
import {ComparisonDimensionsType} from './ecpState';
import {EvaluationCall} from './ecpTypes';
import {EVALUATION_NAME_DEFAULT} from './ecpUtil';
import {HorizontalBox, VerticalBox} from './Layout';
import {ComparisonDefinitionSection} from './sections/ComparisonDefinitionSection/ComparisonDefinitionSection';
import {ExampleCompareSection} from './sections/ExampleCompareSection/ExampleCompareSection';
import {ExampleFilterSection} from './sections/ExampleFilterSection/ExampleFilterSection';
import {ScorecardSection} from './sections/ScorecardSection/ScorecardSection';
import {SummaryPlots} from './sections/SummaryPlotsSection/SummaryPlotsSection';
import {useWFHooks} from '../wfReactInterface/context';

// Add a new component for displaying trace calls
const TraceCallsSection: React.FC<{
  traceCalls: Array<{callId: string; traceCall: any}>;
}> = ({traceCalls}) => {
  // Group calls by their parent evaluation
  const callsByParent = useMemo(() => {
    const grouped: Record<string, any[]> = {};

    traceCalls.forEach(call => {
      const parentId = call.traceCall?.parent_id || 'unknown';
      if (!grouped[parentId]) {
        grouped[parentId] = [];
      }
      grouped[parentId].push(call);
    });

    return grouped;
  }, [traceCalls]);

  // Group calls by input pattern to show multiple examples
  const callsGroupedByInput = useMemo(() => {
    // Create a hash of the input to use as a grouping key
    const hashInput = (input: any) => {
      try {
        return JSON.stringify(input);
      } catch (e) {
        return String(input);
      }
    };

    const grouped: Record<string, Array<{evalId: string; call: any}>> = {};

    Object.entries(callsByParent).forEach(([evalId, calls]) => {
      calls.forEach(call => {
        const inputs = call.traceCall?.inputs || {};
        // Skip self and model inputs for grouping
        const relevantInputs = {...inputs};
        delete relevantInputs.self;
        delete relevantInputs.model;

        const inputHash = hashInput(relevantInputs);

        if (!grouped[inputHash]) {
          grouped[inputHash] = [];
        }

        grouped[inputHash].push({
          evalId,
          call,
        });
      });
    });

    return grouped;
  }, [callsByParent]);

  // Extract all unique inputs across all calls
  const uniqueInputKeys = useMemo(() => {
    const inputs = new Set<string>();
    traceCalls.forEach(call => {
      const callInputs = call.traceCall?.inputs || {};
      Object.keys(callInputs).forEach(key => {
        if (key !== 'self' && key !== 'model') {
          inputs.add(key);
        }
      });
    });
    return Array.from(inputs);
  }, [traceCalls]);

  // Column headers (evaluation IDs)
  const evaluationIds = Object.keys(callsByParent);

  if (traceCalls.length === 0) {
    return (
      <Alert severity="info">
        No trace calls found for the selected evaluations.
      </Alert>
    );
  }

  // Group inputs by example
  const inputGroups = Object.entries(callsGroupedByInput);

  return (
    <Box sx={{width: '100%', padding: STANDARD_PADDING}}>
      {inputGroups.map(([inputHash, callGroup], groupIndex) => (
        <Box key={inputHash} sx={{marginBottom: '32px'}}>
          <Box
            sx={{
              fontSize: '1.2em',
              fontWeight: 'bold',
              marginBottom: '8px',
              borderBottom: '1px solid #e0e0e0',
              paddingBottom: '8px',
            }}>
            Example {groupIndex + 1} of {inputGroups.length}
          </Box>

          {/* Input section */}
          <Box sx={{marginBottom: '24px'}}>
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: `200px repeat(${evaluationIds.length}, 1fr)`,
                borderBottom: '1px solid #e0e0e0',
                paddingBottom: '8px',
                fontWeight: 'bold',
              }}>
              <Box sx={{padding: '8px'}}>Value</Box>
              {evaluationIds.map(evalId => (
                <Box key={evalId} sx={{padding: '8px', textAlign: 'center'}}>
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}>
                    <Box
                      sx={{
                        width: '10px',
                        height: '10px',
                        borderRadius: '50%',
                        bgcolor:
                          evalId === evaluationIds[0] ? '#f06292' : '#42a5f5',
                        marginRight: '8px',
                      }}
                    />
                    model{' '}
                    <Box
                      component="span"
                      sx={{fontSize: '0.9em', color: '#666'}}>
                      {evalId.slice(-4)}
                    </Box>
                  </Box>
                </Box>
              ))}
            </Box>

            {/* Input rows */}
            {uniqueInputKeys.map((inputKey, index) => {
              // Get a sample call from this input group
              const sampleCall = callGroup[0]?.call;
              const inputValue = sampleCall?.traceCall?.inputs?.[inputKey];

              if (inputValue === undefined) return null;

              return (
                <Box
                  key={inputKey}
                  sx={{
                    display: 'grid',
                    gridTemplateColumns: `200px repeat(${evaluationIds.length}, 1fr)`,
                    borderBottom: '1px solid #f5f5f5',
                    bgcolor: index % 2 === 0 ? '#ffffff' : '#f9f9f9',
                  }}>
                  <Box sx={{padding: '8px', fontWeight: 'bold'}}>
                    {inputKey}
                  </Box>
                  {evaluationIds.map(evalId => {
                    const evalCall = callGroup.find(
                      c => c.evalId === evalId
                    )?.call;
                    const thisInputValue =
                      evalCall?.traceCall?.inputs?.[inputKey];
                    return (
                      <Box
                        key={evalId}
                        sx={{
                          padding: '8px',
                          borderLeft: '1px solid #f5f5f5',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}>
                        {thisInputValue !== undefined ? (
                          <Box
                            sx={{
                              maxHeight: '100px',
                              overflow: 'auto',
                            }}>
                            <pre
                              style={{
                                margin: 0,
                                fontSize: '0.9em',
                                whiteSpace: 'pre-wrap',
                                wordBreak: 'break-word',
                              }}>
                              {JSON.stringify(thisInputValue, null, 2)}
                            </pre>
                          </Box>
                        ) : (
                          '-'
                        )}
                      </Box>
                    );
                  })}
                </Box>
              );
            })}
          </Box>

          {/* Model Outputs Section */}
          <Box
            sx={{
              fontWeight: 'bold',
              borderBottom: '1px solid #e0e0e0',
              paddingBottom: '8px',
              marginBottom: '8px',
            }}>
            Model Outputs
          </Box>

          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: `200px repeat(${evaluationIds.length}, 1fr)`,
              borderBottom: '1px solid #f5f5f5',
              bgcolor: '#ffffff',
            }}>
            <Box sx={{padding: '8px', fontWeight: 'bold'}}>output</Box>
            {evaluationIds.map(evalId => {
              const evalCall = callGroup.find(c => c.evalId === evalId)?.call;
              const output = evalCall?.traceCall?.output;
              return (
                <Box
                  key={evalId}
                  sx={{
                    padding: '8px',
                    borderLeft: '1px solid #f5f5f5',
                    maxHeight: '300px',
                    overflow: 'auto',
                  }}>
                  {output !== undefined ? (
                    typeof output === 'object' ? (
                      <pre
                        style={{
                          margin: 0,
                          fontSize: '0.9em',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                        }}>
                        {JSON.stringify(output, null, 2)}
                      </pre>
                    ) : (
                      String(output)
                    )
                  ) : (
                    '-'
                  )}
                </Box>
              );
            })}
          </Box>

          {/* Metrics Section */}
          <Box
            sx={{
              marginTop: '24px',
              fontWeight: 'bold',
              borderBottom: '1px solid #e0e0e0',
              paddingBottom: '8px',
              marginBottom: '8px',
            }}>
            Metrics
          </Box>

          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: `200px repeat(${evaluationIds.length}, 1fr)`,
              borderBottom: '1px solid #f5f5f5',
              bgcolor: '#ffffff',
            }}>
            <Box sx={{padding: '8px', fontWeight: 'bold'}}>Model Latency</Box>
            {evaluationIds.map(evalId => {
              const evalCall = callGroup.find(c => c.evalId === evalId)?.call;
              // Attempt to extract latency from the traceCall
              const executionTime = evalCall?.traceCall?.execution_time;
              return (
                <Box
                  key={evalId}
                  sx={{padding: '8px', borderLeft: '1px solid #f5f5f5'}}>
                  {executionTime !== undefined
                    ? `${(executionTime * 1000).toFixed(3)}ms`
                    : '-'}
                </Box>
              );
            })}
          </Box>
        </Box>
      ))}
    </Box>
  );
};

type CompareEvaluationsPageProps = {
  entity: string;
  project: string;
  evaluationCallIds: string[];
  onEvaluationCallIdsUpdate: (newEvaluationCallIds: string[]) => void;
  selectedMetrics: Record<string, boolean> | null;
  setSelectedMetrics: (newModel: Record<string, boolean>) => void;
};

export const CompareEvaluationsPage: React.FC<
  CompareEvaluationsPageProps
> = props => {
  return (
    <SimplePageLayout
      title={
        props.evaluationCallIds.length === 1
          ? 'Evaluation Results'
          : 'Compare Evaluations'
      }
      hideTabsIfSingle
      tabs={[
        {
          label: 'All',
          content: (
            <CompareEvaluationsPageContent
              entity={props.entity}
              project={props.project}
              evaluationCallIds={props.evaluationCallIds}
              onEvaluationCallIdsUpdate={props.onEvaluationCallIdsUpdate}
              selectedMetrics={props.selectedMetrics}
              setSelectedMetrics={props.setSelectedMetrics}
            />
          ),
        },
      ]}
      headerExtra={<HeaderExtra {...props} />}
    />
  );
};

export const CompareEvaluationsPageContent: React.FC<
  CompareEvaluationsPageProps
> = props => {
  const [comparisonDimensions, setComparisonDimensions] =
    React.useState<ComparisonDimensionsType | null>(null);

  const [selectedInputDigest, setSelectedInputDigest] = React.useState<
    string | null
  >(null);

  // --------------------------------------

  const {useCalls} = useWFHooks();
  const childCalls = useCalls(props.entity, props.project, {
    parentIds: props.evaluationCallIds,
  });
  // console.log('childCalls', childCalls);

  // Access specific input fields (for example, if each child has a "prompt" input)
  const traceCalls = childCalls.result?.map(call => ({
    callId: call.callId,
    traceCall: call.traceCall,
    // Extract other specific inputs as needed
  }));

  console.log('traceCalls', traceCalls);

  // --------------------------------------

  const setComparisonDimensionsAndClearInputDigest = useCallback(
    (
      dimensions:
        | ComparisonDimensionsType
        | null
        | ((
            prev: ComparisonDimensionsType | null
          ) => ComparisonDimensionsType | null)
    ) => {
      if (typeof dimensions === 'function') {
        dimensions = dimensions(comparisonDimensions);
      }
      setComparisonDimensions(dimensions);
      setSelectedInputDigest(null);
    },
    [comparisonDimensions]
  );

  if (props.evaluationCallIds.length === 0) {
    return <div>No evaluations to compare</div>;
  }

  return (
    <CompareEvaluationsProvider
      entity={props.entity}
      project={props.project}
      initialEvaluationCallIds={props.evaluationCallIds}
      selectedMetrics={props.selectedMetrics}
      setSelectedMetrics={props.setSelectedMetrics}
      comparisonDimensions={comparisonDimensions ?? undefined}
      onEvaluationCallIdsUpdate={props.onEvaluationCallIdsUpdate}
      setComparisonDimensions={setComparisonDimensionsAndClearInputDigest}
      selectedInputDigest={selectedInputDigest ?? undefined}
      setSelectedInputDigest={setSelectedInputDigest}>
      <CustomWeaveTypeProjectContext.Provider
        value={{entity: props.entity, project: props.project}}>
        <AutoSizer style={{height: '100%', width: '100%'}}>
          {({height, width}) => (
            <CompareEvaluationsPageInner
              height={height}
              traceCalls={traceCalls}
            />
          )}
        </AutoSizer>
      </CustomWeaveTypeProjectContext.Provider>
    </CompareEvaluationsProvider>
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

const CompareEvaluationsPageInner: React.FC<{
  height: number;
  traceCalls?: Array<{callId: string; traceCall: any}>;
}> = props => {
  const {state, setSelectedMetrics} = useCompareEvaluationsState();
  const showExampleFilter =
    Object.keys(state.summary.evaluationCalls).length === 2;
  // const showExamples =
  //   Object.keys(state.loadableComparisonResults.result?.resultRows ?? {})
  //     .length > 0;

  const showExamples = true;
  console.log('showExampleFilter', showExampleFilter);
  console.log('showExamples', showExamples);
  const resultsLoading = state.loadableComparisonResults.loading;
  return (
    <Box
      sx={{
        height: props.height,
        width: '100%',
        overflow: 'auto',
      }}>
      <VerticalBox
        sx={{
          paddingTop: STANDARD_PADDING,
          alignItems: 'flex-start',
          gridGap: STANDARD_PADDING * 2,
        }}>
        <InvalidEvaluationBanner
          evaluationCalls={Object.values(state.summary.evaluationCalls)}
        />
        <ComparisonDefinitionSection state={state} />
        <SummaryPlots state={state} setSelectedMetrics={setSelectedMetrics} />
        <ScorecardSection state={state} />
        {resultsLoading ? (
          <Box
            sx={{
              width: '100%',
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              height: '50px',
            }}>
            <WaveLoader size="small" />
          </Box>
        ) : showExamples ? (
          <>
            {showExampleFilter && <ExampleFilterSection state={state} />}
            <ResultExplorer
              state={state}
              height={props.height}
              traceCalls={props.traceCalls}
            />
          </>
        ) : (
          <VerticalBox
            sx={{
              // alignItems: '',
              paddingLeft: STANDARD_PADDING,
              paddingRight: STANDARD_PADDING,
              width: '100%',
              overflow: 'auto',
            }}>
            <Box
              sx={{
                fontSize: '1.5em',
                fontWeight: 'bold',
              }}>
              Examples
            </Box>
            <Alert severity="info">
              The selected evaluations' datasets have 0 rows in common, try
              comparing evaluations with datasets that have at least one row in
              common.
            </Alert>
          </VerticalBox>
        )}
      </VerticalBox>
    </Box>
  );
};

const ResultExplorer: React.FC<{
  state: EvaluationComparisonState;
  height: number;
  traceCalls?: Array<{callId: string; traceCall: any}>;
}> = ({state, height, traceCalls}) => {
  return (
    <VerticalBox
      sx={{
        width: '100%',
        overflow: 'hidden',
      }}>
      <HorizontalBox
        sx={{
          flex: '0 0 auto',
          paddingLeft: STANDARD_PADDING,
          paddingRight: STANDARD_PADDING,
          width: '100%',
          alignItems: 'center',
          justifyContent: 'flex-start',
        }}>
        <Box
          sx={{
            fontSize: '1.5em',
            fontWeight: 'bold',
          }}>
          {traceCalls && traceCalls.length > 0
            ? 'Trace Call Outputs'
            : 'Output Comparison'}
        </Box>
      </HorizontalBox>
      <Box
        sx={{
          height,
          overflow: 'auto',
        }}>
        {traceCalls && traceCalls.length > 0 ? (
          <TraceCallsSection traceCalls={traceCalls} />
        ) : (
          <ExampleCompareSection state={state} />
        )}
      </Box>
    </VerticalBox>
  );
};

/*
 * Returns true if the evaluation call has summary metrics.
 */
const isValidEval = (evalCall: EvaluationCall) => {
  return Object.keys(evalCall.summaryMetrics).length > 0;
};

const InvalidEvaluationBanner: React.FC<{
  evaluationCalls: EvaluationCall[];
}> = ({evaluationCalls}) => {
  const [dismissed, setDismissed] = useState(false);
  const invalidEvals = useMemo(() => {
    return Object.values(evaluationCalls)
      .filter(call => !isValidEval(call))
      .map(call =>
        call.name !== EVALUATION_NAME_DEFAULT
          ? call.name
          : call.callId.slice(-4)
      );
  }, [evaluationCalls]);
  if (invalidEvals.length === 0 || dismissed) {
    return null;
  }
  return (
    <Box
      sx={{
        width: '100%',
        paddingLeft: STANDARD_PADDING,
        paddingRight: STANDARD_PADDING,
      }}>
      <Tailwind>
        <Alert
          severity="info"
          classes={{
            root: 'bg-teal-300/[0.30] text-teal-600',
            action: 'text-teal-600',
          }}
          action={
            <Button
              // override the default tailwind classes for text and background hover
              className="text-override hover:bg-override"
              variant="ghost"
              onClick={() => setDismissed(true)}>
              Dismiss
            </Button>
          }>
          <span style={{fontWeight: 'bold'}}>
            No summary information found for{' '}
            {maybePluralizeWord(invalidEvals.length, 'evaluation')}:{' '}
            {invalidEvals.join(', ')}.
          </span>
        </Alert>
      </Tailwind>
    </Box>
  );
};
