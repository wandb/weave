import React, {useEffect, useState} from 'react';

import {fetchEvaluationResults, fetchModels, runEvaluation} from '../api';
import {useEvalStudio} from '../context';
import {EvaluationResult, Model} from '../types';
import {DetailedResults} from './DetailedResults';

export const EvaluationResults: React.FC = () => {
  const [results, setResults] = useState<EvaluationResult[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<Model | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  const {selectedEvaluation, selectedResult, setSelectedResult} =
    useEvalStudio();

  useEffect(() => {
    const loadData = async () => {
      if (!selectedEvaluation) {
        return;
      }

      setLoading(true);
      try {
        const [resultsData, modelsData] = await Promise.all([
          fetchEvaluationResults(selectedEvaluation.id),
          fetchModels(),
        ]);
        setResults(resultsData);
        setModels(modelsData);
      } catch (error) {
        console.error('Failed to fetch data:', error);
        setError('Failed to load evaluation results');
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [selectedEvaluation]);

  const handleRunEvaluation = async () => {
    if (!selectedEvaluation || !selectedModel) {
      setError('Please select a model to evaluate');
      return;
    }

    setIsRunning(true);
    setError(null);

    try {
      const result = await runEvaluation(
        selectedEvaluation.id,
        selectedModel.id
      );
      setResults(prev => [...prev, result]);
      setSelectedModel(null);
    } catch (error) {
      console.error('Failed to run evaluation:', error);
      setError('Failed to run evaluation');
    } finally {
      setIsRunning(false);
    }
  };

  if (!selectedEvaluation) {
    return <div>No evaluation selected</div>;
  }

  if (loading) {
    return <div>Loading results...</div>;
  }

  if (selectedResult) {
    return <DetailedResults />;
  }

  return (
    <div style={{padding: '1rem'}}>
      <h2>{selectedEvaluation.name} Results</h2>

      {error && <div style={{color: 'red', marginBottom: '1rem'}}>{error}</div>}

      <div style={{marginBottom: '2rem'}}>
        <h3>Run New Evaluation</h3>
        <div style={{display: 'flex', gap: '1rem', alignItems: 'center'}}>
          <select
            value={selectedModel?.id || ''}
            onChange={e => {
              const model = models.find(m => m.id === e.target.value);
              setSelectedModel(model || null);
            }}
            style={{padding: '0.5rem'}}>
            <option value="">Select a model...</option>
            {models.map(model => (
              <option key={model.id} value={model.id}>
                {model.name}
              </option>
            ))}
          </select>
          <button
            onClick={handleRunEvaluation}
            disabled={isRunning || !selectedModel}>
            {isRunning ? 'Running...' : 'Run Evaluation'}
          </button>
        </div>
      </div>

      <h3>Previous Results</h3>
      {results.length === 0 ? (
        <div>No results yet. Run your first evaluation!</div>
      ) : (
        <div style={{display: 'flex', flexDirection: 'column', gap: '1rem'}}>
          {results.map(result => (
            <div
              key={result.id}
              style={{
                padding: '1rem',
                border: '1px solid #ccc',
                borderRadius: '4px',
                cursor: result.status === 'completed' ? 'pointer' : 'default',
                backgroundColor: 'white',
                transition: 'background-color 0.2s',
              }}
              onMouseEnter={e => {
                if (result.status === 'completed') {
                  e.currentTarget.style.backgroundColor = '#f5f5f5';
                }
              }}
              onMouseLeave={e => {
                if (result.status === 'completed') {
                  e.currentTarget.style.backgroundColor = 'white';
                }
              }}
              onClick={() => {
                if (result.status === 'completed') {
                  setSelectedResult(result);
                }
              }}>
              <div style={{marginBottom: '0.5rem'}}>
                <strong>Model:</strong> {result.model.name}
              </div>
              <div style={{marginBottom: '0.5rem'}}>
                <strong>Status:</strong>{' '}
                <span
                  style={{
                    color:
                      result.status === 'completed'
                        ? 'green'
                        : result.status === 'failed'
                        ? 'red'
                        : 'orange',
                  }}>
                  {result.status}
                </span>
              </div>
              {result.status === 'completed' && (
                <>
                  <div>
                    <strong>Summary Metrics:</strong>
                    <div style={{marginLeft: '1rem'}}>
                      {Object.entries(result.metrics).map(([key, value]) => (
                        <div key={key}>
                          {key}: {value.toFixed(4)}
                        </div>
                      ))}
                    </div>
                  </div>
                  <div
                    style={{
                      marginTop: '0.5rem',
                      fontSize: '0.9em',
                      color: '#666',
                      fontStyle: 'italic',
                    }}>
                    Click to view detailed results
                  </div>
                </>
              )}
              <div
                style={{fontSize: '0.9em', color: '#666', marginTop: '0.5rem'}}>
                Run at: {new Date(result.createdAt).toLocaleString()}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
