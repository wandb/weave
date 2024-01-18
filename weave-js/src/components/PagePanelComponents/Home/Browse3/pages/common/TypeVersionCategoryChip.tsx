import {Chip} from '@mui/material';
import React from 'react';

import {HackyTypeCategory} from '../wfInterface/types';

const colorMap: {[key: string]: string} = {
  model: 'success',
  dataset: 'info',
  // 'tune': 'warning',
};

const ensureCapitalizedFirstLetter = (str: string) => {
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
};

export const TypeVersionCategoryChip: React.FC<{
  typeCategory: HackyTypeCategory | null;
}> = props => {
  if (props.typeCategory == null) {
    return <></>;
  }
  const color = colorMap[props.typeCategory];
  return (
    <Chip
      label={ensureCapitalizedFirstLetter(props.typeCategory)}
      size="small"
      sx={{height: '20px', lineHeight: 2}}
      color={color as any}
    />
  );
};
