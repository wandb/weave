import React, { useEffect, useState } from 'react';
import { EvaluationDefinition } from '../types';
import { fetchEvaluations } from '../api';
import { useEvalStudio } from '../context';

export const EvaluationsList: React.FC = () => {
  const [evaluations, setEvaluations] = useState<EvaluationDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const { 
    setSelectedEvaluation,
    setIsCreatingNewEval,
  } = useEvalStudio();

  useEffect(() => {
    const loadEvaluations = async () => {
      try {
        const data = await fetchEvaluations();
        setEvaluations(data);
      } catch (error) {
        console.error('Failed to fetch evaluations:', error);
      } finally {
        setLoading(false);
      }
    };

    loadEvaluations();
  }, []);

  if (loading) {
    return <div>Loading evaluations...</div>;
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h2>Evaluations</h2>
        <button onClick={() => setIsCreatingNewEval(true)}>
          Create New Evaluation
        </button>
      </div>
      
      {evaluations.length === 0 ? (
        <div>No evaluations found. Create your first one!</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {evaluations.map((evaluation) => (
            <div
              key={evaluation.id}
              style={{
                padding: '1rem',
                border: '1px solid #ccc',
                borderRadius: '4px',
                cursor: 'pointer',
              }}
              onClick={() => setSelectedEvaluation(evaluation)}
            >
              <h3>{evaluation.name}</h3>
              <div>Dataset: {evaluation.dataset.name}</div>
              <div>Scorers: {evaluation.scorers.map(s => s.name).join(', ')}</div>
              <div>Last Modified: {new Date(evaluation.lastModified).toLocaleDateString()}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}; 