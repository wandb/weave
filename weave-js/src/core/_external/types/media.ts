interface PositionMiddleBase {
  middle: [number, number];
  width: number;
  height: number;
}

interface PositionMinMax {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
}
export interface BoundingBox2D {
  position: PositionMiddleBase | PositionMinMax;
  class_id: number;
  box_caption?: string;
  scores?: {
    [key: string]: number;
  };
  domain?: 'pixel';
}
