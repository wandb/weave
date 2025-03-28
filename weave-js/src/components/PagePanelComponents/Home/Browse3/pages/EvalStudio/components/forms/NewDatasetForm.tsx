import React, {useState} from 'react';

import {Dataset} from '../../types';

interface NewDatasetFormProps {
  onSubmit: (dataset: Dataset) => void;
}

export const NewDatasetForm: React.FC<NewDatasetFormProps> = ({onSubmit}) => {
  const [name, setName] = useState('');
  const [file, setFile] = useState<File | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // TODO: Implement actual dataset creation with file upload
    const newDataset: Dataset = {
      id: Math.random().toString(36).substr(2, 9),
      name,
      createdAt: new Date().toISOString(),
      samples: [], // Would be populated from file
    };
    onSubmit(newDataset);
  };

  return (
    <div style={{padding: '1rem'}}>
      <h2>Create New Dataset</h2>
      <form onSubmit={handleSubmit}>
        <div style={{marginBottom: '1rem'}}>
          <label style={{display: 'block', marginBottom: '0.5rem'}}>
            Dataset Name
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
            placeholder="Enter dataset name"
            required
          />
        </div>
        <div style={{marginBottom: '1rem'}}>
          <label style={{display: 'block', marginBottom: '0.5rem'}}>
            Upload Data File
          </label>
          <input
            type="file"
            onChange={e => setFile(e.target.files?.[0] || null)}
            accept=".csv,.json,.jsonl"
            style={{
              width: '100%',
              padding: '0.5rem',
              border: '1px solid #ddd',
              borderRadius: '4px',
            }}
            required
          />
          <small
            style={{color: '#666', display: 'block', marginTop: '0.25rem'}}>
            Supported formats: CSV, JSON, JSONL
          </small>
        </div>
        <div style={{display: 'flex', gap: '1rem', marginTop: '2rem'}}>
          <button
            type="submit"
            style={{
              padding: '0.5rem 1rem',
              border: '1px solid #00A4EF',
              borderRadius: '4px',
              background: '#00A4EF',
              color: 'white',
              cursor: 'pointer',
            }}>
            Create Dataset
          </button>
        </div>
      </form>
    </div>
  );
};
