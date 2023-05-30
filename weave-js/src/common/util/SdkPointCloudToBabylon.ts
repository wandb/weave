/* 
  I wanted to avoid importing babylonjs here to ensure this code stays 
  semi-independent but we catch some useful errors when doing some of
  the calculations involving vector3 so I am sticking with 
  importing just vector3.
  
  If we really don't want this babylon dependency in components
  I am assuming we could create our own version of Vector3
  fairly painlessly.
*/
import {Vector3} from '@babylonjs/core/Maths/math.vector';
import _ from 'lodash';

import {BoundingBox3D} from '../types/media';
import {ClassIdToLabelMap} from './PointCloudFiltering';
import {
  BabylonPointCloud,
  Position,
  RgbColor,
  SceneBox,
  ScenePoint,
  Vector,
} from './render_babylon';

/*
  This file holds the logic for taking user inputted point cloud data and 
  transforming it into babylon specific data. 
*/

const MAX_POINTS = 300000;
export const DEFAULT_POINT_COLOR: RgbColor = [230, 112, 23]; // burnt orange

export type Category = number;

type SdkFilePoint =
  | [x: number, y: number, z: number]
  | [x: number, y: number, z: number, categoryOrGreyScale: number] // if integer, category. if float, greyscale
  | [x: number, y: number, z: number, r: number, g: number, b: number];

export type Object3DScene = (SdkFilePoint[] & {type: undefined}) | SceneV1;

export const MaxAlphaValue = 1;

export interface SceneV1 {
  type: 'lidar/beta';
  points?: SdkFilePoint[];
  vectors?: Vector[];
  boxes?: Box[];
  center?: [number, number, number];
}

export const loadPointCloud = (fileContents: string): BabylonPointCloud => {
  let object3D;
  try {
    object3D = JSON.parse(fileContents);
  } catch (e: any) {
    const message = e instanceof Error ? e.message : 'unknown';
    console.log('Received error while parsing JSON:', e);
    throw new Error('Invalid point cloud JSON, parse error was: ' + message);
  }

  if (object3D.type !== 'lidar/beta' && !_.isArray(object3D)) {
    throw new Error(
      'Unsupported format, must be a list of points or a scene type.'
    );
  }

  return {
    points: handlePoints(object3D),
    vectors: (object3D.type === 'lidar/beta' && object3D.vectors) || [],
    boxes: handleBoxes(object3D),
  };
};

export const MAX_BOUNDING_BOX_LABELS_FOR_DISPLAY = 50;

export const getFilteringOptionsForPointCloud = (
  pointCloud: BabylonPointCloud
): {boxData: BoundingBox3D[]; newClassIdToLabel: ClassIdToLabelMap} => {
  const labelToClassId = new Map<string, number>();
  const boxData: BoundingBox3D[] = pointCloud.boxes.reduce<BoundingBox3D[]>(
    (resultSoFar: BoundingBox3D[], currentValue) => {
      const {label, score} = currentValue;
      if (!label && score === undefined) {
        return resultSoFar;
      }
      const toAdd: BoundingBox3D = {
        type: '3d',
        score,
      };
      if (label) {
        if (!labelToClassId.has(label)) {
          if (labelToClassId.size < MAX_BOUNDING_BOX_LABELS_FOR_DISPLAY) {
            labelToClassId.set(label, labelToClassId.size);
          } else {
            console.warn(
              'This point cloud had > ',
              MAX_BOUNDING_BOX_LABELS_FOR_DISPLAY,
              ' labels, so ',
              label,
              "won't be available for filtering."
            );
          }
        }
        const id = labelToClassId.get(label);
        if (id === undefined) {
          console.warn(
            'Unable to find filtering id for label:',
            label,
            'skipping this label for filtering'
          );
          if (!score) {
            return resultSoFar;
          }
        } else {
          toAdd.classInfo = {label, id};
        }
      }

      return resultSoFar.concat(toAdd);
    },
    []
  );
  return {
    boxData,
    newClassIdToLabel: new Map<number, string>(
      // switches keys & values
      Array.from(labelToClassId.entries()).map(([str, num]) => [num, str])
    ),
  };
};

export const getVertexCompatiblePositionsAndColors = (points: ScenePoint[]) => {
  const colors: number[] = [];
  const positions: number[] = [];

  for (const point of points) {
    let color: RgbColor;
    if (point.color) {
      color = point.color;
    } else if (point.category) {
      color = colorMap[point.category];
    } else {
      color = DEFAULT_POINT_COLOR;
    }
    // note that the push()s here add 3 and 4 elements to end of their respective arrays
    positions.push(point.position[0], point.position[1], point.position[2]);
    colors.push(color[0] / 255, color[1] / 255, color[2] / 255, MaxAlphaValue);
  }

  return {positions, colors};
};

export const handlePoints = (object3D: Object3DScene): ScenePoint[] => {
  const points =
    object3D.type === 'lidar/beta' ? object3D.points || [] : object3D;

  const truncatedPoints = points.slice(-MAX_POINTS);

  // Draw Points
  return truncatedPoints.map(point => {
    const [x, y, z, r, g, b] = point;
    const position: Position = [x, y, z];
    const category = r;

    if (r !== undefined && g !== undefined && b !== undefined) {
      // User passed in a RGB color
      return {position, color: [r, g, b]};
    } else if (category && Number.isInteger(category)) {
      // User passed in a single integer - this is a category
      return {position, category};
    } else if (category && category >= 0 && category <= 0) {
      // User passed in a single float - this is greyscale
      return {
        position,
        color: [255 * category, 255 * category, 255 * category],
      };
    } else {
      return {position, color: DEFAULT_POINT_COLOR};
    }
  });
};

export interface Box {
  // 8x3 x,y,z
  corners: Array<[number, number, number]>;
  label?: string;
  color: [number, number, number];
  score?: number;
}

export const handleBoxes = (object3D: Object3DScene): SceneBox[] => {
  const boxes = (object3D.type === 'lidar/beta' && object3D.boxes) || [];
  return boxes.map(box => {
    const {corners, color, label, score} = box;
    const edges = cornersToEdges(
      corners.map(p => {
        return new Vector3(...p);
      })
    );
    if (corners == null) {
      throw new Error('Box must have corners');
    }

    if (corners.length !== 8) {
      throw new Error('Box must have 8 corners');
    }
    return {edges, label, color, score};
  });
};

// Turns a set of corners into a box
export function cornersToEdges(corners: Vector3[]) {
  const remainingCorners = new Set(corners);
  const edges: Array<[Vector3, Vector3]> = [];
  const firstCorner = corners[0];
  const firstEnds = [];

  for (const points of combinations(_.drop(corners), 3, 3)) {
    if (areOrthogonal(firstCorner, points[0], points[1], points[2])) {
      edges.push([firstCorner, points[0]]);
      edges.push([firstCorner, points[1]]);
      edges.push([firstCorner, points[2]]);

      firstEnds.push(points[0]);
      firstEnds.push(points[1]);
      firstEnds.push(points[2]);

      // Remove the detected corner
      remainingCorners.delete(firstCorner);
      remainingCorners.delete(points[0]);
      remainingCorners.delete(points[1]);
      remainingCorners.delete(points[2]);
      break;
    }
  }

  if (firstEnds.length !== 3) {
    throw new Error('Provided corners do not form a box');
  }

  const remainingCornerArray = Array.from(remainingCorners);

  // The catty corner is the opposite diagonal corner
  // The farthest remaining point will be the catty corner
  const cattyCorner = _.sortBy(remainingCornerArray, p => {
    return -Vector3.Distance(firstCorner, p);
  })[0];

  remainingCorners.delete(cattyCorner);

  const midCorners = Array.from(remainingCorners);
  edges.push([cattyCorner, midCorners[0]]);
  edges.push([cattyCorner, midCorners[1]]);
  edges.push([cattyCorner, midCorners[2]]);

  // We now have two catty corner halves of a cube we need to connect
  // To draw the remaining 6 edges we loop through each of the 3 Loose
  // ends from our first half and find which two open end from the
  // other corner form a right angle
  for (const end of firstEnds) {
    if (areOrthogonal(end, firstCorner, midCorners[0], midCorners[1])) {
      edges.push([end, midCorners[0]]);
      edges.push([end, midCorners[1]]);
    } else if (areOrthogonal(end, firstCorner, midCorners[1], midCorners[2])) {
      edges.push([end, midCorners[1]]);
      edges.push([end, midCorners[2]]);
    } else if (areOrthogonal(end, firstCorner, midCorners[0], midCorners[2])) {
      edges.push([end, midCorners[0]]);
      edges.push([end, midCorners[2]]);
    } else {
      throw new Error('Provided corners do not form a box');
    }
  }

  return edges;
}

function combinations<T>(a: T[], min: number, max: number) {
  min = min || 1;
  max = max < a.length ? max : a.length;
  const fn = (n: number, src: T[], got: T[], allCur: T[][]) => {
    if (n === 0) {
      if (got.length > 0) {
        allCur[allCur.length] = got;
      }
      return;
    }
    for (let j = 0; j < src.length; j++) {
      fn(n - 1, src.slice(j + 1), got.concat([src[j]]), all);
    }
    return;
  };
  const all: T[][] = [];
  for (let i = min; i < a.length; i++) {
    fn(i, a, [], all);
  }
  if (a.length === max) {
    all.push(a);
  }
  return all;
}

// Checks if the base point forms a set of orthogonal vectors with
// the three given points
function areOrthogonal(base: Vector3, p1: Vector3, p2: Vector3, p3: Vector3) {
  const line1 = base.subtract(p1);
  const line2 = base.subtract(p2);
  const line3 = base.subtract(p3);
  // If all three are perpendicular add to the detected edges
  // Add the set of edges and to the list
  if (
    nearZero(Vector3.Dot(line1, line2)) &&
    nearZero(Vector3.Dot(line1, line3)) &&
    nearZero(Vector3.Dot(line2, line3))
  ) {
    return true;
  } else {
    return false;
  }
}

const epsilon = 0.003;

function nearZero(v: number) {
  return Math.abs(v) < epsilon;
}

// Using google palette - consider making this dynamic
// http://google.github.io/palette.js/
export const colorMap: {[key: number]: RgbColor} = {
  0: [21, 128, 114], // teal-ish?
  1: [55, 126, 184], // blue
  2: [102, 166, 30], // green
  3: [12, 216, 237], // bright darker blue
  4: [152, 78, 162], // purple
  5: [0, 210, 213], // brighter light blue-ish
  6: [255, 127, 0], // orange
  7: [175, 141, 0], // yucky brown-ish yellow
  8: [127, 128, 205], // blue-ish purple
  9: [179, 233, 0], // neon-ish green
  10: [196, 46, 96], // red-ish pink-ish
  11: [166, 86, 40], // brown
  12: [247, 129, 191], // lighter pink
  13: [144, 211, 199], // light green-ish blue-ish
  14: [190, 186, 218], // purple-ish grey
  15: [251, 128, 114], // pink ish orange
  // sorry these names aren't better, but it'll get you started :)
};
