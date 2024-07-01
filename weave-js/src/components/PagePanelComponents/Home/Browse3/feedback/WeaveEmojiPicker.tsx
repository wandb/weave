/**
 * Custom wrapper of emoji-picker-react to detect when we are switching to the full picker.
 */

import EmojiPicker, {PickerProps} from 'emoji-picker-react';
import React, {useEffect, useRef} from 'react';

type Props = PickerProps & {
  onPlusButtonClick: () => void;
};

export const WeaveEmojiPicker = ({onPlusButtonClick, ...props}: Props) => {
  const pickerRef = useRef(null);

  useEffect(() => {
    let btn: Element | null = null;
    if (pickerRef.current) {
      const el = pickerRef.current as HTMLElement;
      btn = el.querySelector('[title="Show all Emojis"]');
      if (btn) {
        btn.addEventListener('click', onPlusButtonClick);
      }
    }
    return () => {
      if (btn) {
        btn.removeEventListener('click', onPlusButtonClick);
      }
    };
  }, [onPlusButtonClick]);

  return (
    <div ref={pickerRef}>
      <EmojiPicker {...props} />
    </div>
  );
};
