import {WBIcon} from '@wandb/ui';
import React from 'react';

import {ControlsImageOverlaysControls} from './ControlImageOverlays';
import * as Controls from './controlsImage';
import {DEFAULT_TILE_LAYOUT, defaultHideImageState} from './ImageWithOverlays';

type ControlMaskProps = {
  mask: Controls.MaskControlState;
  updateMask: (newMask: Partial<Controls.MaskControlState>) => void;
  controls: ControlsImageOverlaysControls;
  updateControls(partialConfig: Partial<ControlsImageOverlaysControls>): void;
};

export const ControlsMask: React.FC<ControlMaskProps> = ({
  mask,
  updateMask,
  controls,
  updateControls,
}) => {
  const {tileLayout = DEFAULT_TILE_LAYOUT} = controls;
  const isAllSplit = tileLayout === 'ALL_SPLIT';
  const defaultHiddenState = defaultHideImageState(tileLayout);
  const toggleImageVisibility = () => {
    if (isAllSplit) {
      const hideImage = !(mask.hideImage ?? defaultHiddenState);
      updateMask({...mask, hideImage});
    } else {
      const hideImage = !(controls.hideImage ?? defaultHiddenState);
      updateControls({...controls, hideImage});
    }
  };

  const isImageHidden =
    (isAllSplit ? mask.hideImage : controls.hideImage) ?? defaultHiddenState;

  return (
    <span>
      <WBIcon
        style={{
          fontSize: '1.1em',
          cursor: 'pointer',
          verticalAlign: 'middle',
          color: isImageHidden ? 'grey' : 'black',
        }}
        onClick={toggleImageVisibility}
        name="panel-images"
      />
    </span>
  );
};
