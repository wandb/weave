import {Chip} from '@mui/material';
import React from 'react';

import {HackyOpCategory} from '../interface/wf/types';

const colorMap: {[key: string]: string} = {
  train: 'success',
  predict: 'info',
  score: 'error',
  evaluate: 'warning',
  // 'tune': 'warning',
};

export const OpVersionCategoryChip: React.FC<{
  opCategory: HackyOpCategory | null;
}> = props => {
  if (props.opCategory == null) {
    return <></>;
  }
  const color = colorMap[props.opCategory];
  // The color seems to be borked
  return <Chip label={props.opCategory} size="small" color={color as any} />;
};
