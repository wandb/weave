import {LegacyWBIcon} from '@wandb/weave/common/components/elements/LegacyWBIcon';
import {LineStyle} from '@wandb/weave/common/components/MediaCard';
import React from 'react';
import {Button, Popup} from 'semantic-ui-react';

import * as Controls from './controlsImage';

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

type ControlsBoxStyleProps = {
  box: Controls.BoxControlState;
  updateBox: (newBox: Partial<Controls.BoxControlState>) => void;
};

export const ControlsBoxStyle: React.FC<ControlsBoxStyleProps> = ({
  box,
  updateBox,
}) => {
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
};

type ControlsBoxProps = {
  box: Controls.BoxControlState;
  updateBox: (newBox: Partial<Controls.BoxControlState>) => void;
};

export const ControlsBox: React.FC<ControlsBoxProps> = ({box, updateBox}) => {
  if (box.type !== 'box') {
    throw new Error('Invalid box control.');
  }
  return <ControlsBoxStyle box={box} updateBox={updateBox} />;
};
