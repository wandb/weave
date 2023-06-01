import {Vector3} from '@babylonjs/core/Maths/math.vector';

import {applyFilter, Filter, getEmptyFilter} from './PointCloudFiltering';
import {
  BabylonPointCloud,
  RgbColor,
  SceneBox,
  ScenePoint,
  Vector,
} from './render_babylon';
import {cornersToEdges} from './SdkPointCloudToBabylon';

// We want to ensure that the filtering code is using value checks,
// so these functions return a new instance of the color each time they're called.
// That ensures that reference checks will fail.
const getColorA = (): RgbColor => [1, 1, 1];
const getColorB = (): RgbColor => [2, 2, 2];
const getColorC = (): RgbColor => [3, 3, 3];

const categoryA = 1;
const categoryB = 2;

// note that optional values like category/BB color/edge are
// deliberately not defined on some of the points/boxes
// to ensure that code handles the "value is not present" scenario
const Points: Record<string, ScenePoint> = {
  A: {
    position: [1, 1, 1],
    color: getColorA(),
    category: categoryA,
  },

  B: {
    position: [2, 2, 2],
    category: categoryB,
  },
  C: {
    position: [3, 3, 3],
    color: getColorC(),
  },
};

const Vectors: Record<string, Vector> = {
  A: {start: [1, 1, 1], end: [2, 2, 2], color: getColorA()},
};

const Boxes: Record<string, SceneBox> = {
  A: {
    edges: cornersToEdges([
      new Vector3(0, 0, 0),
      new Vector3(0, 1, 0),
      new Vector3(1, 0, 0),
      new Vector3(1, 1, 0),
      new Vector3(0, 0, 1),
      new Vector3(0, 1, 1),
      new Vector3(1, 0, 1),
      new Vector3(1, 1, 1),
    ]),
    label: 'First label',
    color: getColorA(),
    score: 1,
  },
  B: {
    edges: cornersToEdges([
      new Vector3(0, 0, 10),
      new Vector3(0, 1, 10),
      new Vector3(1, 0, 10),
      new Vector3(1, 1, 10),
      new Vector3(0, 0, 11),
      new Vector3(0, 1, 11),
      new Vector3(1, 0, 11),
      new Vector3(1, 1, 11),
    ]),
    color: getColorB(),
    score: 3,
  },
  C: {
    edges: cornersToEdges([
      new Vector3(0, 0, 110),
      new Vector3(0, 1, 110),
      new Vector3(1, 0, 110),
      new Vector3(1, 1, 110),
      new Vector3(0, 0, 111),
      new Vector3(0, 1, 111),
      new Vector3(1, 0, 111),
      new Vector3(1, 1, 111),
    ]),
    label: 'Third label',
    color: getColorC(),
    score: 5,
  },
};

const getTestData = (): BabylonPointCloud => ({
  points: [Points.A, Points.B, Points.C],
  vectors: [Vectors.A],
  boxes: [Boxes.A, Boxes.B, Boxes.C],
});

const runApplyFilter = (
  filterOverride: Partial<Filter>,
  dataOverride: Partial<BabylonPointCloud> = {}
): BabylonPointCloud =>
  applyFilter(
    {...getTestData(), ...dataOverride},
    {...getEmptyFilter(), ...filterOverride}
  );

describe('PointCloudFiltering', () => {
  it('does nothing for an empty filter', () => {
    const result = runApplyFilter({});
    expect(result).toEqual(getTestData());
  });
  it('removes bounding boxes by labels', () => {
    const expected = {...getTestData(), boxes: [Boxes.B, Boxes.C]};
    const result = runApplyFilter({hiddenBoundingBoxLabels: ['First label']});
    expect(result).toEqual(expected);
  });

  it('blocks all boxes for hideAllBoxes', () => {
    const expected = {...getTestData(), boxes: []};
    const result = runApplyFilter({hideAllBoxes: true});
    expect(result).toEqual(expected);
  });
  describe('score', () => {
    it('ignores disabled filters', () => {
      const result = runApplyFilter({
        score: {disabled: true, comparator: 'gte', value: 5},
      });
      expect(result).toEqual(getTestData());
    });
    it('handles gte', () => {
      const result = runApplyFilter({
        score: {disabled: false, comparator: 'gte', value: 5},
      });
      expect(result).toEqual({...getTestData(), boxes: [Boxes.C]});
    });
    it('handles lte', () => {
      const result = runApplyFilter({
        score: {disabled: false, comparator: 'lte', value: 3},
      });
      expect(result).toEqual({...getTestData(), boxes: [Boxes.A, Boxes.B]});
    });
    it('handles missing box score', () => {
      const BoxBWithoutScore = {...Boxes.B, score: undefined};
      const result = runApplyFilter(
        // this filter would normal drop A and B with their scores of 1 and 3
        {score: {disabled: false, comparator: 'gte', value: 5}},
        // box B has no score, so it will be ignored by score
        // filter (and be present in result)
        {boxes: [Boxes.A, BoxBWithoutScore, Boxes.C]}
      );
      expect(result).toEqual({
        ...getTestData(),
        boxes: [BoxBWithoutScore, Boxes.C],
      });
    });
    it('ignores filter where score value is missing', () => {
      const UndefinedValueForTest = undefined;
      const result = runApplyFilter(
        {
          score: {
            disabled: false,
            comparator: 'gte',
            value: UndefinedValueForTest,
          },
        },
        {}
      );
      expect(result).toEqual({...getTestData()});
    });
  });
});
