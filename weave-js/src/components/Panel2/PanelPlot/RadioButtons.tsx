import {LegacyWBIcon} from '@wandb/weave/common/components/elements/LegacyWBIcon';
import * as globals from '@wandb/weave/common/css/globals.styles';
import React, {useMemo} from 'react';
import styled from 'styled-components';

export const BRUSH_MODES = ['zoom' as const, 'select' as const];
export type BrushMode = (typeof BRUSH_MODES)[number];

interface IconWrapperProps {
  isDarkMode: boolean;
  isActive: boolean;
}

const IconWrapper = styled.div<IconWrapperProps>`
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  background-color: ${props =>
    props.isActive
      ? props.isDarkMode
        ? globals.hexToRGB(globals.TEAL, 0.16)
        : globals.hexToRGB(globals.TEAL, 0.1)
      : props.isDarkMode
      ? globals.GRAY_880
      : globals.WHITE};

  &:hover {
    background-color: ${props =>
      props.isDarkMode ? globals.GRAY_840 : globals.GRAY_50};
  }
  cursor: pointer;
`;

interface IconProps {
  isDarkMode: boolean;
  isActive: boolean;
}

const Icon = styled.div<IconProps>`
  width: 18px;
  height: 18px;f
  background-color: ${props =>
    props.isActive
      ? props.isDarkMode
        ? globals.TEAL_LIGHT2
        : globals.TEAL_DARK
      : props.isDarkMode
      ? globals.GRAY_600
      : globals.GRAY_500};
`;

interface IconComponentProps extends IconWrapperProps {
  onClick: () => void;
  name: string;
}

const IconComponent: React.FC<IconComponentProps> = ({
  isDarkMode,
  isActive,
  onClick,
  name,
}) => (
  <IconWrapper isDarkMode={isDarkMode} isActive={isActive} onClick={onClick}>
    <Icon isDarkMode={isDarkMode} isActive={isActive}>
      <LegacyWBIcon name={name} className={`wbic-${name}`} />
    </Icon>
  </IconWrapper>
);

interface GroupProps {
  isDarkMode: boolean;
}

const Group = styled.div<GroupProps>`
  display: flex;
  padding: 4px;
  background-color: ${props =>
    props.isDarkMode ? globals.GRAY_880 : globals.WHITE};
  border: 1px solid
    ${props => (props.isDarkMode ? globals.GRAY_800 : globals.GRAY_350)};
  border-radius: 4px;
`;

interface GroupComponentProps extends GroupProps {
  children: React.ReactNode;
}

const GroupComponent: React.FC<GroupComponentProps> = ({
  children,
  isDarkMode,
}) => <Group isDarkMode={isDarkMode}>{children}</Group>;

export const PanelPlotRadioButtons: React.FC<{
  currentValue: BrushMode;
  setMode: (newMode: BrushMode) => void;
}> = ({currentValue, setMode}) => {
  // const [isDarkMode, setIsDarkMode] = React.useState(false);

  const options = useMemo(
    () => [
      {
        mode: 'zoom' as const,
        iconName: 'icon-zoom-in-tool',
      },
      /*
      {
        mode: 'pan' as const,
        iconName: 'icon-pan-tool',
      },
      */
      {
        mode: 'select' as const,
        iconName: 'icon-select-move-tool',
      },
    ],
    []
  );

  return (
    <GroupComponent isDarkMode={false}>
      {options.map(({iconName}, index) => (
        <IconComponent
          key={iconName}
          isActive={currentValue === options[index].mode}
          isDarkMode={false}
          onClick={() => {
            const brushMode = options[index].mode;
            if (currentValue !== brushMode) {
              console.log('SETTING BRUSH MODE', currentValue, '=>', brushMode);
              setMode(brushMode);
            }
          }}
          name={iconName}
        />
      ))}
    </GroupComponent>
  );
};

export default PanelPlotRadioButtons;
