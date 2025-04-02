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
  // Pagination state - must be at the top level of the component
  const [currentExampleIndex, setCurrentExampleIndex] = useState(0);

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

  // Group inputs by example
  const inputGroups = Object.entries(callsGroupedByInput);

  // If no trace calls, show message
  if (traceCalls.length === 0) {
    return (
      <Alert severity="info">
        No trace calls found for the selected evaluations.
      </Alert>
    );
  }

  // If no examples, show message
  if (inputGroups.length === 0) {
    return <Alert severity="info">No examples available to display.</Alert>;
  }

  // Guard against out-of-bounds index after re-renders
  const safeCurrentIndex = Math.min(
    currentExampleIndex,
    inputGroups.length - 1
  );
  const currentExample = inputGroups[safeCurrentIndex];

  // Add the ComparisonPill component
  const TraceCallComparisonPill: React.FC<{
    value: number | undefined;
    baseline: number | undefined;
    metricUnit?: string;
    metricLowerIsBetter?: boolean;
  }> = ({value, baseline, metricUnit = '', metricLowerIsBetter = false}) => {
    if (value === undefined || baseline === undefined) {
      return null;
    }

    const diff = value - baseline;
    const diffFixed = Number.isInteger(diff)
      ? diff.toLocaleString()
      : diff.toFixed(4); // Use 4 decimal places for precision

    const showPill = diff !== 0;
    if (!showPill) {
      return null;
    }

    // Determine color based on whether higher or lower is better
    let pillColor = 'moon';
    if (diff > 0) {
      pillColor = metricLowerIsBetter ? 'red' : 'green';
    } else if (diff < 0) {
      pillColor = metricLowerIsBetter ? 'green' : 'red';
    }

    // Create the pill label with sign
    const pillLabel = `${diff > 0 ? '+' : ''}${diffFixed}${metricUnit}`;

    return (
      <Box
        sx={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: '50px',
          padding: '2px 8px',
          fontSize: '12px',
          fontWeight: 'bold',
          bgcolor:
            pillColor === 'green'
              ? 'rgba(0, 200, 83, 0.2)'
              : pillColor === 'red'
              ? 'rgba(244, 67, 54, 0.2)'
              : 'rgba(160, 174, 192, 0.2)',
          color:
            pillColor === 'green'
              ? '#00c853'
              : pillColor === 'red'
              ? '#f44336'
              : '#718096',
          marginLeft: '8px',
        }}>
        {pillLabel}
      </Box>
    );
  };

  return (
    <VerticalBox
      sx={{
        height: '100%',
        width: '100%',
        gridGap: '0px',
      }}>
      {/* Pagination header for examples */}
      <HorizontalBox
        sx={{
          justifyContent: 'space-between',
          alignItems: 'center',
          bgcolor: '#f5f5f5',
          padding: '16px',
          borderBottom: '1px solid #ccc',
        }}>
        <HorizontalBox
          sx={{
            alignItems: 'center',
            flex: 1,
          }}>
          <Box sx={{fontSize: '14px'}}>
            {`Example ${safeCurrentIndex + 1} of ${inputGroups.length}`}
          </Box>
        </HorizontalBox>
        <Box>
          <Button
            className="mx-16"
            style={{marginLeft: '0px'}}
            size="small"
            disabled={safeCurrentIndex === 0}
            onClick={() => setCurrentExampleIndex(prev => prev - 1)}
            icon="chevron-back"
          />
          <Button
            style={{marginLeft: '0px'}}
            disabled={safeCurrentIndex === inputGroups.length - 1}
            size="small"
            onClick={() => setCurrentExampleIndex(prev => prev + 1)}
            icon="chevron-next"
          />
        </Box>
      </HorizontalBox>

      {/* Main content area */}
      <Box
        sx={{
          flex: 1,
          overflow: 'auto',
          borderBottom: '1px solid #e0e0e0',
        }}>
        {/* Input section */}
        <Box sx={{borderBottom: '1px solid #e0e0e0'}}>
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: `200px repeat(${evaluationIds.length}, 1fr)`,
              bgcolor: '#f5f5f5',
              fontWeight: 'bold',
            }}>
            <Box
              sx={{
                padding: '8px 16px',
                borderRight: '1px solid #e0e0e0',
                borderBottom: '1px solid #e0e0e0',
              }}>
              Input
            </Box>
            <Box
              sx={{
                gridColumn: `2 / span ${evaluationIds.length}`,
                padding: '8px 16px',
                borderBottom: '1px solid #e0e0e0',
              }}>
              Value
            </Box>
          </Box>

          {/* Input rows */}
          {uniqueInputKeys.map((inputKey, index) => {
            // Get a sample call from this input group - use currentExample
            const sampleCall = currentExample[1][0]?.call;
            const inputValue = sampleCall?.traceCall?.inputs?.[inputKey];

            if (inputValue === undefined) return null;

            // Always expand all inputs one level for consistency
            return (
              <React.Fragment key={inputKey}>
                {/* Parent row for all inputs */}
                <Box
                  sx={{
                    display: 'grid',
                    gridTemplateColumns: `200px repeat(${evaluationIds.length}, 1fr)`,
                    bgcolor: '#f0f0f0',
                  }}>
                  <Box
                    sx={{
                      padding: '8px 16px',
                      fontWeight: 'bold',
                      borderRight: '1px solid #e0e0e0',
                      textAlign: 'left',
                    }}>
                    {inputKey}
                  </Box>
                  <Box
                    sx={{
                      gridColumn: `2 / span ${evaluationIds.length}`,
                      padding: '8px 16px',
                      fontStyle: 'italic',
                      color: '#666',
                    }}>
                    {typeof inputValue === 'object' && inputValue !== null
                      ? `${Object.keys(inputValue).length} properties`
                      : typeof inputValue === 'string'
                      ? inputValue.length > 50
                        ? `${inputValue.slice(0, 50)}...`
                        : inputValue
                      : String(inputValue)}
                  </Box>
                </Box>

                {/* Child rows for first level properties if object */}
                {typeof inputValue === 'object' && inputValue !== null ? (
                  Object.entries(inputValue).map(
                    ([subKey, subValue], subIndex) => (
                      <Box
                        key={`${inputKey}.${subKey}`}
                        sx={{
                          display: 'grid',
                          gridTemplateColumns: `200px repeat(${evaluationIds.length}, 1fr)`,
                          bgcolor: subIndex % 2 === 0 ? '#ffffff' : '#fafafa',
                          borderTop: '1px solid #f0f0f0',
                        }}>
                        <Box
                          sx={{
                            padding: '8px 16px 8px 32px', // Increased left padding to show hierarchy
                            fontWeight: 'normal',
                            borderRight: '1px solid #e0e0e0',
                            textAlign: 'left',
                          }}>
                          {subKey}
                        </Box>
                        <Box
                          sx={{
                            gridColumn: `2 / span ${evaluationIds.length}`,
                            padding: '8px 16px',
                            overflow: 'auto',
                            maxHeight: '100px',
                          }}>
                          {typeof subValue === 'object' && subValue !== null ? (
                            <pre
                              style={{
                                margin: 0,
                                fontSize: '0.9em',
                                whiteSpace: 'pre-wrap',
                                wordBreak: 'break-word',
                              }}>
                              {JSON.stringify(subValue, null, 2)}
                            </pre>
                          ) : Array.isArray(subValue) ? (
                            <pre
                              style={{
                                margin: 0,
                                fontSize: '0.9em',
                                whiteSpace: 'pre-wrap',
                                wordBreak: 'break-word',
                              }}>
                              {JSON.stringify(subValue, null, 2)}
                            </pre>
                          ) : (
                            String(subValue)
                          )}
                        </Box>
                      </Box>
                    )
                  )
                ) : (
                  // For primitive values, create a single child row showing the full value
                  <Box
                    sx={{
                      display: 'grid',
                      gridTemplateColumns: `200px repeat(${evaluationIds.length}, 1fr)`,
                      bgcolor: '#ffffff',
                      borderTop: '1px solid #f0f0f0',
                    }}>
                    <Box
                      sx={{
                        padding: '8px 16px 8px 32px',
                        fontWeight: 'normal',
                        fontStyle: 'italic',
                        borderRight: '1px solid #e0e0e0',
                        textAlign: 'left',
                        color: '#666',
                      }}>
                      value
                    </Box>
                    <Box
                      sx={{
                        gridColumn: `2 / span ${evaluationIds.length}`,
                        padding: '8px 16px',
                        overflow: 'auto',
                        maxHeight: '100px',
                      }}>
                      {typeof inputValue === 'object' ? (
                        <pre
                          style={{
                            margin: 0,
                            fontSize: '0.9em',
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word',
                          }}>
                          {JSON.stringify(inputValue, null, 2)}
                        </pre>
                      ) : (
                        String(inputValue)
                      )}
                    </Box>
                  </Box>
                )}
              </React.Fragment>
            );
          })}
        </Box>

        {/* Model Outputs section */}
        <Box sx={{marginTop: '8px'}}>
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: `200px repeat(${evaluationIds.length}, 1fr)`,
              bgcolor: '#f5f5f5',
              fontWeight: 'bold',
            }}>
            <Box
              sx={{
                padding: '8px 16px',
                borderRight: '1px solid #e0e0e0',
                borderBottom: '1px solid #e0e0e0',
              }}>
              Model Outputs
            </Box>
            {evaluationIds.map(evalId => (
              <Box
                key={evalId}
                sx={{
                  padding: '8px',
                  textAlign: 'center',
                  borderRight:
                    evalId !== evaluationIds[evaluationIds.length - 1]
                      ? '1px solid #e0e0e0'
                      : 'none',
                  borderBottom: '1px solid #e0e0e0',
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
                      bgcolor:
                        evalId === evaluationIds[0] ? '#f06292' : '#42a5f5',
                      marginRight: '8px',
                    }}
                  />
                  model{' '}
                  <Box component="span" sx={{fontSize: '0.9em', color: '#666'}}>
                    {evalId.slice(-4)}
                  </Box>
                </Box>
              </Box>
            ))}
          </Box>

          {/* Output row */}
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: `200px repeat(${evaluationIds.length}, 1fr)`,
              bgcolor: '#ffffff',
            }}>
            <Box
              sx={{
                padding: '8px 16px',
                fontWeight: 'bold',
                borderRight: '1px solid #e0e0e0',
              }}>
              output
            </Box>

            {evaluationIds.map((evalId, evalIndex) => {
              const evalCall = currentExample[1].find(
                c => c.evalId === evalId
              )?.call;
              const output = evalCall?.traceCall?.output;
              return (
                <Box
                  key={evalId}
                  sx={{
                    padding: '8px 16px',
                    borderRight:
                      evalId !== evaluationIds[evaluationIds.length - 1]
                        ? '1px solid #e0e0e0'
                        : 'none',
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
        </Box>

        {/* Add structured output comparison section */}
        {(() => {
          // Extract all possible numeric fields from all outputs
          const allNumericFields: Set<string> = new Set();
          const outputsByEvalId: Record<string, any> = {};

          evaluationIds.forEach(evalId => {
            const evalCall = currentExample[1].find(
              c => c.evalId === evalId
            )?.call;
            const output = evalCall?.traceCall?.output;

            // Store output for this evaluation
            outputsByEvalId[evalId] = output;

            // Extract model_output field if it exists
            const modelOutput = output?.model_output || output;

            if (typeof modelOutput === 'object' && modelOutput !== null) {
              // Recursively find all numeric fields in the object
              const findNumericFields = (obj: any, path: string = '') => {
                if (typeof obj !== 'object' || obj === null) return;

                Object.entries(obj).forEach(([key, value]) => {
                  const currentPath = path ? `${path}.${key}` : key;

                  if (typeof value === 'number') {
                    allNumericFields.add(currentPath);
                  } else if (
                    Array.isArray(value) &&
                    value.length > 0 &&
                    typeof value[0] === 'number'
                  ) {
                    // Handle arrays of numbers (like dominant_color)
                    allNumericFields.add(currentPath);
                  } else if (
                    typeof value === 'object' &&
                    value !== null &&
                    !Array.isArray(value)
                  ) {
                    findNumericFields(value, currentPath);
                  }
                });
              };

              findNumericFields(modelOutput);
            }
          });

          // If no numeric fields found, don't render this section
          if (allNumericFields.size === 0) return null;

          // Function to get value by path
          const getValueByPath = (
            obj: any,
            path: string
          ): number | number[] | undefined => {
            try {
              const pathSegments = path.split('.');
              let current = obj;

              for (const segment of pathSegments) {
                if (current?.[segment] === undefined) return undefined;
                current = current[segment];
              }

              // Return the value if it's a number or array of numbers
              if (typeof current === 'number') return current;
              if (
                Array.isArray(current) &&
                current.length > 0 &&
                current.every(item => typeof item === 'number')
              ) {
                return current;
              }

              return undefined;
            } catch (e) {
              return undefined;
            }
          };

          // Convert Set to sorted Array
          const numericFields = Array.from(allNumericFields).sort();

          // Get baseline eval ID for comparison
          const baselineEvalId = evaluationIds[0];

          return (
            <Box sx={{marginTop: '16px'}}>
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: `200px repeat(${evaluationIds.length}, 1fr)`,
                  bgcolor: '#f5f5f5',
                  fontWeight: 'bold',
                }}>
                <Box
                  sx={{
                    padding: '8px 16px',
                    borderRight: '1px solid #e0e0e0',
                    borderBottom: '1px solid #e0e0e0',
                  }}>
                  Output Metrics
                </Box>
                {evaluationIds.map(evalId => (
                  <Box
                    key={evalId}
                    sx={{
                      padding: '8px',
                      textAlign: 'center',
                      borderRight:
                        evalId !== evaluationIds[evaluationIds.length - 1]
                          ? '1px solid #e0e0e0'
                          : 'none',
                      borderBottom: '1px solid #e0e0e0',
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

              {/* Render rows for each numeric field */}
              {numericFields.map((fieldPath, index) => {
                // Get baseline value
                const baselineValue = getValueByPath(
                  outputsByEvalId[baselineEvalId]?.model_output ||
                    outputsByEvalId[baselineEvalId],
                  fieldPath
                );

                return (
                  <Box
                    key={fieldPath}
                    sx={{
                      display: 'grid',
                      gridTemplateColumns: `200px repeat(${evaluationIds.length}, 1fr)`,
                      bgcolor: index % 2 === 0 ? '#ffffff' : '#f9f9f9',
                    }}>
                    <Box
                      sx={{
                        padding: '8px 16px',
                        fontWeight: 'bold',
                        borderRight: '1px solid #e0e0e0',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}>
                      {fieldPath}
                    </Box>

                    {evaluationIds.map(evalId => {
                      const modelOutput =
                        outputsByEvalId[evalId]?.model_output ||
                        outputsByEvalId[evalId];
                      const value = getValueByPath(modelOutput, fieldPath);

                      return (
                        <Box
                          key={evalId}
                          sx={{
                            padding: '8px 16px',
                            borderRight:
                              evalId !== evaluationIds[evaluationIds.length - 1]
                                ? '1px solid #e0e0e0'
                                : 'none',
                            display: 'flex',
                            alignItems: 'center',
                          }}>
                          {value !== undefined ? (
                            <>
                              {Array.isArray(value)
                                ? value
                                    .map(v => (typeof v === 'number' ? v : ''))
                                    .join(', ')
                                : value.toFixed(6)}
                              {/* Only show comparison pills for non-baseline elements and non-arrays */}
                              {evalId !== baselineEvalId &&
                                baselineValue !== undefined &&
                                !Array.isArray(value) && (
                                  <TraceCallComparisonPill
                                    value={value}
                                    baseline={baselineValue as number}
                                    metricLowerIsBetter={false}
                                  />
                                )}
                            </>
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
          );
        })()}

        {/* Metrics Section */}
        <Box sx={{marginTop: '8px'}}>
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: `200px repeat(${evaluationIds.length}, 1fr)`,
              bgcolor: '#f5f5f5',
              fontWeight: 'bold',
            }}>
            <Box
              sx={{
                padding: '8px 16px',
                borderRight: '1px solid #e0e0e0',
                borderBottom: '1px solid #e0e0e0',
              }}>
              Metrics
            </Box>
            {evaluationIds.map(evalId => (
              <Box
                key={evalId}
                sx={{
                  padding: '8px 16px',
                  textAlign: 'center',
                  borderRight:
                    evalId !== evaluationIds[evaluationIds.length - 1]
                      ? '1px solid #e0e0e0'
                      : 'none',
                  borderBottom: '1px solid #e0e0e0',
                }}>
                Trials
              </Box>
            ))}
          </Box>

          {/* Metrics rows */}
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: `200px repeat(${evaluationIds.length}, 1fr)`,
              bgcolor: '#ffffff',
            }}>
            <Box
              sx={{
                padding: '8px 16px',
                fontWeight: 'bold',
                borderRight: '1px solid #e0e0e0',
              }}>
              Model Latency
            </Box>

            {evaluationIds.map((evalId, evalIndex) => {
              const evalCall = currentExample[1].find(
                c => c.evalId === evalId
              )?.call;
              const executionTime = evalCall?.traceCall?.execution_time;

              // Use the first evaluation as baseline for comparison
              const baselineEvalId = evaluationIds[0];
              const baselineCall = currentExample[1].find(
                c => c.evalId === baselineEvalId
              )?.call;
              const baselineTime = baselineCall?.traceCall?.execution_time;

              // Convert to ms for display
              const timeInMs =
                executionTime !== undefined ? executionTime * 1000 : undefined;
              const baselineTimeInMs =
                baselineTime !== undefined ? baselineTime * 1000 : undefined;

              return (
                <Box
                  key={evalId}
                  sx={{
                    padding: '8px 16px',
                    borderRight:
                      evalId !== evaluationIds[evaluationIds.length - 1]
                        ? '1px solid #e0e0e0'
                        : 'none',
                    display: 'flex',
                    alignItems: 'center',
                  }}>
                  {timeInMs !== undefined ? (
                    <>
                      {`${timeInMs.toFixed(3)}ms`}
                      {/* Only show comparison pills for non-baseline elements */}
                      {evalId !== baselineEvalId && (
                        <TraceCallComparisonPill
                          value={timeInMs}
                          baseline={baselineTimeInMs}
                          metricUnit="ms"
                          metricLowerIsBetter={true}
                        />
                      )}
                    </>
                  ) : (
                    '-'
                  )}
                </Box>
              );
            })}
          </Box>

          {/* Add additional metrics here, like Total Tokens */}
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: `200px repeat(${evaluationIds.length}, 1fr)`,
              bgcolor: '#f8f8f8',
            }}>
            <Box
              sx={{
                padding: '8px 16px',
                fontWeight: 'bold',
                borderRight: '1px solid #e0e0e0',
              }}>
              Total Tokens
            </Box>

            {evaluationIds.map((evalId, evalIndex) => {
              const evalCall = currentExample[1].find(
                c => c.evalId === evalId
              )?.call;
              // Extract tokens info from output if available
              const output = evalCall?.traceCall?.output;
              const tokens =
                typeof output === 'object' && output !== null
                  ? output.total_tokens || output.tokens || output.token_count
                  : undefined;

              // Use the first evaluation as baseline
              const baselineEvalId = evaluationIds[0];
              const baselineCall = currentExample[1].find(
                c => c.evalId === baselineEvalId
              )?.call;
              const baselineOutput = baselineCall?.traceCall?.output;
              const baselineTokens =
                typeof baselineOutput === 'object' && baselineOutput !== null
                  ? baselineOutput.total_tokens ||
                    baselineOutput.tokens ||
                    baselineOutput.token_count
                  : undefined;

              return (
                <Box
                  key={evalId}
                  sx={{
                    padding: '8px 16px',
                    borderRight:
                      evalId !== evaluationIds[evaluationIds.length - 1]
                        ? '1px solid #e0e0e0'
                        : 'none',
                    display: 'flex',
                    alignItems: 'center',
                  }}>
                  {tokens !== undefined ? (
                    <>
                      {tokens}
                      {/* Only show comparison pills for non-baseline elements */}
                      {evalId !== baselineEvalId &&
                        typeof tokens === 'number' &&
                        typeof baselineTokens === 'number' && (
                          <TraceCallComparisonPill
                            value={tokens}
                            baseline={baselineTokens}
                            metricLowerIsBetter={true}
                          />
                        )}
                    </>
                  ) : (
                    '-'
                  )}
                </Box>
              );
            })}
          </Box>
        </Box>
      </Box>
    </VerticalBox>
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
