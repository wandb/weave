import React, {useMemo} from 'react';
import * as _ from 'lodash';
import {
  CardImage,
  defaultHideImageState,
  DEFAULT_TILE_LAYOUT,
} from './ImageWithOverlays';
import {ControlsImageOverlays} from './ControlImageOverlays';
import * as MediaImage from '@wandb/cg/browser/model/mediaImage';
import * as Controls from './controlsImage';
import * as Panel2 from './panel';
import * as CGReact from '@wandb/common/cgreact';
import * as Op from '@wandb/cg/browser/ops';
import {LayoutType} from '@wandb/common/types/media';
import {Panel2Loader} from './PanelComp';
import {BoundingBoxSliderControl} from '@wandb/common/components/MediaCard';

const inputType = {type: 'image-file' as const};

export interface PanelImageConfig {
  hideImage?: boolean;
  tileLayout?: LayoutType;
  boxSliders?: {[valueName: string]: BoundingBoxSliderControl};
  overlayControls?: Controls.OverlayControls;
}
type PanelImageProps = Panel2.PanelProps<typeof inputType, PanelImageConfig>;

const PanelImageConfig: React.FC<PanelImageProps> = props => {
  const {config, updateConfig, input} = props;
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
  return (
    <ControlsImageOverlays
      controls={updatedConfig}
      classSets={classSets}
      updateControls={updateConfig}
    />
  );
};

const PanelImage: React.FC<PanelImageProps> = props => {
  const {config} = props;
  const inputNode = props.input;
  const nodeValueQuery = CGReact.useNodeValue(inputNode);
  const imageArtifact = useMemo(
    () => Op.opAssetArtifactVersion({asset: inputNode}),
    [inputNode]
  );

  const image: MediaImage.WBImage = nodeValueQuery.result;

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

  if (nodeValueQuery.loading) {
    return <Panel2Loader />;
  }

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
        <CardImage image={imageInCard} />
        <CardImage
          image={imageInCard}
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
          boundingBoxes={imageBoxes}
          classSets={classSets}
          boxSliders={config?.boxSliders}
          boxControls={otherBoxes}
        />
        {controls.map(([mc, bc], i) => (
          <CardImage
            key={i}
            image={imageInCard}
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

export const Spec: Panel2.PanelSpec<PanelImageConfig> = {
  id: 'image-file',
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
