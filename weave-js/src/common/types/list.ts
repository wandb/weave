import {Type} from '@wandb/weave/core';

export const LIST_ANY_TYPE: Type = {
  type: 'list' as const,
  objectType: 'any' as const,
};
