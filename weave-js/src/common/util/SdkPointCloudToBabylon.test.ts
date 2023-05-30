import {BabylonPointCloud, SceneBox} from './render_babylon';
import {
  colorMap,
  DEFAULT_POINT_COLOR,
  getFilteringOptionsForPointCloud,
  getVertexCompatiblePositionsAndColors,
  MAX_BOUNDING_BOX_LABELS_FOR_DISPLAY,
  MaxAlphaValue,
} from './SdkPointCloudToBabylon';

describe('getVertexCompatiblePositionsAndColors', () => {
  it('should translate points w/color into flat lists', () => {
    expect(
      getVertexCompatiblePositionsAndColors([
        {
          position: [10, 11, 12],
          color: [1, 2, 3],
        },
        {position: [20, 21, 22], color: [101, 102, 103]},
      ])
    ).toEqual({
      positions: [10, 11, 12, 20, 21, 22],
      colors: [
        1 / 255,
        2 / 255,
        3 / 255,
        MaxAlphaValue,
        101 / 255,
        102 / 255,
        103 / 255,
        MaxAlphaValue,
      ],
    });
  });
  it('should translate points w/category into flat lists', () => {
    const category = 1;
    const expectedColor = colorMap[category];
    expect(
      getVertexCompatiblePositionsAndColors([
        {
          position: [10, 11, 12],
          category,
        },
      ])
    ).toEqual({
      positions: [10, 11, 12],
      colors: [
        expectedColor[0] / 255,
        expectedColor[1] / 255,
        expectedColor[2] / 255,
        MaxAlphaValue,
      ],
    });
  });
  it('should translate points with no color/category into flat lists', () => {
    const expectedColor = DEFAULT_POINT_COLOR;
    expect(
      getVertexCompatiblePositionsAndColors([
        {
          position: [10, 11, 12],
        },
      ])
    ).toEqual({
      positions: [10, 11, 12],
      colors: [
        expectedColor[0] / 255,
        expectedColor[1] / 255,
        expectedColor[2] / 255,
        MaxAlphaValue,
      ],
    });
  });
});

export const Boxes: Record<string, SceneBox> = {
  LabelAndScore: {
    edges: [],
    label: 'First label',
    color: [1, 1, 1],
    score: 1,
  },
  LabelOnly: {
    edges: [],
    label: 'Other label',
    color: [1, 1, 1],
  },
  ScoreOnly: {
    edges: [],
    color: [1, 1, 1],
    score: 20,
  },
  ScoreZero: {
    edges: [],
    color: [1, 1, 1],
    score: 0,
  },
};

const getPointCloud = (boxes: SceneBox[]): BabylonPointCloud => ({
  boxes,
  points: [],
  vectors: [],
});

describe('getFilteringOptionsForPointCloud', () => {
  it('adds if the box has only a score', () => {
    const {boxData, newClassIdToLabel} = getFilteringOptionsForPointCloud(
      getPointCloud([Boxes.ScoreOnly])
    );
    expect(boxData).toEqual([{type: '3d', score: 20}]);
    expect(newClassIdToLabel.size).toEqual(0);
  });
  it('adds if the box has only a 0 score', () => {
    const {boxData} = getFilteringOptionsForPointCloud(
      getPointCloud([Boxes.ScoreZero])
    );
    expect(boxData).toEqual([{type: '3d', score: 0}]);
  });
  it('adds if it has only a label', () => {
    const {boxData, newClassIdToLabel} = getFilteringOptionsForPointCloud(
      getPointCloud([Boxes.LabelOnly])
    );
    expect(boxData).toEqual([
      {type: '3d', classInfo: {id: 0, label: 'Other label'}},
    ]);
    expect(Array.from(newClassIdToLabel.entries())).toEqual([
      [0, 'Other label'],
    ]);
  });
  it('adds if it has a label and score', () => {
    const {boxData, newClassIdToLabel} = getFilteringOptionsForPointCloud(
      getPointCloud([Boxes.LabelAndScore])
    );
    expect(boxData).toEqual([
      {type: '3d', score: 1, classInfo: {id: 0, label: 'First label'}},
    ]);
    expect(Array.from(newClassIdToLabel.entries())).toEqual([
      [0, 'First label'],
    ]);
  });
  it("doesn't add if no label or score", () => {
    const {boxData, newClassIdToLabel} = getFilteringOptionsForPointCloud(
      getPointCloud([])
    );
    expect(boxData).toHaveLength(0);
    expect(newClassIdToLabel.size).toEqual(0);
  });
  it("doesn't add if only label and already at max labels", () => {
    expect(MAX_BOUNDING_BOX_LABELS_FOR_DISPLAY).toEqual(50); // precondition: if this fails, adjust test below
    const boxes = [...Array(60).keys()].map<SceneBox>(num => ({
      edges: [],
      label: 'label' + num,
      color: [1, 1, 1],
    }));
    boxes[52].score = 100; // this one will get added because of score, but won't have a label mapping
    const {boxData, newClassIdToLabel} = getFilteringOptionsForPointCloud(
      getPointCloud(boxes)
    );
    expect(boxData).toHaveLength(50 + 1); // MAX_BOUNDING... plus one for the box with a score
    // spot check a couple
    expect(boxData[0]).toEqual({
      type: '3d',
      classInfo: {id: 0, label: 'label0'},
    });
    expect(boxData[5]).toEqual({
      type: '3d',
      classInfo: {id: 5, label: 'label5'},
    });
    expect(boxData[50]).toEqual({
      type: '3d',
      score: 100,
    });
    expect(newClassIdToLabel.get(0)).toEqual('label0');
    expect(newClassIdToLabel.get(49)).toEqual('label49');
  });
});
