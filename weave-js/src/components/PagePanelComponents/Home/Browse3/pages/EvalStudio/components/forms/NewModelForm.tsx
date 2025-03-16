import React, {useState} from 'react';

import {Model} from '../../types';

interface NewModelFormProps {
  onSubmit: (model: Model) => void;
}

export const NewModelForm: React.FC<NewModelFormProps> = ({onSubmit}) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [modelType, setModelType] = useState('llm');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // TODO: Implement actual model creation
    const newModel: Model = {
      id: Math.random().toString(36).substr(2, 9),
      name,
      description,
    };
    onSubmit(newModel);
  };

  return (
    <div style={{padding: '1rem'}}>
      <h2>Add New Model</h2>
      <form onSubmit={handleSubmit}>
        <div style={{marginBottom: '1rem'}}>
          <label style={{display: 'block', marginBottom: '0.5rem'}}>
            Model Name
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
            placeholder="Enter model name"
            required
          />
        </div>
        <div style={{marginBottom: '1rem'}}>
          <label style={{display: 'block', marginBottom: '0.5rem'}}>
            Description
          </label>
          <textarea
            value={description}
            onChange={e => setDescription(e.target.value)}
            style={{
              width: '100%',
              padding: '0.5rem',
              border: '1px solid #ddd',
              borderRadius: '4px',
              minHeight: '100px',
              resize: 'vertical',
            }}
            placeholder="Enter model description"
          />
        </div>
        <div style={{marginBottom: '1rem'}}>
          <label style={{display: 'block', marginBottom: '0.5rem'}}>
            Model Type
          </label>
          <select
            value={modelType}
            onChange={e => setModelType(e.target.value)}
            style={{
              width: '100%',
              padding: '0.5rem',
              border: '1px solid #ddd',
              borderRadius: '4px',
            }}>
            <option value="llm">Large Language Model</option>
            <option value="embedding">Embedding Model</option>
            <option value="classifier">Classifier</option>
            <option value="custom">Custom Model</option>
          </select>
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
            Add Model
          </button>
        </div>
      </form>
    </div>
  );
};
