import {Box} from '@material-ui/core';
import {Alert} from '@mui/material';
import React, {useMemo, useState} from 'react';

import {Button} from '../../../../../Button';
import {
  CustomWeaveTypeDispatcher,
  CustomWeaveTypePayload,
  CustomWeaveTypeProjectContext,
  isCustomWeaveType,
} from '../../typeViews/CustomWeaveTypeDispatcher';
import {EvaluationComparisonState} from './ecpState';
import {HorizontalBox, VerticalBox} from './Layout';

// Add a new component for displaying trace calls
export const TraceCallsSection: React.FC<{
  traceCalls: Array<{callId: string; traceCall: any}>;
  entity?: string;
  project?: string;
  state: EvaluationComparisonState;
}> = ({traceCalls, entity, project, state}) => {
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
  const evaluationIds = useMemo(() => {
    // Get evaluation IDs in the same order as they appear in the state
    // Reverse the array to match the order in the rest of the UI
    return Object.keys(state.summary.evaluationCalls).reverse();
  }, [state.summary.evaluationCalls]);

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
    evalId: string;
    baselineEvalId: string;
    metricUnit?: string;
    metricLowerIsBetter?: boolean;
  }> = ({
    value,
    baseline,
    evalId,
    baselineEvalId,
    metricUnit = '',
    metricLowerIsBetter = false,
  }) => {
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

    // Determine if the difference is positive or negative for color selection
    // If metricLowerIsBetter is true, then negative diffs are good (green)
    // If metricLowerIsBetter is false, then positive diffs are good (green)
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
                            // Check if this is a type that we should render using the CustomWeaveTypeDispatcher
                            isCustomWeaveType(subValue) ? (
                              <CustomWeaveTypeProjectContext.Provider
                                value={{
                                  entity: entity || '',
                                  project: project || '',
                                }}>
                                <CustomWeaveTypeDispatcher
                                  data={subValue as CustomWeaveTypePayload}
                                />
                              </CustomWeaveTypeProjectContext.Provider>
                            ) : (
                              <pre
                                style={{
                                  margin: 0,
                                  fontSize: '0.9em',
                                  whiteSpace: 'pre-wrap',
                                  wordBreak: 'break-word',
                                }}>
                                {JSON.stringify(subValue, null, 2)}
                              </pre>
                            )
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

        {/* Output Metrics section */}
        {(() => {
          // Extract all possible numeric fields from all outputs
          const allNumericFields: Set<string> = new Set();
          const outputsByEvalId: Record<string, any> = {};
          let hasPrimitiveOutput = false;

          evaluationIds.forEach(evalId => {
            const evalCall = currentExample[1].find(
              c => c.evalId === evalId
            )?.call;
            const output = evalCall?.traceCall?.output;

            // Store output for this evaluation
            outputsByEvalId[evalId] = output;

            // Extract model_output field if it exists
            const modelOutput = output?.model_output || output;

            // Handle primitive outputs (anything that's not an object or is null)
            if (typeof modelOutput !== 'object' || modelOutput === null) {
              hasPrimitiveOutput = true;
              allNumericFields.add('value');
            } else if (
              typeof modelOutput === 'object' &&
              modelOutput !== null
            ) {
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
            // Special case for primitive outputs when path is 'value'
            if (path === 'value' && (typeof obj !== 'object' || obj === null)) {
              // For non-numeric primitives, we can't show comparison pills,
              // so convert to numbers where it makes sense
              if (typeof obj === 'number') return obj;
              if (typeof obj === 'boolean') return obj ? 1 : 0;
              // For strings and other types, just return undefined
              // so we don't show comparison pills
              return undefined;
            }

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
                  {hasPrimitiveOutput
                    ? 'Model Output Value'
                    : 'Model Output Metrics'}
                </Box>
                {evaluationIds.map(evalId => {
                  return (
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
                              state.summary.evaluationCalls[evalId].color,
                            marginRight: '8px',
                          }}
                        />
                        {state.summary.evaluationCalls[evalId].name || 'model'}{' '}
                        <Box
                          component="span"
                          sx={{fontSize: '0.9em', color: '#666'}}>
                          {evalId.slice(-4)}
                        </Box>
                      </Box>
                    </Box>
                  );
                })}
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
                      const isPrimitive =
                        fieldPath === 'value' &&
                        (typeof modelOutput !== 'object' ||
                          modelOutput === null);

                      // Determine what to display based on the value type
                      let displayValue = '-';

                      if (value !== undefined) {
                        if (Array.isArray(value)) {
                          displayValue = value
                            .map(v => (typeof v === 'number' ? v : ''))
                            .join(', ');
                        } else if (isPrimitive) {
                          displayValue = String(modelOutput);
                        } else if (typeof value === 'number') {
                          displayValue = value.toFixed(6);
                        } else {
                          displayValue = String(value);
                        }
                      } else if (isPrimitive) {
                        displayValue = String(modelOutput);
                      }

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
                          {displayValue}

                          {value !== undefined &&
                            evalId !== baselineEvalId &&
                            baselineValue !== undefined &&
                            !Array.isArray(value) && (
                              <TraceCallComparisonPill
                                value={value}
                                baseline={baselineValue as number}
                                evalId={evalId}
                                baselineEvalId={baselineEvalId}
                                metricLowerIsBetter={false}
                              />
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
      </Box>
    </VerticalBox>
  );
};
