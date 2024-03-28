import React from 'react';

import {Pill, TagColorName} from '../../../../../Tag';
import {ObjectCategory} from '../wfReactInterface/wfDataModelHooksInterface';

const colorMap: Record<ObjectCategory, TagColorName> = {
  Model: 'blue',
  Dataset: 'green',
};

export const TypeVersionCategoryChip: React.FC<{
  rootObjectType: ObjectCategory | null;
}> = props => {
  if (props.rootObjectType == null) {
    return <></>;
  }
  const label = props.rootObjectType;
  const color = colorMap[props.rootObjectType] ?? 'moon';
  return <Pill color={color} label={label} />;
};
