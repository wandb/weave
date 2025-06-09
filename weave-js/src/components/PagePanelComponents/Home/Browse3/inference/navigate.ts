/**
 * Utilities for navigation related to inference.
 */
import {History} from 'history';

import {MODEL_INDEX} from './modelInfo';
import {InferenceContextType} from './types';

const playgroundUrl = (entityName: string, projectName: string) => {
  return `/${entityName}/${projectName}/weave/playground`;
};

export const navigateToPlayground = (
  history: History,
  modelIds: string | string[],
  inferenceContext: InferenceContextType
) => {
  inferenceContext.ensureProjectExists().then(() => {
    const targetModelIds = Array.isArray(modelIds) ? modelIds : [modelIds];
    const playgroundIds = targetModelIds.map(
      id => MODEL_INDEX[id].idPlayground
    );
    const {playgroundEntity, playgroundProject} = inferenceContext;
    const path = playgroundUrl(playgroundEntity, playgroundProject);
    history.push(
      `${path}?${new URLSearchParams(
        playgroundIds.map(modelId => ['model', modelId])
      )}`
    );
  });
};
