import {typedDict} from '@wandb/weave/core';

export const inputType = {
  type: 'list' as const,
  objectType: typedDict({
    id: 'string',
    name: 'string',
    tagCategoryName: 'string',
    attributes: 'string',
  }),
};
