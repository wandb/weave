import {ObjectRef, parseRef} from '@wandb/weave/react';
import React, {useEffect, useState} from 'react';

import {SmallRef} from '../../../smallRef/SmallRef';
import {useGetTraceServerClientContext} from '../../wfReactInterface/traceServerClientContext';
import {fetchEvaluationResults} from '../api';
import {useEvalStudio} from '../context';
import {EvaluationResult} from '../types';

type ResultRow = {
  id: string;
  status: 'running' | 'completed' | 'failed';
  metrics: Record<string, number>;
  createdAt: string;
};

export const EvaluationResults: React.FC = () => {
  const [results, setResults] = useState<ResultRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedRow, setSelectedRow] = useState<number | null>(null);
  const [hoveredRow, setHoveredRow] = useState<number | null>(null);

  const {selectedEvaluation} = useEvalStudio();
  const getTraceServerClient = useGetTraceServerClientContext();

  useEffect(() => {
    const loadResults = async () => {
      if (!selectedEvaluation) {
        return;
      }

      try {
        const data = await fetchEvaluationResults(selectedEvaluation.objectId);

        // Transform the data into the format we need
        const transformedData: ResultRow[] = data.map(result => ({
          id: result.id,
          status: result.status,
          metrics: result.metrics,
          createdAt: result.createdAt,
        }));

        setResults(transformedData);
      } catch (error) {
        console.error('Failed to fetch results:', error);
        setError('Failed to load evaluation results');
      } finally {
        setLoading(false);
      }
    };

    loadResults();
  }, [selectedEvaluation]);

  if (!selectedEvaluation) {
    return null;
  }

  if (loading) {
    return <div style={{padding: '1rem'}}>Loading results...</div>;
  }

  if (error) {
    return <div style={{padding: '1rem', color: 'red'}}>{error}</div>;
  }

  const columnStyles = {
    header: {
      padding: '0.75rem 1rem',
      textAlign: 'left' as const,
      fontWeight: 500,
      color: '#666',
      borderBottom: '2px solid #eee',
      backgroundColor: '#f8f8f8',
    },
    cell: {
      padding: '0.75rem 1rem',
      borderBottom: '1px solid #eee',
    },
  };

  return (
    <div style={{height: '100%', display: 'flex', flexDirection: 'column'}}>
      <div
        style={{
          padding: '1.5rem',
          borderBottom: '1px solid #eee',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
        }}>
        <div>
          <h2
            style={{
              margin: 0,
              fontSize: '1.4rem',
              fontWeight: 500,
              color: '#111',
              marginBottom: '1rem',
            }}>
            {selectedEvaluation.displayName}
          </h2>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'auto 1fr',
              gap: '0.5rem 1rem',
              color: '#666',
              fontSize: '0.9rem',
            }}>
            <div style={{fontWeight: 500}}>Dataset:</div>
            <div>
              <SmallRef
                objRef={parseRef(selectedEvaluation.datasetRef) as ObjectRef}
              />
            </div>
            <div style={{fontWeight: 500}}>Scorers:</div>
            <div style={{display: 'flex', gap: '0.5rem', flexWrap: 'wrap'}}>
              {selectedEvaluation.scorerRefs.map((scorerRef, index) => (
                <React.Fragment key={scorerRef}>
                  <SmallRef objRef={parseRef(scorerRef) as ObjectRef} />
                  {index < selectedEvaluation.scorerRefs.length - 1 && (
                    <span style={{color: '#999'}}>•</span>
                  )}
                </React.Fragment>
              ))}
            </div>
          </div>
        </div>
        <button
          style={{
            padding: '0.75rem 1.25rem',
            backgroundColor: '#00A4EF',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '0.9rem',
            fontWeight: 500,
            boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
          }}
          onClick={() => {
            /* TODO: Implement run action */
          }}>
          Run Evaluation
        </button>
      </div>

      <div style={{flex: 1, overflowY: 'auto'}}>
        <table style={{width: '100%', borderCollapse: 'collapse'}}>
          <thead>
            <tr>
              <th style={columnStyles.header}>Status</th>
              <th style={columnStyles.header}>Created At</th>
              <th style={columnStyles.header}>Metrics</th>
            </tr>
          </thead>
          <tbody>
            {results.map((row, index) => (
              <tr
                key={row.id}
                style={{
                  backgroundColor:
                    selectedRow === index
                      ? '#f5f5f5'
                      : hoveredRow === index
                      ? '#f8f8f8'
                      : 'white',
                  cursor: 'pointer',
                }}
                onClick={() => setSelectedRow(index)}
                onMouseEnter={() => setHoveredRow(index)}
                onMouseLeave={() => setHoveredRow(null)}>
                <td style={columnStyles.cell}>
                  <div
                    style={{
                      width: '8px',
                      height: '8px',
                      borderRadius: '50%',
                      backgroundColor:
                        row.status === 'completed'
                          ? '#4CAF50'
                          : row.status === 'failed'
                          ? '#f44336'
                          : '#FFC107',
                      display: 'inline-block',
                      marginRight: '0.5rem',
                    }}
                  />
                  {row.status}
                </td>
                <td style={columnStyles.cell}>
                  {new Date(row.createdAt).toLocaleString()}
                </td>
                <td style={columnStyles.cell}>
                  {Object.entries(row.metrics).map(([key, value]) => (
                    <div
                      key={key}
                      style={{display: 'inline-block', marginRight: '1rem'}}>
                      <span style={{color: '#666'}}>{key}:</span>{' '}
                      <span>{value.toFixed(3)}</span>
                    </div>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
