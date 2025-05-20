import modelInfo from './modelsFinal.json';
import {Model, ModelInfo} from './types';

export const MODEL_INFO = modelInfo as ModelInfo;
MODEL_INFO.models.forEach((model: Model) => {
  console.log({model});
  if (model.id_huggingface) {
    model.url_huggingface = `https://huggingface.co/${model.id_huggingface}`;
  }
});
