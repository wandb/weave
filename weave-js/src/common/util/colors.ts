import Color from 'color';

import * as globals from '../css/globals.styles';

export function colorN(
  index: number,
  palette: string[],
  alpha?: number
): string {
  /**
   * Given an index and a palette, returns a color.
   */
  const c = Color(palette[index % palette.length]);
  return c
    .alpha(alpha || c.alpha())
    .rgb()
    .string();
}

export type RGB = [number, number, number];
export const COLORS16 = [
  '#E87B9F', // pink
  '#A12864', // maroon
  '#DA4C4C', // red
  '#F0B899', // peach
  '#E57439', // orange
  '#EDB732', // yellow
  '#A0C75C', // lime
  '#479A5F', // kelly green
  '#87CEBF', // seafoam
  '#229487', // forest
  '#5BC5DB', // cyan
  '#5387DD', // blue
  '#7D54B2', // purple
  '#C565C7', // magenta
  '#A46750', // brown
  '#A1A9AD', // gray
];

export function colorNRGB(
  index: number,
  palette: string[],
  alpha?: number
): RGB {
  /**
   * Given an index and a palette, returns a color.
   */
  const c = Color(palette[index % palette.length]);
  return c
    .alpha(alpha || c.alpha())
    .rgb()
    .array() as [number, number, number];
}

// Our bespoke palette. This is in round-robin order.
export const ROBIN16 = [
  11, // blue
  2, // red
  7, // kelly green
  12, // purple
  0, // pink
  4, // orange
  8, // seafoam
  13, // magenta
  5, // yellow
  10, // cyan
  9, // forest
  3, // peach
  6, // lime
  14, // brown
  1, // maroon
  15, // gray
].map(i => COLORS16[i]);
export const GLOBAL_COLORS = {
  primary: Color(globals.primary),
  outline: Color('rgb(219, 219, 219)'),
  linkBlue: Color(globals.primaryText),
  lightGray: Color('#B3B3B0'),
  gray: Color(globals.textSecondary),
  background: globals.gray50,
};

export function colorFromString(s: string): RGB {
  return Color(s).rgb().array() as [number, number, number];
}

function hashString(s: string) {
  return s.split('').reduce((a, b) => {
    // tslint:disable:no-bitwise
    a = (a << 10) - a + b.charCodeAt(0);
    return a & a;
    // tslint:enable:no-bitwise
  }, 0);
}

export function colorFromName(name: string, alpha?: number) {
  /**
   * Hashes a given run name and returns a corresponding color.
   */
  const idx = Math.abs(hashString(name));
  return colorN(idx, COLORS16, alpha);
}
