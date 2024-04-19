import {RefObject} from 'react';

/**
 * The order of these colors are intentional!
 * This list includes all possible colors a label can be based ordered by hue.
 */
export const TAG_HUE_WHEEL = [
  'teal',
  'green',
  'cactus',
  'gold',
  'sienna',
  'red',
  'magenta',
  'purple',
  'blue',
  'moon',
] as const;
export type TagColorName = (typeof TAG_HUE_WHEEL)[number];

/**
 * The order of these colors are intentional!
 * This list can be used where we need to render multiple labels in a page because
 * this order will optimize contrast.
 */
export const TAG_COLOR_CONTRAST_WHEEL: TagColorName[] = [
  'teal',
  'gold',
  'sienna',
  'purple',
  'moon',
  'blue',
  'cactus',
  'magenta',
  'green',
  'red',
];

export const TAG_COLOR: Record<TagColorName, string> = {
  teal: 'text-teal-600 bg-teal-300/[0.48] dark:text-teal-400 dark:bg-teal-700/[0.48]',
  gold: 'text-gold-600 bg-gold-300/[0.48] dark:text-gold-400 dark:bg-gold-700/[0.48]',
  sienna:
    'text-sienna-600 bg-sienna-300/[0.48] dark:text-sienna-400 dark:bg-sienna-700/[0.48]',
  purple:
    'text-purple-600 bg-purple-300/[0.48] dark:text-purple-400 dark:bg-purple-700/[0.48]',
  moon: ' text-moon-600 bg-moon-300/[0.48] dark:text-moon-400 dark:bg-moon-700/[0.48]',
  blue: 'text-blue-600 bg-blue-300/[0.48] dark:text-blue-400 dark:bg-blue-700/[0.48]',
  cactus:
    'text-cactus-600 bg-cactus-300/[0.48] dark:text-cactus-400 dark:bg-cactus-700/[0.48]',
  magenta:
    'text-magenta-600 bg-magenta-300/[0.48] dark:text-magenta-400 dark:bg-magenta-700/[0.48]',
  green:
    'text-green-600 bg-green-300/[0.48] dark:text-green-400 dark:bg-green-700/[0.48]',
  red: 'text-red-600 bg-red-300/[0.48] dark:text-red-400 dark:bg-red-700/[0.48]',
};

export const TAG_HOVER_COLOR: Record<TagColorName, string> = {
  teal: 'hover:bg-teal-300/[0.68] hover:dark:bg-teal-700/[0.68]',
  gold: 'hover:bg-gold-300/[0.68] hover:dark:bg-gold-700/[0.68]',
  sienna: 'hover:bg-sienna-300/[0.68] hover:dark:bg-sienna-700/[0.68]',
  purple: 'hover:bg-purple-300/[0.68] hover:dark:bg-purple-700/[0.68]',
  moon: 'hover:bg-moon-300/[0.68] hover:dark:bg-moon-700/[0.68]',
  blue: 'hover:bg-blue-300/[0.68] hover:dark:bg-blue-700/[0.68]',
  cactus: 'hover:bg-cactus-300/[0.68] hover:dark:bg-cactus-700/[0.68]',
  magenta: 'hover:bg-magenta-300/[0.68] hover:dark:bg-magenta-700/[0.68]',
  green: 'hover:bg-green-300/[0.68] hover:dark:bg-green-700/[0.68]',
  red: 'hover:bg-red-300/[0.68] hover:dark:bg-red-700/[0.68]',
};

export function getRandomTagColor(): TagColorName {
  const randomIndex = Math.floor(Math.random() * TAG_HUE_WHEEL.length);
  return TAG_HUE_WHEEL[randomIndex];
}

export function getTagColorClass(color?: TagColorName): string {
  return TAG_COLOR[color ?? getRandomTagColor()];
}

export function getTagHoverClass(color?: TagColorName): string {
  return TAG_HOVER_COLOR[color ?? getRandomTagColor()];
}

export function getTagContrastColor(index?: number): TagColorName {
  if (!index) {
    return TAG_COLOR_CONTRAST_WHEEL[0];
  }
  return TAG_COLOR_CONTRAST_WHEEL[index % TAG_COLOR_CONTRAST_WHEEL.length];
}

/**
 * Determines if a label's text exceeds the specified width
 */
const MAX_TAG_LABEL_WIDTH_PX = 168;
export function isTagLabelTruncated(
  labelRef: RefObject<HTMLElement>,
  maxWidth: number = MAX_TAG_LABEL_WIDTH_PX
) {
  const labelLen = labelRef?.current?.clientWidth ?? 0;
  return labelLen >= maxWidth;
}
