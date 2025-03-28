import React, {useMemo} from 'react';
import {styled} from '@mui/material/styles';
import {Box, Paper, Typography, Tooltip} from '@mui/material';
import {StyledDataGrid} from '../../../StyledDataGrid';
import {useEvaluationComparisonState} from '../../CompareEvaluationsPage/ecpState';
import {buildCompositeMetricsMap} from '../../CompareEvaluationsPage/compositeMetricsUtil';
import {ValueViewNumber} from '../../CallPage/ValueViewNumber';
import {SIGNIFICANT_DIGITS} from '../../CompareEvaluationsPage/ecpConstants';
import {MetricValueType} from '../../CompareEvaluationsPage/ecpTypes';
import {isWeaveRef} from '../../../filters/common';
import {parseRef} from '../../../../../../../react';
import {SmallRef} from '../../../smallRef/SmallRef';
import {isCustomWeaveTypePayload} from '../../../typeViews/customWeaveType.types';
import {CustomWeaveTypeDispatcher} from '../../../typeViews/CustomWeaveTypeDispatcher';

// Types
interface RunReportProps {
  entity: string;
  project: string;
  runId: string;
}

const ReportContainer = styled('div')({
  display: 'flex',
  flexDirection: 'column',
  gap: '16px',
  padding: '16px',
  height: '100%',
});

const HeaderCard = styled(Paper)({
  padding: '16px',
  borderRadius: '8px',
  backgroundColor: '#f8f9fa',
});

const MetricChip = styled('div')({
  display: 'inline-flex',
  alignItems: 'center',
  padding: '4px 8px',
  borderRadius: '4px',
  backgroundColor: '#e3f2fd',
  color: '#1976d2',
  fontSize: '0.875rem',
  fontWeight: 500,
  marginRight: '8px',
});

// Helper function to format metric name
const formatMetricName = (metricSubPath: string[]) => {
  return metricSubPath.map(p => p.replace(/_/g, ' ')).join(' > ');
};

// Helper function to format metric value
const formatMetricValue = (value: MetricValueType, scoreType: 'binary' | 'continuous') => {
  if (scoreType === 'binary') {
    return typeof value === 'boolean' ? value.toString() : value;
  }
  return typeof value === 'number' ? value.toFixed(SIGNIFICANT_DIGITS) : value;
};

// Component to handle nested data display
const NestedValueView: React.FC<{value: any}> = ({value}) => {
  if (value == null) {
    return <span>-</span>;
  }
  
  if (typeof value === 'object') {
    if (isCustomWeaveTypePayload(value)) {
      return (
        <Box sx={{width: '100%', maxHeight: '300px', overflow: 'auto'}}>
          <CustomWeaveTypeDispatcher data={value} />
        </Box>
      );
    }
    if (isWeaveRef(value)) {
      return <SmallRef objRef={parseRef(value)} />;
    }
    return (
      <pre style={{
        whiteSpace: 'pre-wrap',
        textAlign: 'left',
        wordBreak: 'break-all',
        padding: 0,
        margin: 0,
        fontFamily: 'monospace',
        fontSize: '0.875rem',
        maxHeight: '200px',
        overflow: 'auto'
      }}>
        {JSON.stringify(value, null, 2)}
      </pre>
    );
  }

  if (typeof value === 'string' && isWeaveRef(value)) {
    return <SmallRef objRef={parseRef(value)} />;
  }

  return <span>{String(value)}</span>;
};

// Helper function to flatten nested objects
const flattenObject = (obj: any, prefix = ''): Record<string, any> => {
  if (obj == null) return {};
  
  // If it's not an object or is an array, return as is
  if (typeof obj !== 'object' || Array.isArray(obj) || obj instanceof Date) {
    return prefix ? {[prefix]: obj} : obj;
  }
  
  // Handle custom types and refs without flattening
  if (isCustomWeaveTypePayload(obj) || isWeaveRef(obj)) {
    return prefix ? {[prefix]: obj} : obj;
  }
  
  return Object.keys(obj).reduce((acc: Record<string, any>, key: string) => {
    const value = obj[key];
    const newKey = prefix ? `${prefix}.${key}` : key;
    
    // If value is null/undefined, add it with the current prefix
    if (value == null) {
      acc[newKey] = value;
      return acc;
    }
    
    // If value is not an object or is a special type, add it as is
    if (typeof value !== 'object' || Array.isArray(value) || value instanceof Date || 
        isCustomWeaveTypePayload(value) || isWeaveRef(value)) {
      acc[newKey] = value;
      return acc;
    }
    
    // Otherwise, flatten recursively
    Object.assign(acc, flattenObject(value, newKey));
    return acc;
  }, {});
};

// Helper function to get unique flattened keys from an array of objects
const getUniqueKeys = (objects: any[]): string[] => {
  const keySets = objects.map(obj => Object.keys(flattenObject(obj)));
  return Array.from(new Set(keySets.flat()));
};

export const RunReport: React.FC<RunReportProps> = ({entity, project, runId}) => {
  const state = useEvaluationComparisonState(entity, project, [runId]);

  const compositeScoreMetrics = useMemo(
    () => state.result ? buildCompositeMetricsMap(state.result.summary, 'score') : null,
    [state.result]
  );

  if (state.loading || !state.result) {
    return (
      <ReportContainer>
        <Typography>Loading...</Typography>
      </ReportContainer>
    );
  }

  const {summary, loadableComparisonResults} = state.result;
  
  if (loadableComparisonResults.loading || !loadableComparisonResults.result || !compositeScoreMetrics) {
    return (
      <ReportContainer>
        <Typography>Loading results...</Typography>
      </ReportContainer>
    );
  }

  const results = loadableComparisonResults.result;
  const evaluationCall = summary.evaluationCalls[runId];

  // Get all inputs and outputs to analyze their structure
  const allInputs = Object.values(results.inputs).map(input => input.val);
  const allOutputs = Object.values(results.resultRows)
    .map(row => {
      const predictAndScore = Object.values(row.evaluations[runId].predictAndScores)[0];
      return predictAndScore._rawPredictTraceData?.output;
    })
    .filter(Boolean);

  // Get unique keys for inputs and outputs
  const inputKeys = getUniqueKeys(allInputs);
  const outputKeys = getUniqueKeys(allOutputs);

  // Transform the results into rows for the grid
  const rows = Object.entries(results.resultRows).map(([rowDigest, rowData]) => {
    const input = results.inputs[rowDigest];
    const evalData = rowData.evaluations[runId];
    const predictAndScore = Object.values(evalData.predictAndScores)[0];
    
    // Extract model output and metrics from trace data
    const predictOutput = predictAndScore._rawPredictTraceData?.output;
    const summary = predictAndScore._rawPredictAndScoreTraceData?.summary?.weave;
    
    // Flatten input and output
    const flattenedInput = flattenObject(input.val);
    const flattenedOutput = flattenObject(predictOutput);
    
    return {
      id: rowDigest,
      ...flattenedInput,
      output: predictOutput, // Keep the full output as a single field
      modelLatency: summary?.latency_ms,
      totalTokens: summary?.usage?.total_tokens,
      ...Object.entries(predictAndScore.scoreMetrics).reduce((acc, [metricId, result]) => {
        acc[metricId] = result.value;
        return acc;
      }, {} as Record<string, any>)
    };
  });

  // Create columns based on available metrics, grouped by scorer
  const columns = [
    {
      field: 'id',
      headerName: 'ID',
      width: 100,
      renderCell: (params: any) => (
        <Tooltip title={params.value}>
          <span>{params.value.slice(0, 8)}...</span>
        </Tooltip>
      ),
    },
    // Input columns
    ...inputKeys.map(key => ({
      field: key,
      headerName: `Input: ${key}`,
      flex: 1,
      minWidth: 150,
      renderCell: (params: any) => <NestedValueView value={params.value} />,
    })),
    // Output column
    {
      field: 'output',
      headerName: 'Output',
      flex: 1,
      minWidth: 200,
      renderCell: (params: any) => <NestedValueView value={params.value} />,
    },
    {
      field: 'modelLatency',
      headerName: 'Model Latency (ms)',
      width: 150,
      renderCell: (params: any) => {
        const value = params.value;
        return value != null ? <ValueViewNumber value={value} /> : null;
      },
    },
    {
      field: 'totalTokens',
      headerName: 'Total Tokens',
      width: 120,
      renderCell: (params: any) => {
        const value = params.value;
        return value != null ? <ValueViewNumber value={value} /> : null;
      },
    },
    ...Object.entries(compositeScoreMetrics).flatMap(([groupName, group]) => 
      Object.entries(group.metrics).map(([keyPath, metricGroup]) => {
        const metric = Object.values(metricGroup.scorerRefs)[0].metric;
        return {
          field: keyPath,
          headerName: formatMetricName(metric.metricSubPath),
          description: `${groupName} - ${formatMetricName(metric.metricSubPath)}${metric.unit ? ` (${metric.unit})` : ''}`,
          width: 130,
          renderCell: (params: any) => {
            const value = params.value;
            if (value == null) return null;
            if (metric.scoreType === 'binary') {
              return (
                <Box sx={{color: value ? 'success.main' : 'error.main'}}>
                  {value ? '✓' : '✗'}
                </Box>
              );
            }
            return <ValueViewNumber value={value} />;
          }
        };
      })
    )
  ];

  return (
    <ReportContainer>
      <HeaderCard>
        <Typography variant="h6" gutterBottom>
          {evaluationCall.name}
        </Typography>
        <Box sx={{display: 'flex', gap: 1, flexWrap: 'wrap'}}>
          {Object.entries(evaluationCall.summaryMetrics).map(([metricId, result]) => {
            const metric = summary.summaryMetrics[metricId];
            if (!metric) return null;
            return (
              <Tooltip 
                key={metricId} 
                title={`${formatMetricName(metric.metricSubPath)}${metric.unit ? ` (${metric.unit})` : ''}`}
              >
                <MetricChip>
                  {formatMetricName(metric.metricSubPath)}: {formatMetricValue(result.value, metric.scoreType)}
                </MetricChip>
              </Tooltip>
            );
          })}
        </Box>
      </HeaderCard>

      <Box sx={{flex: 1, minHeight: 0}}>
        <StyledDataGrid
          rows={rows}
          columns={columns}
          disableRowSelectionOnClick
          density="compact"
          sx={{
            '& .MuiDataGrid-cell': {
              fontSize: '0.875rem',
            },
          }}
        />
      </Box>
    </ReportContainer>
  );
}; 