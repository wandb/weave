import {Chip} from '@mui/material';
import _ from 'lodash';
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
  return (
    <Chip
      label={_.capitalize(props.typeCategory)}
      size="small"
      sx={{height: '20px', lineHeight: 2}}
      color={color as any}
    />
  );
};
