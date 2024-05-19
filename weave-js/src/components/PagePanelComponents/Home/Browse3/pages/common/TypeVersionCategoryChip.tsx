import React from 'react';

import {Pill, TagColorName} from '../../../../../Tag';
import {KnownBaseObjectClassType} from '../wfReactInterface/wfDataModelHooksInterface';

const colorMap: Record<KnownBaseObjectClassType, TagColorName> = {
  Model: 'blue',
  Dataset: 'green',
};

export const TypeVersionCategoryChip: React.FC<{
  baseObjectClass: KnownBaseObjectClassType | null;
}> = props => {
  if (props.baseObjectClass == null) {
    return <></>;
  }
  const label = props.baseObjectClass;
  const color = colorMap[props.baseObjectClass] ?? 'moon';
  return <Pill color={color} label={label} />;
};
