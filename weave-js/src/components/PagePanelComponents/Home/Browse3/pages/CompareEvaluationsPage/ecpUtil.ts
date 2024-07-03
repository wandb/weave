import { ScoreDimension } from './ecpTypes';


export const scoreIdFromScoreDimension = (dim: ScoreDimension): string => {
  return dim.scorerRef + '@' + dim.scoreKeyPath;
};
