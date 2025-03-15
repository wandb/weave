import React from 'react';

import { useEvalStudio } from '../context';

export const CreateScorer: React.FC = () => {
  const { setIsCreatingNewScorer } = useEvalStudio();

  return (
    <div style={{ padding: '1rem' }}>
      <h2>Create New Scorer</h2>
      <p>Scorer creation UI will be implemented here.</p>
      <button onClick={() => setIsCreatingNewScorer(false)}>Close</button>
    </div>
  );
}; 