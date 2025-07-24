/**
 * Utilities for navigation related to inference.
 */
import {History} from 'history';

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
    const {playgroundEntity, playgroundProject} = inferenceContext;
    const path = playgroundUrl(playgroundEntity, playgroundProject);
    history.push(
      `${path}?${new URLSearchParams(
        targetModelIds.map(modelId => ['model', modelId])
      )}`
    );
  });
};
