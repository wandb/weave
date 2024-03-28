import React from 'react';

import {Pill, TagColorName} from '../../../../../Tag';
import {ObjectCategory} from '../wfReactInterface/wfDataModelHooksInterface';

const colorMap: Record<ObjectCategory, TagColorName> = {
  Model: 'blue',
  Dataset: 'green',
};

export const TypeVersionCategoryChip: React.FC<{
  baseObjectClass: ObjectCategory | null;
}> = props => {
  if (props.baseObjectClass == null) {
    return <></>;
  }
  const label = props.baseObjectClass;
  const color = colorMap[props.baseObjectClass] ?? 'moon';
  return <Pill color={color} label={label} />;
};
