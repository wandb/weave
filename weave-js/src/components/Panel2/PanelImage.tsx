import {BoundingBoxSliderControl} from '@wandb/weave/common/components/MediaCard';
import {BoundingBox2D, LayoutType} from '@wandb/weave/common/types/media';
import {
  opAssetArtifactVersion,
  replaceInputVariables,
  WBImage,
} from '@wandb/weave/core';
import * as _ from 'lodash';
import React, {FC, useMemo} from 'react';

import {useWeaveContext} from '../../context';
import * as CGReact from '../../react';
import {ControlsImageOverlays} from './ControlImageOverlays';
import * as Controls from './controlsImage';
import {
  CardImage,
  DEFAULT_TILE_LAYOUT,
  defaultHideImageState,
} from './ImageWithOverlays';
import * as Panel2 from './panel';

const inputType = {type: 'image-file' as const};

interface PanelImageConfigType {
  hideImage?: boolean;
  tileLayout?: LayoutType;
  boxSliders?: {[valueName: string]: BoundingBoxSliderControl};
  overlayControls?: Controls.OverlayControls;
}
type PanelImageProps = Panel2.PanelProps<
  typeof inputType,
  PanelImageConfigType
>;

const PanelImageConfig: FC<PanelImageProps> = ({
  config,
  updateConfig,
  input,
}) => {
  const {classSets, controls} = Controls.useImageControls(
    input.type,
    config?.overlayControls
  );
  const updatedConfig = useMemo(() => {
    if (controls === config?.overlayControls) {
      return config;
    } else {
      return {
        ...config,
        overlayControls: controls,
      };
    }
  }, [config, controls]);

  const weave = useWeaveContext();

  const exemplarsNode = useMemo(() => {
    return replaceInputVariables(input, weave.client.opStore);
  }, [input, weave.client.opStore]);

  const exemplars = CGReact.useNodeValue(exemplarsNode).result;
  const boxes = useMemo(() => {
    if (exemplars == null) {
      return {};
    }

    const exArray = _.isArray(exemplars) ? exemplars : [exemplars];

    return Object.fromEntries(
      exArray.reduce(
        (
          memo: Array<[string, BoundingBox2D[]]>,
          example: WBImage,
          idx: number
        ) => {
          const {boxes: exampleBoxes} = example ?? {};
          if (exampleBoxes == null) {
            return memo;
          }
          return memo.concat(
            Object.entries(exampleBoxes).map(([key, box]) => {
              return [`${idx}-${key}`, box];
            })
          );
        },
        []
      )
    );
  }, [exemplars]);

  return (
    <ControlsImageOverlays
      boxes={boxes}
      controls={updatedConfig}
      classSets={classSets}
      updateControls={updateConfig}
    />
  );
};

const PanelImage: FC<PanelImageProps> = ({config, input}) => {
  const inputNode = input;
  const nodeValueQuery = CGReact.useNodeValue(inputNode);
  const imageArtifact = useMemo(
    () => opAssetArtifactVersion({asset: inputNode}),
    [inputNode]
  );

  const image: WBImage = nodeValueQuery.result;

  const {
    maskControls: mergedMaskControls,
    boxControls: mergedBoxControls,
    classSets,
  } = Controls.useImageControls(inputNode.type, config?.overlayControls);

  const {imageBoxes, imageMasks, boxControls, maskControls} = useMemo(() => {
    const knownBoxKeys = image?.boxes != null ? _.keys(image.boxes) : [];
    const knownMaskKeys = image?.masks != null ? _.keys(image.masks) : [];
    const mergedMaskControlsValues = Object.values(mergedMaskControls);
    const mergedBoxControlsValues = Object.values(mergedBoxControls);
    const controlBoxKeys = mergedBoxControlsValues.map(c => c.name.slice(4));
    const controlMaskKeys = mergedMaskControlsValues.map(c => c.name.slice(5));

    const validBoxKeys = _.intersection(knownBoxKeys, controlBoxKeys);
    const validMaskKeys = _.intersection(knownMaskKeys, controlMaskKeys);

    const imageBoxesRes =
      image?.boxes != null ? validBoxKeys.map(k => image.boxes![k]) : undefined;
    const imageMasksRes =
      image?.masks != null
        ? validMaskKeys.map(k => {
            return {
              loadedFrom: imageArtifact,
              path: image.masks![k]?.path,
            };
          })
        : undefined;

    const boxControlsRes = mergedBoxControlsValues.filter(c =>
      validBoxKeys.includes(c.name.slice(4))
    );
    const maskControlsRes = mergedMaskControlsValues.filter(c =>
      validMaskKeys.includes(c.name.slice(5))
    );
    return {
      imageBoxes: imageBoxesRes,
      imageMasks: imageMasksRes,
      boxControls: boxControlsRes,
      maskControls: maskControlsRes,
    };
  }, [image, mergedBoxControls, mergedMaskControls, imageArtifact]);

  const {tileLayout, hideImage} = config ?? {};
  const hideImageDefault = defaultHideImageState(tileLayout);
  const imageInCard = {
    path: image?.path,
    loadedFrom: imageArtifact,
    width: image?.width,
    height: image?.height,
  };

  if (tileLayout === 'MASKS_NEXT_TO_IMAGE') {
    return (
      <div style={{display: 'flex', width: '100%', height: '100%'}}>
        <CardImage image={imageInCard} imageFileNode={inputNode} />
        <CardImage
          image={imageInCard}
          imageFileNode={inputNode}
          boundingBoxes={imageBoxes}
          masks={imageMasks}
          classSets={classSets}
          boxSliders={config?.boxSliders}
          maskControls={maskControls}
          boxControls={boxControls}
          hideImage={hideImage ?? hideImageDefault}
        />
      </div>
    );
  }

  if (tileLayout === 'ALL_SPLIT') {
    const controls: Array<
      [Controls.MaskControlState, Controls.BoxControlState | undefined]
    > = maskControls.map(mc => [
      mc,
      boxControls.find(bc => bc.name === mc.name),
    ]);
    const otherBoxes = boxControls.filter(bc =>
      maskControls.every(mc => bc.name !== mc.name)
    );
    return (
      <div style={{display: 'flex', width: '100%', height: '100%'}}>
        <CardImage
          image={imageInCard}
          imageFileNode={inputNode}
          boundingBoxes={imageBoxes}
          classSets={classSets}
          boxSliders={config?.boxSliders}
          boxControls={otherBoxes}
        />
        {controls.map(([mc, bc], i) => (
          <CardImage
            key={i}
            image={imageInCard}
            imageFileNode={inputNode}
            boundingBoxes={imageBoxes}
            masks={imageMasks?.slice(i, i + 1)}
            classSets={classSets}
            boxSliders={config?.boxSliders}
            maskControls={mc ? [mc] : undefined}
            boxControls={bc ? [bc] : undefined}
            hideImage={mc.hideImage ?? hideImageDefault}
          />
        ))}
      </div>
    );
  }

  return (
    <CardImage
      image={imageInCard}
      imageFileNode={inputNode}
      boundingBoxes={imageBoxes}
      masks={imageMasks}
      classSets={classSets}
      boxSliders={config?.boxSliders}
      maskControls={maskControls}
      boxControls={boxControls}
      hideImage={hideImage ?? hideImageDefault}
    />
  );
};

export const Spec: Panel2.PanelSpec<PanelImageConfigType> = {
  id: 'image-file',
  icon: 'photo',
  displayName: 'Image',
  ConfigComponent: PanelImageConfig,
  Component: PanelImage,
  inputType,
  canFullscreen: true,
  defaultFixedSize: config => {
    const {tileLayout = DEFAULT_TILE_LAYOUT} = config ?? {};

    let multiplier = 1;
    if (tileLayout === 'MASKS_NEXT_TO_IMAGE') {
      multiplier = 2;
    }
    if (tileLayout === 'ALL_SPLIT') {
      const masks = Object.values(config?.overlayControls ?? []).filter(
        v => v.type === 'mask'
      );
      multiplier = masks.length + 1;
    }

    return {
      width: 200 * multiplier,
      height: (9 / 16) * 200,
    };
  },
};
