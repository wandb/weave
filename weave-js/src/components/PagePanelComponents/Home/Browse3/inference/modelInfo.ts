/**
 * The structured data for the models is currently stored in a JSON file.
 */
import modelInfo from './modelsFinal.json';
import {Model, ModelInfo} from './types';

// TODO: On load, calculate some summary statistics we could use for visualization or filters.

export const MODEL_INFO = modelInfo as ModelInfo;
MODEL_INFO.models.forEach((model: Model) => {
  if (model.idHuggingFace) {
    model.urlHuggingFace = `https://huggingface.co/${model.idHuggingFace}`;
  }
});

// Create a mapping from model id to model object.
export const MODEL_INDEX = MODEL_INFO.models.reduce((acc, m) => {
  acc[m.id] = m;
  return acc;
}, {} as Record<string, Model>);

export const getHostedModels = (): Model[] => {
  return MODEL_INFO.models.filter(model => model.status === 'hosted');
};

export const getModelsByIds = (modelIds: string[]): Model[] => {
  return modelIds
    .map(id => MODEL_INDEX[id])
    .filter((model): model is Model => model != null);
};
