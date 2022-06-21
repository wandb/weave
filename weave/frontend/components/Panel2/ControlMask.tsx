import React from 'react';
import makeComp from '@wandb/common/util/profiler';
import {WBIcon} from '@wandb/ui';
import {ControlsImageOverlaysControls} from './ControlImageOverlays';
import * as Controls from './controlsImage';
import {defaultHideImageState, DEFAULT_TILE_LAYOUT} from './ImageWithOverlays';

export const ControlsMask = makeComp<{
  mask: Controls.MaskControlState;
  updateMask: (newMask: Partial<Controls.MaskControlState>) => void;
  controls: ControlsImageOverlaysControls;
  updateControls(partialConfig: Partial<ControlsImageOverlaysControls>): void;
}>(
  ({mask, updateMask, controls, updateControls}) => {
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
  },
  {id: 'ControlsMask'}
);
