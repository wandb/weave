import {Box} from '@material-ui/core';
import {Alert} from '@mui/material';
import React, {useMemo} from 'react';

import {CustomWeaveTypeProjectContext} from '../../typeViews/CustomWeaveTypeDispatcher';
import {STANDARD_PADDING} from './ecpConstants';
import {EvaluationComparisonState} from './ecpState';
import {HorizontalBox, VerticalBox} from './Layout';
import {SummarizePlotsSection} from './sections/SummarizePlotsSection/SummarizePlotsSection';
import {TraceCallsSection} from './TraceCallsSection';

// SummarizeCallsSection component
export const SummarizeCallsSection: React.FC<{
  summarizeCalls: Array<{callId: string; traceCall: any}>;
  entity?: string;
  project?: string;
  state: EvaluationComparisonState;
}> = ({summarizeCalls, entity, project, state}) => {
  // Group calls by their parent evaluation
  const callsByParent = useMemo(() => {
    const grouped: Record<string, any[]> = {};

    summarizeCalls.forEach(call => {
      const parentId = call.traceCall?.parent_id || 'unknown';
      if (!grouped[parentId]) {
        grouped[parentId] = [];
      }
      grouped[parentId].push(call);
    });

    console.log('callsByParent', grouped);
    return grouped;
  }, [summarizeCalls]);

  // Column headers (evaluation IDs)
  const evaluationIds = useMemo(() => {
    // Get evaluation IDs in the same order as they appear in the state
    // Reverse the array to match the order in the rest of the UI
    return Object.keys(state.summary.evaluationCalls).reverse();
  }, [state.summary.evaluationCalls]);

  // Extract all unique metrics from all summarize calls
  const allMetrics = useMemo(() => {
    const metrics = new Set<string>();

    // For each parent evaluation that has summarize calls
    Object.entries(callsByParent).forEach(([parentId, calls]) => {
      if (calls.length > 0) {
        // Get the first call's output data
        const call = calls[0];
        const resultObj = call?.traceCall?.result_obj;
        const output = call?.traceCall?.output; // Check traceCall.output as indicated by user
        const inputs = call?.traceCall?.inputs || {};

        // Log to debug the actual data structure
        console.log(`Summarize call for ${parentId}:`, {
          resultObj,
          output,
          inputs,
          fullCall: call,
        });

        // Try various paths where metrics might be stored
        const potentialMetricsObjects = [
          output, // Direct output as mentioned by user
          resultObj, // Direct result object
          resultObj?.metrics, // Common pattern: {metrics: {...}}
          resultObj?.summary, // Common pattern: {summary: {...}}
          resultObj?.result, // Common pattern: {result: {...}}
          inputs?.summary, // Sometimes the summary is in the inputs
        ];

        // Check each potential path for metrics
        potentialMetricsObjects.forEach(metricsObj => {
          if (metricsObj && typeof metricsObj === 'object') {
            Object.keys(metricsObj).forEach(key => {
              metrics.add(key);
            });
          }
        });
      }
    });

    console.log('Found metrics:', Array.from(metrics));
    return Array.from(metrics).sort();
  }, [callsByParent]);

  // If no summarize calls, show message
  if (summarizeCalls.length === 0) {
    return (
      <Alert severity="info">
        No summarize calls found for the selected evaluations.
      </Alert>
    );
  }

  // If no metrics found, show message
  if (allMetrics.length === 0) {
    return (
      <Alert severity="info">
        No metrics data found in the summarize calls. Check the console for
        debugging information.
      </Alert>
    );
  }

  // Function to get metric value from a call
  const getMetricValue = (call: any, metricName: string) => {
    if (!call) return undefined;

    // Try various possible paths to find the metric
    const resultObj = call.traceCall?.result_obj;
    const output = call.traceCall?.output; // Check direct output as mentioned by user
    const inputs = call.traceCall?.inputs || {};

    // Check common paths where metrics might be stored
    const potentialSources = [
      output, // Direct output as mentioned by user
      resultObj, // Direct result object
      resultObj?.metrics, // Common pattern: {metrics: {...}}
      resultObj?.summary, // Common pattern: {summary: {...}}
      resultObj?.result, // Common pattern: {result: {...}}
      inputs?.summary, // Sometimes the summary is in the inputs
    ];

    // Look for the metric in each potential source
    for (const source of potentialSources) {
      if (
        source &&
        typeof source === 'object' &&
        source[metricName] !== undefined
      ) {
        return source[metricName];
      }
    }

    return undefined;
  };

  return (
    <VerticalBox
      sx={{
        height: '100%',
        width: '100%',
        gridGap: '0px',
      }}>
      {/* Main content area */}
      <Box
        sx={{
          flex: 1,
          overflow: 'auto',
          borderBottom: '1px solid #e0e0e0',
        }}>
        {/* Output section */}
        <Box
          sx={{
            borderBottom: '1px solid #e0e0e0',
            display: 'table',
            width: '100%',
          }}>
          {/* Header row */}
          <Box
            sx={{
              display: 'table-row',
              bgcolor: '#f5f5f5',
              fontWeight: 'bold',
            }}>
            <Box
              sx={{
                display: 'table-cell',
                width: '200px',
                padding: '8px 16px',
                borderRight: '1px solid #e0e0e0',
                borderBottom: '1px solid #e0e0e0',
                alignItems: 'center',
              }}>
              Metric
            </Box>
            {evaluationIds.map((evalId, colIndex) => (
              <Box
                key={evalId}
                sx={{
                  display: 'table-cell',
                  width: `calc((100% - 200px) / ${evaluationIds.length})`,
                  padding: '8px 16px',
                  borderRight:
                    colIndex < evaluationIds.length - 1
                      ? '1px solid #e0e0e0'
                      : 'none',
                  borderBottom: '1px solid #e0e0e0',
                  textAlign: 'center',
                  alignItems: 'center',
                }}>
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
                      bgcolor: state.summary.evaluationCalls[evalId].color,
                      marginRight: '8px',
                      flexShrink: 0,
                    }}
                  />
                  <Box
                    sx={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                    }}>
                    <span>
                      {state.summary.evaluationCalls[evalId].name || 'model'}
                    </span>
                    <Box
                      component="span"
                      sx={{fontSize: '0.9em', color: '#666'}}>
                      {evalId.slice(-4)}
                    </Box>
                  </Box>
                </Box>
              </Box>
            ))}
          </Box>

          {/* Render metrics from summarize calls */}
          {allMetrics.map((metricName, metricIndex) => {
            // Get a sample of this metric to determine type
            let sampleValue;
            for (const [evalId, calls] of Object.entries(callsByParent)) {
              if (calls.length > 0) {
                const value = getMetricValue(calls[0], metricName);
                if (value !== undefined) {
                  sampleValue = value;
                  break;
                }
              }
            }

            const isObject =
              typeof sampleValue === 'object' &&
              sampleValue !== null &&
              !Array.isArray(sampleValue);
            // Use alternating colors for parent rows
            const parentRowBgColor =
              metricIndex % 2 === 0 ? '#f8f8f8' : '#ffffff';

            return (
              <React.Fragment key={metricName}>
                {/* Parent row for metric */}
                <Box
                  sx={{
                    display: 'table-row',
                    bgcolor: parentRowBgColor,
                  }}>
                  <Box
                    sx={{
                      display: 'table-cell',
                      padding: '8px 16px',
                      fontWeight: 'bold',
                      borderRight: '1px solid #e0e0e0',
                      borderBottom: '1px solid #e0e0e0',
                      textAlign: 'left',
                      alignItems: 'center',
                    }}>
                    {metricName}
                  </Box>

                  {evaluationIds.map((evalId, colIndex) => {
                    // Find call for this evaluation
                    const evalCalls = callsByParent[evalId] || [];
                    const evalCall = evalCalls[0];
                    const value = evalCall
                      ? getMetricValue(evalCall, metricName)
                      : undefined;

                    return (
                      <Box
                        key={evalId}
                        sx={{
                          display: 'table-cell',
                          padding: '8px 16px',
                          borderRight:
                            colIndex < evaluationIds.length - 1
                              ? '1px solid #e0e0e0'
                              : 'none',
                          borderBottom: '1px solid #e0e0e0',
                          textAlign: 'center',
                          color: typeof value === 'object' ? '#666' : 'inherit',
                          fontStyle:
                            typeof value === 'object' ? 'italic' : 'normal',
                          alignItems: 'center',
                        }}>
                        {typeof value === 'object' && value !== null
                          ? `${Object.keys(value).length} properties`
                          : typeof value === 'number'
                          ? value.toFixed(4)
                          : value !== undefined
                          ? String(value)
                          : '-'}
                      </Box>
                    );
                  })}
                </Box>

                {/* Child rows for object properties */}
                {isObject &&
                  Object.entries(sampleValue).map(
                    ([subKey, subValue], subIdx) => {
                      // Use consistent alternating colors for child rows regardless of parent
                      const childRowBgColor =
                        (metricIndex % 2 === 0 && subIdx % 2 === 0) ||
                        (metricIndex % 2 === 1 && subIdx % 2 === 1)
                          ? '#f0f0f0'
                          : '#ffffff';

                      return (
                        <Box
                          key={`${metricName}.${subKey}`}
                          sx={{
                            display: 'table-row',
                            bgcolor: childRowBgColor,
                          }}>
                          <Box
                            sx={{
                              display: 'table-cell',
                              padding: '8px 16px 8px 32px', // Increased left padding to show hierarchy
                              fontWeight: 'normal',
                              borderRight: '1px solid #e0e0e0',
                              borderBottom: '1px solid #e0e0e0',
                              textAlign: 'left',
                              alignItems: 'center',
                            }}>
                            {subKey}
                          </Box>

                          {evaluationIds.map((evalId, colIndex) => {
                            // Find call for this evaluation
                            const evalCalls = callsByParent[evalId] || [];
                            const evalCall = evalCalls[0];
                            const parentValue = evalCall
                              ? getMetricValue(evalCall, metricName)
                              : undefined;
                            const nestedValue =
                              typeof parentValue === 'object' &&
                              parentValue !== null
                                ? parentValue[subKey]
                                : undefined;

                            return (
                              <Box
                                key={evalId}
                                sx={{
                                  display: 'table-cell',
                                  padding: '8px 16px',
                                  borderRight:
                                    colIndex < evaluationIds.length - 1
                                      ? '1px solid #e0e0e0'
                                      : 'none',
                                  borderBottom: '1px solid #e0e0e0',
                                  textAlign:
                                    typeof nestedValue === 'object'
                                      ? 'left'
                                      : 'center',
                                  alignItems: 'center',
                                }}>
                                {typeof nestedValue === 'object' &&
                                nestedValue !== null ? (
                                  <pre
                                    style={{
                                      margin: 0,
                                      fontSize: '0.9em',
                                      whiteSpace: 'pre-wrap',
                                      wordBreak: 'break-word',
                                      textAlign: 'left',
                                    }}>
                                    {JSON.stringify(nestedValue, null, 2)}
                                  </pre>
                                ) : typeof nestedValue === 'number' ? (
                                  nestedValue.toFixed(4)
                                ) : nestedValue !== undefined ? (
                                  String(nestedValue)
                                ) : (
                                  '-'
                                )}
                              </Box>
                            );
                          })}
                        </Box>
                      );
                    }
                  )}
              </React.Fragment>
            );
          })}
        </Box>
      </Box>
    </VerticalBox>
  );
};

interface TraceCallsCompareEvaluationsPageProps {
  height: number;
  traceCalls: Array<{callId: string; traceCall: any}>;
  summarizeCalls: Array<{callId: string; traceCall: any}>;
  state: EvaluationComparisonState;
}

export const TraceCallsCompareEvaluationsPage: React.FC<
  TraceCallsCompareEvaluationsPageProps
> = ({height, traceCalls, summarizeCalls, state}) => {
  const projectContext = React.useContext(CustomWeaveTypeProjectContext);

  return (
    <Box
      sx={{
        height,
        width: '100%',
        overflow: 'auto',
      }}>
      <VerticalBox
        sx={{
          paddingTop: STANDARD_PADDING,
          alignItems: 'flex-start',
          gridGap: STANDARD_PADDING * 2,
        }}>
        {/* Summarize Calls Section */}
        {summarizeCalls.length > 0 && (
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
                {/* Evaluation Summary */}
              </Box>
            </HorizontalBox>
            <Box
              sx={{
                height: 400, // Fixed height for plots section
                overflow: 'auto',
              }}>
              <SummarizePlotsSection
                summarizeCalls={summarizeCalls}
                state={state}
              />
            </Box>

            {/* Evaluation Summary Section */}
            <HorizontalBox
              sx={{
                flex: '0 0 auto',
                paddingLeft: STANDARD_PADDING,
                paddingRight: STANDARD_PADDING,
                width: '100%',
                alignItems: 'center',
                justifyContent: 'flex-start',
                marginTop: STANDARD_PADDING,
              }}>
              <Box
                sx={{
                  fontSize: '1.5em',
                  fontWeight: 'bold',
                }}>
                Summary
              </Box>
            </HorizontalBox>
            <Box
              sx={{
                height: 300, // Fixed height for summary section
                overflow: 'auto',
                marginTop: STANDARD_PADDING,
              }}>
              <SummarizeCallsSection
                summarizeCalls={summarizeCalls}
                entity={projectContext?.entity}
                project={projectContext?.project}
                state={state}
              />
            </Box>
          </VerticalBox>
        )}
        {/* Trace Calls Section */}
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
              Trace Call Outputs
            </Box>
          </HorizontalBox>
          <Box
            sx={{
              height: summarizeCalls.length > 0 ? height - 700 : height, // Adjust height based on whether summary sections are shown
              overflow: 'auto',
            }}>
            <TraceCallsSection
              traceCalls={traceCalls}
              entity={projectContext?.entity}
              project={projectContext?.project}
              state={state}
            />
          </Box>
        </VerticalBox>
      </VerticalBox>
    </Box>
  );
};
