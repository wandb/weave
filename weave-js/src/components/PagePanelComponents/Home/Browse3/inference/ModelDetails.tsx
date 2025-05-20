/**
 * Display detailed information about one model.
 */
import React from 'react';

import {Alert} from '../../../../Alert';
import {ModelDetailsLoaded} from './ModelDetailsLoaded';
import {MODEL_INDEX} from './modelInfo';
import {InferenceContextType, ModelId} from './types';

type ModelDetailsProps = {
  id: ModelId;
  inferenceContext: InferenceContextType;
};

export const ModelDetails = ({id, inferenceContext}: ModelDetailsProps) => {
  const model = MODEL_INDEX[id];
  if (!model) {
    return (
      <div className="m-24">
        <Alert severity="error">Model not found</Alert>
      </div>
    );
  }
  return (
    <ModelDetailsLoaded model={model} inferenceContext={inferenceContext} />
  );
};
