import React from 'react';

import {StatusCodeType} from '../../wfReactInterface/tsDataModelHooks';
import {EvaluationResult} from '../types';

interface ModelReportProps {
  results: EvaluationResult[];
}

const getStatusStyle = (status: StatusCodeType) => {
  switch (status) {
    case 'SUCCESS':
      return {
        background: '#e6f4ea',
        color: '#137333',
      };
    case 'ERROR':
      return {
        background: '#fce8e6',
        color: '#c5221f',
      };
    default:
      return {
        background: '#f1f3f4',
        color: '#666',
      };
  }
};

export const ModelReport: React.FC<ModelReportProps> = ({results}) => {
  // Calculate summary statistics
  const summaryStats = results.reduce((acc, result) => {
    Object.entries(result.metrics).forEach(([key, value]) => {
      if (typeof value === 'number') {
        if (!acc[key]) {
          acc[key] = {
            min: value,
            max: value,
            sum: value,
            count: 1,
          };
        } else {
          acc[key].min = Math.min(acc[key].min, value);
          acc[key].max = Math.max(acc[key].max, value);
          acc[key].sum += value;
          acc[key].count += 1;
        }
      }
    });
    return acc;
  }, {} as Record<string, {min: number; max: number; sum: number; count: number}>);

  return (
    <div style={{padding: '1rem'}}>
      <h2>Model Performance Report</h2>

      {/* Summary Statistics */}
      <div style={{marginBottom: '2rem'}}>
        <h3>Summary Statistics</h3>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
            gap: '1rem',
            marginTop: '1rem',
          }}>
          {Object.entries(summaryStats).map(([metric, stats]) => (
            <div
              key={metric}
              style={{
                padding: '1rem',
                border: '1px solid #eee',
                borderRadius: '4px',
                background: 'white',
              }}>
              <div style={{fontWeight: 500, marginBottom: '0.5rem'}}>
                {metric.charAt(0).toUpperCase() + metric.slice(1)}
              </div>
              <div style={{fontSize: '0.9em', color: '#666'}}>
                <div>Average: {(stats.sum / stats.count).toFixed(3)}</div>
                <div>Min: {stats.min.toFixed(3)}</div>
                <div>Max: {stats.max.toFixed(3)}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Results Table */}
      <div>
        <h3>Detailed Results</h3>
        <div
          style={{
            marginTop: '1rem',
            border: '1px solid #eee',
            borderRadius: '4px',
            overflow: 'auto',
          }}>
          <table style={{width: '100%', borderCollapse: 'collapse'}}>
            <thead>
              <tr style={{background: '#f5f5f5'}}>
                <th
                  style={{
                    padding: '0.75rem',
                    textAlign: 'left',
                    borderBottom: '1px solid #eee',
                  }}>
                  Status
                </th>
                <th
                  style={{
                    padding: '0.75rem',
                    textAlign: 'left',
                    borderBottom: '1px solid #eee',
                  }}>
                  Created
                </th>
                {Object.keys(results[0]?.metrics || {}).map(metric => (
                  <th
                    key={metric}
                    style={{
                      padding: '0.75rem',
                      textAlign: 'left',
                      borderBottom: '1px solid #eee',
                    }}>
                    {metric.charAt(0).toUpperCase() + metric.slice(1)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {results.map(result => (
                <tr
                  key={result.callId}
                  style={{borderBottom: '1px solid #eee'}}>
                  <td style={{padding: '0.75rem'}}>
                    <span
                      style={{
                        display: 'inline-block',
                        padding: '0.25rem 0.5rem',
                        borderRadius: '4px',
                        fontSize: '0.9em',
                        ...getStatusStyle(result.status),
                      }}>
                      {result.status}
                    </span>
                  </td>
                  <td style={{padding: '0.75rem'}}>
                    {result.createdAt.toLocaleDateString()}
                  </td>
                  {Object.entries(result.metrics).map(([key, value]) => (
                    <td key={key} style={{padding: '0.75rem'}}>
                      {typeof value === 'number' ? value.toFixed(3) : value}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
