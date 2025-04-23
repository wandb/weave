import {
  AllBoundingBoxControls,
  BoundingBoxSliderControl,
} from '../components/MediaCard';
import {compare} from './ops';
import {BabylonPointCloud, SceneBox} from './render_babylon';

export const getEmptyFilter = () => ({
  hiddenBoundingBoxLabels: [],
  shownBoundingBoxLabels: [],
  hideAllBoxes: false,
  score: {},
});

export interface Filter {
  hiddenBoundingBoxLabels: string[];
  shownBoundingBoxLabels: string[];
  hideAllBoxes: boolean;
  score: BoundingBoxSliderControl;
}

export const DEFAULT_SCORE_GROUP_NAME = 'score';
export const BOXES = 'boxes';
const ALL_LABEL = 'all';
export const GROUP_NAME_3D_BOUNDING_BOXES = 'Labels';

function categorizeBoxVisibility(
  classIdControl: NonNullable<
    AllBoundingBoxControls['toggles']
  >[string][string],
  classIdToLabel: ClassIdToLabelMap
) {
  return Object.keys(classIdControl).reduce<{
    hiddenBoundingBoxLabels: string[];
    shownBoundingBoxLabels: string[];
  }>(
    ({hiddenBoundingBoxLabels, shownBoundingBoxLabels}, strClassId) => {
      if (strClassId === ALL_LABEL) {
        // all label handled separately
        return {hiddenBoundingBoxLabels, shownBoundingBoxLabels};
      }
      const classId = parseInt(strClassId, 10);
      const label = classIdToLabel.get(classId);
      const toggle = classIdControl[classId];
      // If the toggle is not disabled, then it's not a toggle we want to hide the box for.
      if (!label || !toggle) {
        return {hiddenBoundingBoxLabels, shownBoundingBoxLabels};
      }
      if (toggle.disabled) {
        hiddenBoundingBoxLabels.push(label);
      } else {
        shownBoundingBoxLabels.push(label);
      }

      return {hiddenBoundingBoxLabels, shownBoundingBoxLabels};
    },
    {
      hiddenBoundingBoxLabels: [] as string[],
      shownBoundingBoxLabels: [] as string[],
    }
  );
}

export const getFilterFromBBoxConfig = (
  boundingBoxConfig: AllBoundingBoxControls | undefined,
  classIdToLabel: ClassIdToLabelMap
): Filter => {
  if (!boundingBoxConfig) {
    return getEmptyFilter();
  }

  const classIdControl =
    boundingBoxConfig?.toggles?.[BOXES]?.[GROUP_NAME_3D_BOUNDING_BOXES] ?? {};

  const {hiddenBoundingBoxLabels, shownBoundingBoxLabels} =
    categorizeBoxVisibility(classIdControl, classIdToLabel);
  // AllBoundingBoxControls.styles controls how lines appear (solid, dashed/etc),
  // but that is currently not supported for 3d
  return {
    hiddenBoundingBoxLabels,
    shownBoundingBoxLabels,
    hideAllBoxes: classIdControl[ALL_LABEL]?.disabled ?? false,
    score: boundingBoxConfig.sliders
      ? boundingBoxConfig.sliders[DEFAULT_SCORE_GROUP_NAME]
      : {},
  };
};

export type ClassIdToLabelMap = Map<number, string>;
// the 3d case is similar to but not the same as the 2d case,
// since we don't have classes for boxes or multiple scores
// 2d code for filtering is in ImageWithOverlays.isBoundingBoxHidden()
// I tried converting this over to use isBoundingBoxHidden, and the
// transformation was tricky/more error prone than this way.
// TODO: merge this and isBoundingBoxHidden.
const isBoundingBoxVisible = (box: SceneBox, filter: Filter) => {
  if (
    filter.hideAllBoxes &&
    (box.label == null || !filter.shownBoundingBoxLabels.includes(box.label))
  ) {
    return false;
  }

  if (box.label && filter.hiddenBoundingBoxLabels.includes(box.label)) {
    return false;
  }

  // now filter on score
  if (box.score === undefined) {
    return true;
  }
  if (
    !filter.score ||
    filter.score.value === undefined || // value of 0 is valid for comparison
    filter.score.disabled
  ) {
    return true;
  }
  return compare(
    filter.score.comparator ?? 'gte',
    box.score,
    filter.score.value
  );
};

export const applyFilter = (
  data: BabylonPointCloud,
  filter: Filter
): BabylonPointCloud => ({
  points: [...data.points],
  vectors: [...data.vectors],
  boxes: data.boxes.filter(box => isBoundingBoxVisible(box, filter)),
});
