import {CompareOp} from '../util/ops';

export interface Style {
  lineStyle: LineStyle;
}

export type LineStyle = 'line' | 'dotted' | 'dashed';

export interface BoundingBoxSliderControl {
  disabled?: boolean;
  comparator?: CompareOp;
  value?: number;
}

export interface BoundingBoxClassControl {
  disabled: boolean;
}

export interface AllBoundingBoxControls {
  sliders?: {
    [valueName: string]: BoundingBoxSliderControl;
  };
  toggles?: {
    [boxes: string]: {
      [groupName: string]: {
        [classIdOrAll: number | string]: BoundingBoxClassControl;
      };
    };
  };
  styles?: {
    [mediaKey: string]: {
      [boxKey: string]: Style;
    };
  };
}

export interface MaskControl {
  disabled: boolean;
  opacity: number;
}

export interface AllMaskControls {
  toggles?: {
    [mediaKey: string]: {
      [maskKey: string]: {[classOrAll: string]: MaskControl};
    };
  };
}

// The *Control classes are used to connect information
// controlled in the media panel to information used
// for rendering in the child cards
//
// e.g. Bounding box confidence slider or
//      Segmentation mask toggle
export interface Camera3DControl {
  cameraIndex: number;
}

export interface MediaPanelCardControl {
  cameraControl?: Camera3DControl;
  boundingBoxControl?: AllBoundingBoxControls;
  segmentationMaskControl?: AllMaskControls;
}
