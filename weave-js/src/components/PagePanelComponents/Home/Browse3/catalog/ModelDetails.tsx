import React from 'react';

import {ModelDetailsLoaded} from './ModelDetailsLoaded';
import {MODEL_INFO} from './modelInfo';
import {Model, ModelId} from './types';

type ModelDetailsProps = {
  id: ModelId;
};

export const ModelDetails = ({id}: ModelDetailsProps) => {
  console.log({id});
  const model = MODEL_INFO.models.find((m: Model) => m.id === id);
  if (!model) {
    return <div>Model not found</div>;
  }
  return <ModelDetailsLoaded model={model} />;
};
