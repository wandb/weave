import {throttle} from 'lodash';
import React from 'react';

/**
 * Hook that alerts mousedowns outside of the passed ref.
 */
export function useOnMouseDownOutside(
  elements: Array<Element | null>,
  handler: (e: MouseEvent) => void
) {
  React.useEffect(() => {
    function handleMouseDownOutside(e: MouseEvent) {
      if (e.target instanceof Element) {
        for (const el of elements) {
          if (el && el.contains(e.target)) {
            return;
          }
        }
        handler(e);
      }
    }

    document.addEventListener('mousedown', handleMouseDownOutside);
    return () => {
      document.removeEventListener('mousedown', handleMouseDownOutside);
    };
  }, [elements, handler]);
}

/**
 * Hook that alerts mousedowns inside of the passed ref.
 * There's probably a better alternative to this.
 */
export function useOnMouseDownInside(
  el: HTMLElement | null,
  handler: (e: MouseEvent) => void
) {
  React.useEffect(() => {
    if (!el) {
      return;
    }

    el.addEventListener('mousedown', handler);
    return () => {
      el.removeEventListener('mousedown', handler);
    };
  }, [el, handler]);
}

export function getLeafNode(n: Node): Node {
  while (n.childNodes.length > 0) {
    n = n.childNodes[0];
  }
  return n;
}

/**
 * Function that allows automatic scrolling when
 * dragging past page size.
 */
const scrollBy = throttle((px: number) => {
  window.scrollBy({top: px, behavior: 'auto'});
}, 30);

export const autoScrollWhenDragging = (clientY: number) => {
  if (clientY < 100) {
    scrollBy((clientY - 100) / 5);
  } else if (clientY > window.innerHeight - 100) {
    scrollBy((clientY - (window.innerHeight - 100)) / 5);
  }
};
