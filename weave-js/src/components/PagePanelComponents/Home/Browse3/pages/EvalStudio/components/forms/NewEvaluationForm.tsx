import React, {useState} from 'react';

import {EvaluationDefinition as Evaluation, Scorer} from '../../types';

interface NewEvaluationFormProps {
  onSubmit: (evaluation: Evaluation) => void;
}

export const NewEvaluationForm: React.FC<NewEvaluationFormProps> = ({
  onSubmit,
}) => {
  const [name, setName] = useState('');
  const [selectedScorers, setSelectedScorers] = useState<string[]>([]);

  // Mock scorers for now - would come from API
  const availableScorers: Scorer[] = [
    {id: 'scorer1', name: 'Accuracy', description: 'Basic accuracy scorer'},
    {
      id: 'scorer2',
      name: 'F1 Score',
      description: 'F1 score for balanced evaluation',
    },
    {
      id: 'scorer3',
      name: 'BLEU',
      description: 'BLEU score for text generation',
    },
    {
      id: 'scorer4',
      name: 'ROUGE',
      description: 'ROUGE score for summarization',
    },
  ];

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // TODO: Implement actual evaluation creation
    const newEvaluation: Evaluation = {
      entity: 'wandb',
      project: 'eval-studio',
      objectId: Math.random().toString(36).substr(2, 9),
      objectDigest: Math.random().toString(36).substr(2, 9),
      evaluationRef: Math.random().toString(36).substr(2, 9),
      displayName: name,
      createdAt: new Date(),
      datasetRef: 'dataset1', // Would come from context
      scorerRefs: selectedScorers,
    };
    onSubmit(newEvaluation);
  };

  return (
    <div style={{padding: '1rem'}}>
      <h2>Create New Evaluation</h2>
      <form onSubmit={handleSubmit}>
        <div style={{marginBottom: '1rem'}}>
          <label style={{display: 'block', marginBottom: '0.5rem'}}>
            Evaluation Name
          </label>
          <input
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            style={{
              width: '100%',
              padding: '0.5rem',
              border: '1px solid #ddd',
              borderRadius: '4px',
            }}
            placeholder="Enter evaluation name"
            required
          />
        </div>
        <div style={{marginBottom: '1rem'}}>
          <label style={{display: 'block', marginBottom: '0.5rem'}}>
            Select Scorers
          </label>
          <div
            style={{
              border: '1px solid #ddd',
              borderRadius: '4px',
              maxHeight: '200px',
              overflowY: 'auto',
            }}>
            {availableScorers.map(scorer => (
              <div
                key={scorer.id}
                style={{
                  padding: '0.5rem',
                  borderBottom: '1px solid #eee',
                  display: 'flex',
                  alignItems: 'center',
                }}>
                <input
                  type="checkbox"
                  id={scorer.id}
                  checked={selectedScorers.includes(scorer.id)}
                  onChange={e => {
                    if (e.target.checked) {
                      setSelectedScorers([...selectedScorers, scorer.id]);
                    } else {
                      setSelectedScorers(
                        selectedScorers.filter(id => id !== scorer.id)
                      );
                    }
                  }}
                  style={{marginRight: '0.5rem'}}
                />
                <label htmlFor={scorer.id} style={{flex: 1}}>
                  <div>{scorer.name}</div>
                  {scorer.description && (
                    <div style={{fontSize: '0.9em', color: '#666'}}>
                      {scorer.description}
                    </div>
                  )}
                </label>
              </div>
            ))}
          </div>
        </div>
        <div style={{display: 'flex', gap: '1rem', marginTop: '2rem'}}>
          <button
            type="submit"
            disabled={selectedScorers.length === 0}
            style={{
              padding: '0.5rem 1rem',
              border: '1px solid #00A4EF',
              borderRadius: '4px',
              background: selectedScorers.length === 0 ? '#eee' : '#00A4EF',
              color: selectedScorers.length === 0 ? '#666' : 'white',
              cursor: selectedScorers.length === 0 ? 'not-allowed' : 'pointer',
            }}>
            Create Evaluation
          </button>
        </div>
      </form>
    </div>
  );
};
