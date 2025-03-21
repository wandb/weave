import React, {useEffect, useState} from 'react';

import {createEvaluation, fetchDatasets, fetchScorers} from '../api';
import {useEvalStudio} from '../context';
import {Dataset, Scorer} from '../types';

export const CreateEvaluation: React.FC = () => {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [scorers, setScorers] = useState<Scorer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const {
    selectedDataset,
    selectedScorers,
    evaluationName,
    setSelectedDataset,
    setSelectedScorers,
    setEvaluationName,
    setIsCreatingNewEval,
    setIsCreatingNewDataset,
    setIsCreatingNewScorer,
  } = useEvalStudio();

  useEffect(() => {
    const loadData = async () => {
      try {
        const [datasetsData, scorersData] = await Promise.all([
          fetchDatasets(),
          fetchScorers(),
        ]);
        setDatasets(datasetsData);
        setScorers(scorersData);
      } catch (error) {
        console.error('Failed to fetch data:', error);
        setError('Failed to load required data');
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (
      !selectedDataset ||
      selectedScorers.length === 0 ||
      !evaluationName.trim()
    ) {
      setError('Please fill in all required fields');
      return;
    }

    try {
      await createEvaluation(
        evaluationName,
        selectedDataset.id,
        selectedScorers.map(s => s.id)
      );
      setIsCreatingNewEval(false);
    } catch (error) {
      console.error('Failed to create evaluation:', error);
      setError('Failed to create evaluation');
    }
  };

  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    <div style={{padding: '1rem'}}>
      <h2>Create New Evaluation</h2>

      {error && <div style={{color: 'red', marginBottom: '1rem'}}>{error}</div>}

      <form onSubmit={handleSubmit}>
        <div style={{marginBottom: '1rem'}}>
          <label>
            Name:
            <input
              type="text"
              value={evaluationName}
              onChange={e => setEvaluationName(e.target.value)}
              style={{marginLeft: '0.5rem'}}
            />
          </label>
        </div>

        <div style={{marginBottom: '1rem'}}>
          <h3>Dataset</h3>
          <div style={{display: 'flex', gap: '0.5rem', marginBottom: '0.5rem'}}>
            <button type="button" onClick={() => setIsCreatingNewDataset(true)}>
              Create New Dataset
            </button>
          </div>
          <div
            style={{display: 'flex', flexDirection: 'column', gap: '0.5rem'}}>
            {datasets.map(dataset => (
              <div
                key={dataset.id}
                style={{
                  padding: '0.5rem',
                  border: '1px solid #ccc',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  background:
                    selectedDataset?.id === dataset.id
                      ? '#e0e0e0'
                      : 'transparent',
                }}
                onClick={() => setSelectedDataset(dataset)}>
                {dataset.name}
              </div>
            ))}
          </div>
        </div>

        <div style={{marginBottom: '1rem'}}>
          <h3>Scorers</h3>
          <div style={{display: 'flex', gap: '0.5rem', marginBottom: '0.5rem'}}>
            <button type="button" onClick={() => setIsCreatingNewScorer(true)}>
              Create New Scorer
            </button>
          </div>
          <div
            style={{display: 'flex', flexDirection: 'column', gap: '0.5rem'}}>
            {scorers.map(scorer => (
              <div
                key={scorer.id}
                style={{
                  padding: '0.5rem',
                  border: '1px solid #ccc',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  background: selectedScorers.some(s => s.id === scorer.id)
                    ? '#e0e0e0'
                    : 'transparent',
                }}
                onClick={() => {
                  if (selectedScorers.some(s => s.id === scorer.id)) {
                    setSelectedScorers(
                      selectedScorers.filter(s => s.id !== scorer.id)
                    );
                  } else {
                    setSelectedScorers([...selectedScorers, scorer]);
                  }
                }}>
                {scorer.name}
                {scorer.description && (
                  <div style={{fontSize: '0.9em', color: '#666'}}>
                    {scorer.description}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        <div style={{display: 'flex', gap: '1rem'}}>
          <button type="submit">Create Evaluation</button>
          <button type="button" onClick={() => setIsCreatingNewEval(false)}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
};
