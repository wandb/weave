/**
 * Colored chip representing Op Category.
 */
import {Pill, TagColorName} from '@wandb/weave/components/Tag';
import React from 'react';

// TODO: Align this list with HackyOpCategory
export const OP_CATEGORY = ['predict', 'train', 'evaluate', 'score'] as const;
export type OpCategoryType = (typeof OP_CATEGORY)[number];

type CategoryChipProps = {
  value: string;
};

// Using this format instead of a simple map to color name in case we want to
// add an icon or tooltip in the future.
type CategoryInfo = {
  color: TagColorName;
};

const CATEGORY_INFO: Record<OpCategoryType, CategoryInfo> = {
  predict: {
    color: 'teal',
  },
  train: {
    color: 'green',
  },
  evaluate: {
    color: 'sienna',
  },
  score: {
    color: 'gold',
  },
};

export const CategoryChip = ({value}: CategoryChipProps) => {
  const categoryStr = value.toLowerCase() as OpCategoryType;
  const label = categoryStr.charAt(0).toUpperCase() + categoryStr.slice(1);

  const categoryInfo = CATEGORY_INFO[categoryStr];
  if (categoryInfo == null) {
    return <Pill color="moon" label={label} />;
  }
  return <Pill color={categoryInfo.color} label={label} />;
};
