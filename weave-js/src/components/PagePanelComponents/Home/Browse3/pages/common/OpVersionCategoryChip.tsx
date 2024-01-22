import {Chip} from '@mui/material';
import _ from 'lodash';
import React from 'react';

import {HackyOpCategory} from '../wfInterface/types';

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
  return (
    <Chip
      label={_.capitalize(props.opCategory)}
      size="small"
      sx={{height: '20px', lineHeight: 2}}
      color={color as any}
    />
  );
};
