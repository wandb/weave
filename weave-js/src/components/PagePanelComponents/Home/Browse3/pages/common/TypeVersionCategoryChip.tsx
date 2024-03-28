import _ from 'lodash';
import React from 'react';

import {Pill, TagColorName} from '../../../../../Tag';
import {HackyTypeCategory} from '../wfInterface/types';

const colorMap: Record<HackyTypeCategory, TagColorName> = {
  model: 'blue',
  dataset: 'green',
};

export const TypeVersionCategoryChip: React.FC<{
  typeCategory: HackyTypeCategory | null;
}> = props => {
  if (props.typeCategory == null) {
    return <></>;
  }
  const label = _.capitalize(props.typeCategory);
  const color = colorMap[props.typeCategory];
  return <Pill color={color} label={label} />;
};
