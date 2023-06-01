import React, {ReactNode, useCallback, useRef, useState} from 'react';

import * as S from './lct.style';

type TipOverlayResult = {
  tipOverlay: ReactNode;
  showTipOverlay: () => void;
};

export function useTipOverlay(): TipOverlayResult {
  const [tipOverlayShown, setTipOverlayShown] = useState(false);

  const hideTipOverlayTimeoutIDRef = useRef<number | null>(null);

  const showTipOverlay = useCallback(() => {
    setTipOverlayShown(true);
    const timeoutID = (hideTipOverlayTimeoutIDRef.current = window.setTimeout(
      () => {
        if (hideTipOverlayTimeoutIDRef.current === timeoutID) {
          setTipOverlayShown(false);
        }
      },
      1000
    ));
  }, []);

  return {
    tipOverlay: (
      <S.TipOverlay visible={tipOverlayShown}>
        Click and drag to pan
      </S.TipOverlay>
    ),
    showTipOverlay,
  };
}
