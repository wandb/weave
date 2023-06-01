import {omit} from 'lodash';
import * as React from 'react';
import {memo, useCallback, useMemo, useState} from 'react';
import {
  Dropdown,
  DropdownItemProps,
  Popup,
  StrictPopupProps,
} from 'semantic-ui-react';

import * as globals from '../css/globals.styles';

type DropdownSection = DropdownItemProps[];

export interface PopupDropdownProps extends StrictPopupProps {
  position?: StrictPopupProps['position'];
  options?: DropdownItemProps[];
  sections?: DropdownSection[];
  MenuComponent?: typeof Dropdown.Menu;
  onOpen?: () => void;
  onClose?: () => void;
}

const PopupDropdownComp: React.FC<PopupDropdownProps> = props => {
  const noop = () => {};
  const {
    position,
    className,
    options,
    sections,
    on = `click`,
    MenuComponent = Dropdown.Menu,
    onOpen = noop,
    onClose = noop,
  } = props;

  const [isOpen, setIsOpen] = useState(false);
  const handleOpen = useCallback(() => {
    setIsOpen(true);
    onOpen();
  }, [setIsOpen, onOpen]);
  const handleClose = useCallback(() => {
    setIsOpen(false);
    onClose();
  }, [setIsOpen, onClose]);

  const popperModifiers = useMemo(
    () => ({
      preventOverflow: {enabled: false},
      flip: {enabled: false},
    }),
    []
  );

  const makeDropdownItem = useCallback(
    (opts, i: number) => (
      <Dropdown.Item
        key={i}
        {...opts}
        onClick={e => {
          opts.onClick?.(e);
          handleClose();
        }}
      />
    ),
    [handleClose]
  );

  const content = useMemo(
    () => (
      <div onClick={handleClose}>
        <Dropdown open={true} icon={null}>
          <MenuComponent>
            {options?.map(makeDropdownItem)}
            {sections?.map((sec, i: number) => (
              <React.Fragment key={i}>
                {i > 0 && (
                  <div
                    style={{
                      margin: '8px 16px',
                      height: 1,
                      background: globals.gray400,
                    }}
                  />
                )}
                {sec.map(makeDropdownItem)}
              </React.Fragment>
            ))}
          </MenuComponent>
        </Dropdown>
      </div>
    ),
    [handleClose, makeDropdownItem, options, sections, MenuComponent]
  );

  return (
    <Popup
      basic
      position={position ?? 'bottom left'}
      {...omit(props, 'options')}
      className={'popup-dropdown ' + (className || '')}
      on={on}
      hoverable
      popperModifiers={popperModifiers}
      content={content}
      onOpen={handleOpen}
      open={isOpen}
      onClose={handleClose}
    />
  );
};

export const PopupDropdown = memo(PopupDropdownComp);
