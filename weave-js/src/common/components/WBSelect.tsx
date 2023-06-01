import {WBIcon} from '@wandb/ui';
import {WBPopup} from '@wandb/ui';
import React from 'react';

import {useOnMouseDownOutside} from '../util/dom';
import {
  getOptionDisplayName,
  WBMenu,
  WBMenuOnSelectHandler,
  WBMenuOption,
  WBMenuTheme,
} from './WBMenu';
import * as S from './WBSelect.styles';

export type WBSelectProps = {
  className?: string;
  popupStyle?: React.CSSProperties;
  value: string | number;
  displayedValue?: string | number;
  options: WBMenuOption[];
  typeable?: boolean;
  menuWidth?: number;
  menuTheme?: WBMenuTheme;
  menuBackgroundColor?: string;
  menuFontSize?: number;
  menuLineHeight?: number;
  autoMenuWidth?: boolean;
  disabled?: boolean;
  onSelect: WBMenuOnSelectHandler;
  onChangeHoveredIndex?: (index: number) => void;
  'data-test'?: string;
};

export const WBSelect: React.FC<WBSelectProps> = props => {
  const [rect, setRect] = React.useState<DOMRect | undefined>();
  const [open, setOpen] = React.useState(false);
  const [inputFocused, setInputFocused] = React.useState(false);
  const [defaultWidth, setDefaultWidth] = React.useState(0);
  const [selectedElement, setSelectedElement] =
    React.useState<HTMLDivElement | null>(null);

  const [openerEl, setOpenerEl] = React.useState<HTMLDivElement | null>(null);
  const [popupEl, setPopupEl] = React.useState<HTMLDivElement | null>(null);
  const onClickOutside = React.useCallback(() => {
    setOpen(false);
  }, []);
  const mousedownExcludedEls = React.useMemo(
    () => [openerEl, popupEl],
    [openerEl, popupEl]
  );
  useOnMouseDownOutside(mousedownExcludedEls, onClickOutside);

  let menuX = 0;
  let menuY = 0;
  if (rect != null) {
    menuX = rect.left;
    menuY = rect.top + rect.height / 2;
  }

  const selectedOption = props.options.find(opt => opt.value === props.value);
  const displayedValue =
    props.displayedValue ??
    (selectedOption == null
      ? props.value
      : getOptionDisplayName(selectedOption));

  return (
    <>
      {props.typeable ? (
        <S.TypeableWrapper
          data-test={props['data-test']}
          ref={node => {
            if (node) {
              setDefaultWidth(node.offsetWidth);
            }
          }}
          open={open && !props.disabled}
          inputFocused={inputFocused && !props.disabled}
          className={props.className}
          onMouseDown={e => {
            setRect(e.currentTarget.getBoundingClientRect());
          }}>
          <S.StyledAutoCompletingInput
            options={props.options.map(opt => getOptionDisplayName(opt))}
            value={selectedOption?.name}
            disabled={props.disabled}
            onSelect={val => {
              const selected = props.options.find(
                opt => getOptionDisplayName(opt) === val
              );
              if (selected != null) {
                props.onSelect(selected.value, {option: selected});
              }
            }}
            onFocus={() => setInputFocused(true)}
            onBlur={() => setInputFocused(false)}
          />
          <S.CaretWrapper
            ref={node => setOpenerEl(node)}
            onMouseDown={() => setOpen(o => !o)}>
            <WBIcon name="next" />
          </S.CaretWrapper>
        </S.TypeableWrapper>
      ) : (
        <S.BasicWrapper
          data-test={props['data-test']}
          ref={node => {
            setOpenerEl(node);
            if (node) {
              setDefaultWidth(node.offsetWidth);
            }
          }}
          tabIndex={props.disabled ? undefined : 0}
          // onMouseDown={e => e.preventDefault()}
          // onFocus={e => {
          //   setRect(e.currentTarget.getBoundingClientRect());
          //   setOpen(true);
          // }}
          // onBlur={() => {
          //   setOpen(false);
          // }}
          onKeyDown={e => {
            if (e.keyCode === 38 || e.keyCode === 40 /* up or down */) {
              if (!open) {
                setRect(e.currentTarget.getBoundingClientRect());
                setOpen(true);
              }
            }
          }}
          open={open && !props.disabled}
          onMouseDown={e => {
            setRect(e.currentTarget.getBoundingClientRect());
            setOpen(o => !o);
          }}
          className={props.className}>
          <S.DisplayedValue>{displayedValue}</S.DisplayedValue>
          <S.DropdownArrow />
        </S.BasicWrapper>
      )}
      {open && !props.disabled && (
        <WBPopup
          style={props.popupStyle}
          x={menuX}
          y={menuY}
          direction={'center right'}
          ref={node => setPopupEl(node)}
          elementToPosition={selectedElement}>
          <WBMenu
            theme={props.menuTheme}
            backgroundColor={props.menuBackgroundColor}
            fontSize={props.menuFontSize}
            lineHeight={props.menuLineHeight}
            width={
              props.autoMenuWidth ? undefined : props.menuWidth ?? defaultWidth
            }
            selected={props.value}
            options={props.options}
            onSelect={(val, extra) => {
              setOpen(false);
              props.onSelect(val, extra);
            }}
            onEsc={() => {
              setOpen(false);
            }}
            selectedRef={node => setSelectedElement(node)}
          />
        </WBPopup>
      )}
    </>
  );
};
