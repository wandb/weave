import {PopupProps} from 'semantic-ui-react';

///// Block Popup clicks
//
// If you use our WBMenu or other WB* components inside of a semantic Popup,
// clicking on a menu item will dismiss the popup, which is not what you want.
// Put this class on your menu (or any of its ancestors that end up in the
// portal WBMenu creates), and then use withIgnoreBlockClicks as the onClose
// method of the Popup you want to fix.
export const BLOCK_POPUP_CLICKS_CLASSNAME = 'block-popup-clicks';

type PopupOnCloseFn = NonNullable<PopupProps['onClose']>;

export const withIgnoreBlockedClicks = (fn: PopupOnCloseFn): PopupOnCloseFn => {
  const wrapped: PopupOnCloseFn = (event, data) => {
    if (
      event.target != null &&
      (event.target as any).closest('.block-popup-clicks') != null
    ) {
      return;
    }
    return fn(event, data);
  };
  return wrapped;
};
