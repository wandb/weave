import React from 'react';
import {Button, Popup} from 'semantic-ui-react';
import makeComp from '@wandb/common/util/profiler';
import LegacyWBIcon from '@wandb/common/components/elements/LegacyWBIcon';
import * as Controls from './controlsImage';
import {LineStyle} from '@wandb/common/components/MediaCard';

const styleOptions: Array<{key: LineStyle; icon: string}> = [
  {
    key: 'line',
    icon: 'line-solid',
  },
  {
    key: 'dotted',
    icon: 'line-dot',
  },
  {
    key: 'dashed',
    icon: 'line-dash',
  },
];

export const ControlsBoxStyle = makeComp<{
  box: Controls.BoxControlState;
  updateBox: (newBox: Partial<Controls.BoxControlState>) => void;
}>(
  ({box, updateBox}) => {
    const activeMarkOption =
      styleOptions.find(o => o.key === box.lineStyle) || styleOptions[0];

    return (
      <Popup
        offset={-12}
        className="control-box-popup"
        on="click"
        trigger={
          <LegacyWBIcon
            name={activeMarkOption.icon}
            className="control-box-picker"
          />
        }
        content={
          <Button.Group className="control-box-buttons">
            {styleOptions.map(markOption => (
              <Button
                key={markOption.key}
                size="tiny"
                active={markOption.key === box.lineStyle}
                className="wb-icon-button only-icon"
                onClick={() => {
                  updateBox({lineStyle: markOption.key});
                }}>
                <LegacyWBIcon name={markOption.icon} />
              </Button>
            ))}
          </Button.Group>
        }
      />
    );
  },
  {id: 'ControlsBoxStyle'}
);

export const ControlsBox = makeComp<{
  box: Controls.BoxControlState;
  updateBox: (newBox: Partial<Controls.BoxControlState>) => void;
}>(
  ({box, updateBox}) => {
    if (box.type !== 'box') {
      throw new Error('Invalid box control.');
    }
    return <ControlsBoxStyle box={box} updateBox={updateBox} />;
  },
  {id: 'ControlsBox'}
);
