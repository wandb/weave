import {Select} from '@wandb/weave/components/Form/Select';
import React from 'react';

export const LoadingSelect: typeof Select = props => {
  return <Select isDisabled placeholder="Loading..." {...props} />;
};
