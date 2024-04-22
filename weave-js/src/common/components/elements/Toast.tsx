import React, {createElement, FC} from 'react';
import {
  Slide,
  toast as toastify,
  ToastContainer as ToastifyContainer,
  ToastContent,
  ToastOptions,
} from 'react-toastify';

import {LegacyWBIcon} from './LegacyWBIcon';

interface CloseButtonProps {
  closeToast: any;
}

export const ToastContainer: FC = React.memo(() => {
  return (
    <ToastifyContainer
      position={toastify.POSITION.TOP_RIGHT}
      hideProgressBar={true}
      className="toast-container"
      toastClassName="toast"
      transition={Slide}
      closeButton={createElement(({closeToast}: CloseButtonProps) => (
        <LegacyWBIcon
          name="close"
          onClick={closeToast}
          className="close-toast"
        />
      ))}
    />
  );
});

export function toast(text: ToastContent, options?: ToastOptions): void {
  toastify(text, options);
}
