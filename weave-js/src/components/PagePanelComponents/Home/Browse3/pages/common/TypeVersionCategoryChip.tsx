import {Chip} from '@mui/material';
import React from 'react';

import {HackyTypeCategory} from '../wfInterface/types';

const colorMap: {[key: string]: string} = {
  model: 'success',
  dataset: 'info',
  // 'tune': 'warning',
};

export const TypeVersionCategoryChip: React.FC<{
  typeCategory: HackyTypeCategory | null;
}> = props => {
  if (props.typeCategory == null) {
    return <></>;
  }
  const color = colorMap[props.typeCategory];
  return <Chip label={props.typeCategory} size="small" color={color as any} />;
};
