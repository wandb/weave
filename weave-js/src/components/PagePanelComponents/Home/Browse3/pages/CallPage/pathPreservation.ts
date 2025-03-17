/**
 * We have separated the notion of the "selected call" and the
 * "selected path" for a descendant of that call.
 */

import _ from 'lodash';

// These were chosen because they are not valid in op names
// and are more readable after URL encoding than alternatives.
const SEPARATOR_NODE = ' ';
const SEPARATOR_INDEX = '*';

export const updatePath = (
  parentPath: string,
  spanName: string,
  indexWithinSameName: number
) => {
  if (indexWithinSameName === -1) {
    // Skip root
    return '';
  }
  const thisPath = `${spanName}${SEPARATOR_INDEX}${indexWithinSameName}`;
  if (!parentPath) {
    return thisPath;
  }
  return `${parentPath}${SEPARATOR_NODE}${thisPath}`;
};

// Lower scores are better, 0 is a perfect match.
export const scorePathSimilarity = (pathA: string, pathB: string) => {
  let score = 0;
  if (pathA === pathB) {
    return score;
  }
  const pathAparts = pathA.split(SEPARATOR_NODE);
  const pathBparts = pathB.split(SEPARATOR_NODE);
  for (const [aPart, bPart] of _.zip(pathAparts, pathBparts)) {
    if (!aPart || !bPart) {
      // TODO: Something better to do with uneven length lists?
      score += 10;
      continue;
    }
    const aPartComponents = aPart.split(SEPARATOR_INDEX);
    const bPartComponents = bPart.split(SEPARATOR_INDEX);
    if (aPartComponents[0] !== bPartComponents[0]) {
      return Number.POSITIVE_INFINITY;
    }
    const aNum = parseInt(aPartComponents[1], 10);
    const bNum = parseInt(bPartComponents[1], 10);
    score += Math.abs(aNum - bNum);
  }
  return score;
};
