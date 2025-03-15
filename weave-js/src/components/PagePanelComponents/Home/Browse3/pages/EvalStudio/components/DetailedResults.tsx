import React, { useEffect, useState } from 'react';

import { fetchDetailedResults } from '../api';
import { useEvalStudio } from '../context';
import { DetailedEvaluationResult } from '../types';

export const DetailedResults: React.FC = () => {
  const [detailedResults, setDetailedResults] = useState<DetailedEvaluationResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const { selectedResult, selectedEvaluation, setSelectedResult } = useEvalStudio();

  useEffect(() => {
    const loadData = async () => {
      if (!selectedResult) return;
      
      setLoading(true);
      try {
        const data = await fetchDetailedResults(selectedResult.id);
        setDetailedResults(data);
      } catch (error) {
        console.error('Failed to fetch detailed results:', error);
        setError('Failed to load detailed results');
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [selectedResult]);

  if (!selectedResult || !selectedEvaluation) {
    return null;
  }

  if (loading) {
    return <div>Loading detailed results...</div>;
  }

  if (error) {
    return (
      <div>
        <div style={{ color: 'red', marginBottom: '1rem' }}>{error}</div>
        <button onClick={() => setSelectedResult(null)}>Back to Results</button>
      </div>
    );
  }

  if (!detailedResults) {
    return <div>No detailed results available</div>;
  }

  return (
    <div style={{ padding: '1rem' }}>
      <div style={{ marginBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>Detailed Results for {selectedResult.model.name}</h2>
        <button onClick={() => setSelectedResult(null)}>Back to Results</button>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={{ padding: '0.5rem', textAlign: 'left', borderBottom: '2px solid #ccc' }}>
                Input
              </th>
              <th style={{ padding: '0.5rem', textAlign: 'left', borderBottom: '2px solid #ccc' }}>
                Model Prediction
              </th>
              {selectedEvaluation.scorers.map(scorer => (
                <th
                  key={scorer.id}
                  style={{ padding: '0.5rem', textAlign: 'left', borderBottom: '2px solid #ccc' }}
                >
                  {scorer.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {detailedResults.predictions.map(prediction => {
              const sample = selectedEvaluation.dataset.samples.find(
                s => s.id === prediction.sampleId
              );
              
              return (
                <tr key={prediction.sampleId}>
                  <td style={{ padding: '0.5rem', borderBottom: '1px solid #eee' }}>
                    {sample?.input || 'Unknown input'}
                  </td>
                  <td style={{ padding: '0.5rem', borderBottom: '1px solid #eee' }}>
                    {prediction.modelPrediction}
                  </td>
                  {selectedEvaluation.scorers.map(scorer => (
                    <td
                      key={scorer.id}
                      style={{
                        padding: '0.5rem',
                        borderBottom: '1px solid #eee',
                        color: prediction.scores[scorer.id] >= 0.5 ? 'green' : 'red',
                      }}
                    >
                      {prediction.scores[scorer.id]?.toFixed(4) || 'N/A'}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}; 