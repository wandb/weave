import {WBPopup, WBPopupDirection} from '@wandb/ui';
import {disableBodyScroll, enableBodyScroll} from 'body-scroll-lock';
import React, {useCallback} from 'react';
import ReactDOM from 'react-dom';

import PointyTriangle, {PointyTriangleDirection} from './PointyTriangle';
import * as S from './WBAnchoredPopup.styles';

function getScrollParent(node: Element | null): Element | null {
  if (node == null) {
    return null;
  }

  const overflowY = window.getComputedStyle(node).overflowY;
  const isScrollable = overflowY !== 'visible' && overflowY !== 'hidden';
  if (isScrollable && node.scrollHeight > node.clientHeight) {
    return node;
  } else {
    return getScrollParent(node.parentElement);
  }
}

export type OnParentScrollOption = 'follow' | 'disable' | (() => void);

export interface WBAnchoredPopupProps {
  className?: string;
  direction?: WBPopupDirection;
  triangleColor?: string;
  triangleSize?: number;
  anchorElement: Element | null;
  maxHeight?: number;
  children: React.ReactNode;
  onParentScroll?: OnParentScrollOption;
  scrollerRef?: React.Ref<HTMLDivElement>;
  onScroll?: (event: React.UIEvent<HTMLDivElement, UIEvent>) => void;
}

export const WBAnchoredPopup = React.forwardRef<
  HTMLDivElement,
  WBAnchoredPopupProps
>(
  (
    {
      className,
      direction = 'bottom right',
      triangleColor,
      triangleSize = 4,
      anchorElement,
      children,
      maxHeight,
      onParentScroll = 'follow',
      scrollerRef,
      onScroll,
    },
    ref
  ) => {
    const [rect, setRect] = React.useState<DOMRect | undefined>();
    const [scrollerElement, setScrollerElement] =
      React.useState<HTMLElement | null>(null);

    const updateRect = useCallback(() => {
      if (anchorElement) {
        setRect(anchorElement.getBoundingClientRect());
      }
      const scrollParent = getScrollParent(anchorElement);
      function handleParentScroll() {
        if (typeof onParentScroll === 'function') {
          onParentScroll();
        }
        if (anchorElement && onParentScroll === 'follow') {
          setRect(anchorElement.getBoundingClientRect());
        }
      }
      if (scrollParent) {
        scrollParent.addEventListener('scroll', handleParentScroll);
      }
      document.addEventListener('scroll', handleParentScroll);
      return () => {
        if (scrollParent) {
          scrollParent.removeEventListener('scroll', handleParentScroll);
        }
        document.removeEventListener('scroll', handleParentScroll);
      };
    }, [anchorElement, onParentScroll]);
    React.useEffect(updateRect, [updateRect]);
    React.useEffect(() => {
      if (anchorElement) {
        // any movement of the anchor element should trigger a repositioning
        // of the popup
        const observer = new IntersectionObserver(updateRect);
        observer.observe(anchorElement);
        return () => observer.unobserve(anchorElement);
      }

      return;
    }, [anchorElement, updateRect]);

    React.useEffect(() => {
      if (onParentScroll === 'disable') {
        if (scrollerElement) {
          disableBodyScroll(scrollerElement, {reserveScrollBarGap: true});
          return () => {
            enableBodyScroll(scrollerElement);
          };
        }
      }
      return;
    }, [onParentScroll, scrollerElement]);

    let popupX = 0;
    let popupY = 0;
    let triangleX = 0;
    let triangleY = 0;

    if (rect != null) {
      const [verticalDirection, horizontalDirection] = direction.split(' ');
      switch (verticalDirection) {
        case 'top':
          popupY = rect.top - triangleSize;
          triangleY = rect.top;
          break;
        case 'center':
          popupY = rect.top + rect.height / 2;
          triangleY = rect.top + rect.height / 2;
          break;
        case 'bottom':
          popupY = rect.bottom + triangleSize;
          triangleY = rect.bottom;
          break;
      }

      switch (horizontalDirection) {
        case 'left':
          if (verticalDirection === 'center') {
            popupX = rect.left - triangleSize;
            triangleX = rect.left;
          } else {
            popupX = rect.left + rect.width;
            triangleX = rect.left + rect.width / 2;
          }
          break;
        case 'center':
          popupX = rect.left + rect.width / 2;
          triangleX = rect.left + rect.width / 2;
          break;
        case 'right':
          if (verticalDirection === 'center') {
            popupX = rect.right + triangleSize;
            triangleX = rect.right;
          } else {
            popupX = rect.left;
            triangleX = rect.left + rect.width / 2;
          }
          break;
      }
    }

    const pointyTriangleDirection = React.useMemo(() => {
      for (const dir of ['top', 'bottom', 'left', 'right']) {
        if (direction.indexOf(dir) !== -1) {
          return dir as PointyTriangleDirection;
        }
      }
      return 'bottom';
    }, [direction]);

    const scrollerCallbackRef = React.useCallback(
      (node: HTMLDivElement | null) => {
        if (scrollerRef) {
          if (typeof scrollerRef === 'function') {
            scrollerRef(node);
          } else {
            (scrollerRef as any).current = node;
          }
        }
        setScrollerElement(node);
      },
      [scrollerRef]
    );

    return ReactDOM.createPortal(
      <>
        <S.Wrapper>
          {triangleSize > 0 && (
            <PointyTriangle
              x={triangleX}
              y={triangleY}
              size={triangleSize}
              direction={pointyTriangleDirection}
              color={triangleColor}
              noPortal
            />
          )}
          <WBPopup
            className={className}
            ref={ref}
            scrollerRef={scrollerCallbackRef}
            x={popupX}
            y={popupY}
            maxHeight={maxHeight}
            direction={direction}
            noPortal
            onScroll={onScroll}>
            {children}
          </WBPopup>
        </S.Wrapper>
      </>,
      document.body
    );
  }
);
WBAnchoredPopup.displayName = 'WBAnchoredPopup';
