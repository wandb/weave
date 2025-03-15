import React from 'react';
import { useEvalStudio } from '../context';

export const CreateDataset: React.FC = () => {
  const { setIsCreatingNewDataset } = useEvalStudio();

  return (
    <div style={{ padding: '1rem' }}>
      <h2>Create New Dataset</h2>
      <p>Dataset creation UI will be implemented here.</p>
      <button onClick={() => setIsCreatingNewDataset(false)}>Close</button>
    </div>
  );
}; 