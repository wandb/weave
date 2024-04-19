// Right now this is just a wrapper, but
// use this as a single code path for segmentation colors
// for future flexibility
import {colorN, ROBIN16} from './colors';

export const boxColor = (id: number) => {
  return colorN(id, ROBIN16);
};
