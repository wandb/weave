import {LineStyle, Style} from '@wandb/weave/common/components/MediaCard';
import {BoundingBox2D, LayoutType} from '@wandb/weave/common/types/media';
import {colorFromString} from '@wandb/weave/common/util/colors';
import {boxColor} from '@wandb/weave/common/util/media';
import {
  constString,
  File,
  Node,
  opArtifactVersionFile,
  opAssetFile,
  VoidNode,
} from '@wandb/weave/core';
import * as _ from 'lodash';
import React, {FC, useEffect, useMemo, useRef, useState} from 'react';
import styled from 'styled-components';

import {compare} from '../../compare';
import * as Controls from './controlsImage';
import {ClassSetControls, ClassSetState, ClassState} from './controlsImage';
import {useSignedUrlWithExpiration} from './useAssetFromArtifact';

// Copied from media.tsx, for some reason importing media.tsx
// doesn't work with storybook, at least at the moment I'm doing
// this on the plane with no wifi (and therefore no ability to
// update yarn packages).
export const DEFAULT_ALL_MASK_CONTROL: Controls.OverlayClassState = {
  disabled: false,
  opacity: 0.6,
};

export const DEFAULT_CLASS_MASK_CONTROL: Controls.OverlayClassState = {
  disabled: false,
  opacity: 1,
};

export const DEFAULT_CLASS_COLOR = [0, 0, 0, 0];

export const DEFAULT_TILE_LAYOUT: LayoutType = 'ALL_STACKED';
export const defaultHideImageState = (layout?: LayoutType) =>
  layout != null && layout !== 'ALL_STACKED';

interface CardImageProps {
  image: {
    loadedFrom: Node;
    path: string;
    width: number;
    height: number;
  };
  imageFileNode: Node;
  masks?: Array<{loadedFrom: Node; path: string}>;
  boundingBoxes?: BoundingBox2D[][];
  classSets?: ClassSetControls;
  maskControls?: Controls.MaskControlState[];
  boxControls?: Controls.BoxControlState[];
  boxSliders?: Controls.BoxSliderState;
  hideImage?: boolean;
}

export const CardImage: FC<CardImageProps> = ({
  image,
  imageFileNode,
  masks,
  boundingBoxes,
  classSets,
  boxControls,
  maskControls,
  boxSliders,
  hideImage,
}) => {
  const assetFileNode = useMemo(
    () => opAssetFile({asset: imageFileNode}),
    [imageFileNode]
  ) as Node<File>;
  const {signedUrl} = useSignedUrlWithExpiration(assetFileNode, 60 * 1000);

  const imageStyle = {
    position: 'absolute',
    height: '100%',
    width: '100%',
  } as const;

  return (
    <div
      data-test="card-image"
      style={{
        height: '100%',
        width: '100%',
        position: 'relative',
      }}>
      {signedUrl == null ? (
        <div />
      ) : (
        <>
          {!hideImage && (
            <img
              style={{...imageStyle, objectFit: 'contain'}}
              alt={image.path}
              src={signedUrl}
            />
          )}
          {masks != null &&
            maskControls?.map((maskControl, i) => {
              const mask = masks[i];
              if (maskControl != null) {
                const classSet = (classSets ?? {})[maskControl.classSetID];
                return (
                  <SegmentationMaskFromCG
                    key={i}
                    style={imageStyle}
                    filePath={mask}
                    mediaSize={{width: image.width, height: image.height}}
                    maskControls={maskControl as Controls.MaskControlState}
                    classSet={classSet}
                  />
                );
              }
              return undefined;
            })}

          {boundingBoxes != null &&
            boxControls?.map((boxControl, i) => {
              if (boxControl != null) {
                const classSet = classSets?.[boxControl.classSetID];
                return (
                  <BoundingBoxes
                    key={i}
                    style={imageStyle}
                    bboxControls={boxControl as Controls.BoxControlState}
                    boxData={boundingBoxes[i]}
                    mediaSize={{width: image.width, height: image.height}}
                    classSet={classSet}
                    sliderControls={boxSliders}
                  />
                );
              }
              return undefined;
            })}
        </>
      )}
    </div>
  );
};

type RGBA = [number, number, number, number];

/**
 * Draw image data to canvas. Throws error if context not found.
 */
const drawImageData = (canvas: HTMLCanvasElement, imageData: ImageData) => {
  const ctx = canvas.getContext('2d');
  if (ctx == null) {
    throw new Error("Can't get context in image render");
  }
  ctx.putImageData(imageData, 0, 0);
};

/**
 * Replaces class ID with class color.
 *
 * @param segmentation contains segmentation data in (width x height x RGBA). R is
 * used as the class ID.
 * @param classColors maps class ids to colors
 */
const drawSegmentation = (
  segmentation: ImageData,
  classColors: Record<number, RGBA>
) => {
  const {width, height} = segmentation;
  const newImageData = new ImageData(width, height);
  for (let x = 0; x < width; x++) {
    for (let y = 0; y < height; y++) {
      const index = x * 4 + y * 4 * width;
      const classID = segmentation.data[index];
      const color = classColors[classID] || DEFAULT_CLASS_COLOR;
      const [r, g, b, a] = color;

      newImageData.data[index] = r;
      newImageData.data[index + 1] = g;
      newImageData.data[index + 2] = b;
      newImageData.data[index + 3] = a;
    }
  }
  return newImageData;
};

const OverlayCanvas = styled.canvas`
  width: 100%;
  height: 100%;
  object-fit: contain;
`;

interface SegmentationCanvasProps {
  segmentation: ImageData;
  classState: Record<string, ClassState>;
  classOverlay: Record<string, Controls.OverlayClassState>;
}

/**
 * Creates a canvas for visualizing class segmentation.
 */
const SegmentationCanvas: FC<SegmentationCanvasProps> = ({
  segmentation,
  classState,
  classOverlay,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const {width, height} = segmentation;

  // Create colored segmentation image data and draws it
  useEffect(() => {
    const allToggle = classOverlay.all ?? DEFAULT_ALL_MASK_CONTROL;
    const classColors = Object.fromEntries(
      _.map(classState, ({color}, classId) => {
        const classToggle = classOverlay[classId] ?? DEFAULT_CLASS_MASK_CONTROL;

        const {disabled, opacity} = classToggle;
        const isDisabled = allToggle.disabled || disabled;

        const rgb = colorFromString(color);
        const alpha = isDisabled ? 0 : allToggle.opacity * opacity * 255;
        const rgba: RGBA = [...rgb, alpha] as RGBA; // TODO(np): Type assertion

        return [classId, rgba];
      })
    );
    const newImageData = drawSegmentation(segmentation, classColors);

    if (canvasRef.current == null || newImageData == null) {
      return;
    }
    const canvas = canvasRef.current;
    drawImageData(canvas, newImageData);
  }, [segmentation, classState, classOverlay]);

  return <OverlayCanvas width={width} height={height} ref={canvasRef} />;
};

export interface SegmentationMaskLoaderProps {
  directUrl?: string;
  style?: React.CSSProperties;
  mediaSize: {
    width: number;
    height: number;
  };
  classState: Record<string, ClassState>;
  classOverlay: Record<string, Controls.OverlayClassState>;
}

export const SegmentationMaskLoader: FC<SegmentationMaskLoaderProps> = ({
  directUrl,
  classState,
  classOverlay,
  mediaSize,
  style,
}) => {
  const [classIDImageData, setClassIDImageData] = useState<ImageData>();

  // On file load pull image data into memory
  const loadSuccess = React.useCallback(
    (url: string) => {
      const tempCanvas = document.createElement('canvas');
      tempCanvas.width = mediaSize.width;
      tempCanvas.height = mediaSize.height;
      const ctx = tempCanvas.getContext('2d');
      if (ctx == null) {
        throw new Error("Can't get context in Segmentation Mask");
      }

      const img = new Image(mediaSize.width, mediaSize.height);
      // Load Results into image data so we can read the values
      // in memory
      img.onload = () => {
        ctx?.drawImage(img, 0, 0);
        const imageData = ctx.getImageData(
          0,
          0,
          mediaSize.width,
          mediaSize.height
        );
        setClassIDImageData(imageData);
      };
      img.crossOrigin = 'Anonymous';
      img.src = url;
    },
    [mediaSize.width, mediaSize.height]
  );

  useEffect(() => {
    if (directUrl != null) {
      loadSuccess(directUrl);
    }
  }, [directUrl, loadSuccess]);

  if (classIDImageData == null) {
    return <div />;
  }
  if (directUrl == null) {
    return <div>missing</div>;
  }

  return (
    <div style={{...style}}>
      <SegmentationCanvas
        segmentation={classIDImageData}
        classState={classState}
        classOverlay={classOverlay}
      />
    </div>
  );
};

type SegmentationMaskFromCGProps = {
  filePath: {
    loadedFrom: Node;
    path: string;
  };
  style?: React.CSSProperties;
  mediaSize: {
    width: number;
    height: number;
  };
  maskControls: Controls.MaskControlState;
  classSet: ClassSetState;
};

/**
 * Get segmentation data file URL from CG.
 */
const SegmentationMaskFromCG: FC<SegmentationMaskFromCGProps> = props => {
  const {filePath, classSet, maskControls} = props;
  const {loadedFrom, path} = filePath;

  const fileNode = useMemo(
    () =>
      opArtifactVersionFile({
        artifactVersion: loadedFrom as any,
        path: constString(path),
      }) as
        | Node<{
            type: 'file';
            extension: string;
          }>
        | VoidNode,
    [loadedFrom, path]
  );
  const {signedUrl} = useSignedUrlWithExpiration(fileNode, 60 * 1000);

  if (signedUrl == null) {
    return <div />;
  }
  return (
    <SegmentationMaskLoader
      {...props}
      directUrl={signedUrl}
      classState={classSet.classes}
      classOverlay={maskControls.classOverlayStates}
    />
  );
};

export interface BoundingBoxCanvasProps {
  mediaSize: {width: number; height: number};
  boxData: BoundingBox2D[];
  bboxControls: Controls.BoxControlState;
  sliders?: Controls.BoxSliderState;
  classStates?: Record<string, ClassState>;
  boxStyle?: React.CSSProperties;
  sliderControls?: Controls.BoxSliderState;
}

const isBoundingBoxHidden = (
  box: BoundingBox2D,
  bboxControls: Controls.BoxControlState,
  sliders?: Controls.BoxSliderState
) => {
  const {classOverlayStates} = bboxControls;
  const allDisabled =
    classOverlayStates.all?.disabled ?? DEFAULT_ALL_MASK_CONTROL.disabled;

  if (allDisabled) {
    return true;
  }

  const {class_id: classId} = box;
  const classState = classOverlayStates?.[classId];
  if (classState?.disabled) {
    return true;
  }

  if (sliders == null) {
    return false;
  }

  return Object.keys(sliders).some(k => {
    const slider = sliders?.[k];
    if (slider.value == null || (slider.disabled ?? false)) {
      return false;
    }

    const boxScore = box.scores?.[k];
    if (boxScore == null) {
      return false;
    }

    return !compare(slider.comparator ?? 'gte', boxScore, slider.value);
  });
};

export const BoundingBoxesCanvas: FC<BoundingBoxCanvasProps> = ({
  mediaSize,
  boxData,
  bboxControls,
  classStates,
  sliderControls,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const {lineStyle, classOverlayStates} = bboxControls;

  useEffect(() => {
    if (canvasRef.current == null) {
      return;
    }

    const canvas = canvasRef.current;
    const opts = {
      boxStyle: {lineStyle: lineStyle ?? 'line'},
      hideLabel: bboxControls.hideLabels ?? false,
    };

    clearCanvas(canvas);

    for (const box of boxData) {
      const {class_id: classId} = box;
      const isHidden = isBoundingBoxHidden(box, bboxControls, sliderControls);

      if (!isHidden) {
        const color = boxColor(classId);
        const name = classStates?.[classId]?.name ?? `ID: ${box.class_id}`;
        drawBox(canvas, box, name, mediaSize, color, opts);
      }
    }
  }, [
    classOverlayStates,
    classStates,
    lineStyle,
    boxData,
    bboxControls,
    mediaSize,
    sliderControls,
  ]);

  return <OverlayCanvas {...mediaSize} ref={canvasRef} />;
};

export interface BoundingBoxesProps {
  style?: React.CSSProperties;
  mediaSize: {
    width: number;
    height: number;
  };
  boxData: BoundingBox2D[];
  bboxControls: Controls.BoxControlState;
  sliderControls?: Controls.BoxSliderState;
  boxStyle?: React.CSSProperties;
  classSet?: ClassSetState;
}

const BoundingBoxes: FC<BoundingBoxesProps> = props => (
  <div style={{...props.style}}>
    <BoundingBoxesCanvas {...props} classStates={props.classSet?.classes} />
  </div>
);

const clearCanvas = (canvas: HTMLCanvasElement) => {
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    throw new Error('Tried to clear canvas without context');
  }
  ctx.clearRect(0, 0, canvas.width, canvas.height);
};

const lineDashArray = (dashStyle: LineStyle) => {
  const mapping = {
    line: [],
    dotted: [2, 2],
    dashed: [12, 6],
  };

  return mapping[dashStyle];
};

const drawBox = (
  c: HTMLCanvasElement,
  box: BoundingBox2D,
  className: string,
  mediaSize: {width: number; height: number},
  color: string,
  opts?: {boxStyle: Style | undefined; hideLabel: boolean | undefined}
) => {
  const ctx = c.getContext('2d');

  if (ctx == null) {
    throw new Error('Canvas context not valid');
  }

  let w: number;
  let h: number;
  let x: number;
  let y: number;
  if ('minX' in box.position && box.position.minX != null) {
    w = box.position.maxX - box.position.minX;
    h = box.position.maxY - box.position.minY;
    x = box.position.minX;
    y = box.position.minY;
  } else if ('middle' in box.position && box.position.middle != null) {
    w = box.position.width;
    h = box.position.height;
    x = box.position.middle[0] - w / 2;
    y = box.position.middle[1] - h / 2;
  } else {
    throw new Error(
      `Invalid position for bounding box: ${JSON.stringify(box, null, 2)}`
    );
  }

  const domain = box.domain;
  if (domain === 'pixel') {
    // Do nothing
  } else {
    const {width, height} = mediaSize;
    x *= width;
    y *= height;
    w *= width;
    h *= height;
  }

  // Draw the 2D Box
  const lineWidth = 3;
  ctx.lineWidth = lineWidth;
  if (opts?.boxStyle?.lineStyle != null) {
    ctx.setLineDash(lineDashArray(opts.boxStyle.lineStyle));
  }
  ctx.strokeStyle = color;
  ctx.strokeRect(x, y, w, h);

  // Draw the label
  if (!opts?.hideLabel) {
    const {box_caption} = box;
    const labelHeight = 14;
    ctx.font = '14px Arial';
    const labelPad = 4;

    const text = box_caption ?? className;
    const tm = ctx.measureText(text);
    // If label doesn't fit draw from right edge instead of left
    const labelShift = tm.width + x > c.width ? w - tm.width - labelPad : 0;
    // Label background
    ctx.fillStyle = color;
    ctx.fillRect(
      x - lineWidth / 2 + labelShift,
      y - labelHeight - 2 * labelPad,
      tm.width + labelPad * 2,
      labelHeight + 2 * labelPad
    );

    // Text
    ctx.fillStyle = 'white';
    ctx.fillText(text, x + labelPad + labelShift, y - labelPad);
  }
};
