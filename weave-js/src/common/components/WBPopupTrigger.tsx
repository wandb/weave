import React from 'react';

import {useOnMouseDownOutside} from '../util/dom';
import {WBAnchoredPopup} from './WBAnchoredPopup';
import {WBPopupDirection} from './WBPopup';

export type TriggerGenerator = (props: {
  anchorRef: (node: Element | null) => void;
  open: boolean;
  setOpen: React.Dispatch<React.SetStateAction<boolean>>;
}) => React.ReactNode;

export interface WBPopupTriggerProps {
  direction?: WBPopupDirection;
  triangleColor?: string;
  onParentScroll?: 'follow' | 'disable' | (() => void);
  children: TriggerGenerator;
  popupContent(props: {close: () => void}): React.ReactNode;
}

export const WBPopupTrigger: React.FC<WBPopupTriggerProps> = props => {
  const [open, setOpen] = React.useState(false);
  const [popupEl, setPopupEl] = React.useState<HTMLElement | null>(null);
  const [anchorElement, setAnchorElement] = React.useState<Element | null>(
    null
  );

  const onMouseDownOutside = React.useCallback(() => setOpen(false), []);
  useOnMouseDownOutside([popupEl, anchorElement], onMouseDownOutside);

  const callbackRef = React.useCallback((node: Element | null) => {
    setAnchorElement(node);
  }, []);

  const close = React.useCallback(() => {
    setOpen(false);
  }, []);

  const popupCallbackRef = React.useCallback((node: HTMLElement | null) => {
    setPopupEl(node);
  }, []);

  return (
    <>
      {props.children({anchorRef: callbackRef, open, setOpen})}
      {open && (
        <WBAnchoredPopup
          ref={popupCallbackRef}
          direction={props.direction}
          triangleColor={props.triangleColor}
          anchorElement={anchorElement}
          onParentScroll={props.onParentScroll}>
          {props.popupContent({close})}
        </WBAnchoredPopup>
      )}
    </>
  );
};
