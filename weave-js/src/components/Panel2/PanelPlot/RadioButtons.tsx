import * as Color from '@wandb/weave/common/css/color.styles';
import React, {useMemo} from 'react';
import styled from 'styled-components';

import {Button} from '../../Button';
import {IconName} from '../../Icon';

export const BRUSH_MODES = ['zoom' as const, 'select' as const];
export type BrushMode = (typeof BRUSH_MODES)[number];

const Group = styled.div`
  display: flex;
  padding: 4px;
  line-height: 0;
  background-color: ${Color.WHITE};
  border: 1px solid ${Color.MOON_300};
  border-radius: 4px;
`;
Group.displayName = 'S.Group';

export const PanelPlotRadioButtons: React.FC<{
  currentValue: BrushMode;
  setMode: (newMode: BrushMode) => void;
}> = ({currentValue, setMode}) => {
  const options = useMemo(
    () => [
      {
        mode: 'zoom' as const,
        iconName: 'zoom-in-tool' as IconName,
        tooltip: 'Zoom',
      },
      /*
      {
        mode: 'pan' as const,
        iconName: 'icon-pan-tool',
      },
      */
      {
        mode: 'select' as const,
        iconName: 'select-move-tool' as IconName,
        tooltip: 'Select',
      },
    ],
    []
  );

  return (
    <Group>
      {options.map(({iconName, tooltip}, index) => (
        <Button
          key={iconName}
          icon={iconName}
          size="small"
          variant={currentValue === options[index].mode ? 'secondary' : 'ghost'}
          tooltip={tooltip}
          onClick={() => {
            const brushMode = options[index].mode;
            if (currentValue !== brushMode) {
              setMode(brushMode);
            }
          }}
        />
      ))}
    </Group>
  );
};

export default PanelPlotRadioButtons;
