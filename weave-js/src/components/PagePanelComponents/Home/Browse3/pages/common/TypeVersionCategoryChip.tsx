import React from 'react';

import {Pill, TagColorName} from '../../../../../Tag';
import {KnownBaseObjectClassType} from '../wfReactInterface/wfDataModelHooksInterface';

const colorMap: Record<KnownBaseObjectClassType, TagColorName> = {
  Prompt: 'purple',
  Model: 'blue',
  Dataset: 'green',
  Evaluation: 'cactus',
  Leaderboard: 'gold',
  Scorer: 'purple',
  ActionSpec: 'sienna',
  AnnotationSpec: 'magenta',
  SavedView: 'magenta',
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
