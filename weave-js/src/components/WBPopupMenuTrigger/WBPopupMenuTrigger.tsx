import React from 'react';

import {
  WBMenu,
  WBMenuOnSelectHandler,
  WBMenuOption,
  WBMenuTheme,
} from '../../common/components/WBMenu';
import {WBPopupDirection} from '../WBPopup';
import {TriggerGenerator, WBPopupTrigger} from '../WBPopupTrigger';

export interface WBPopupMenuTriggerProps {
  options: WBMenuOption[];
  selected?: number | string;
  direction?: WBPopupDirection;
  menuWidth?: number;
  menuBackgroundColor?: string;
  theme?: WBMenuTheme;
  children: TriggerGenerator;
  onSelect?: WBMenuOnSelectHandler;
}

export const WBPopupMenuTrigger: React.FC<WBPopupMenuTriggerProps> = props => {
  return (
    <WBPopupTrigger
      direction={props.direction}
      triangleColor={props.menuBackgroundColor}
      popupContent={({close}) => (
        <WBMenu
          // classname just used to identify in testing
          className="wb-menu-trigger-content"
          width={props.menuWidth}
          options={props.options}
          selected={props.selected}
          onSelect={(val, extra) => {
            close();
            props.onSelect?.(val, extra);
          }}
          onEsc={close}
          backgroundColor={props.menuBackgroundColor}
          theme={props.theme}
        />
      )}>
      {props.children}
    </WBPopupTrigger>
  );
};
