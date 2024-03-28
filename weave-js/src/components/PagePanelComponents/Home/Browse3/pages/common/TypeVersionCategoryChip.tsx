import _ from 'lodash';
import React from 'react';

import {Pill, TagColorName} from '../../../../../Tag';
import {ObjectCategory} from '../wfReactInterface/wfDataModelHooksInterface';

const colorMap: Record<ObjectCategory, TagColorName> = {
  Model: 'blue',
  Dataset: 'green',
};

export const TypeVersionCategoryChip: React.FC<{
  typeCategory: ObjectCategory | null;
}> = props => {
  if (props.typeCategory == null) {
    return <></>;
  }
  const label = _.capitalize(props.typeCategory);
  const color = colorMap[props.typeCategory];
  return <Pill color={color} label={label} />;
};
