import React from 'react';

/**
 * Hook to handle scrolling an element into view when a condition is met
 * @param elementRef - Reference to the element to scroll
 * @param shouldScroll - Condition that triggers the scroll
 * @param options - ScrollIntoView options
 */
export const useScrollIntoView = (
  elementRef: React.RefObject<HTMLElement>,
  shouldScroll: boolean,
  instant: boolean = false
) => {
  React.useEffect(() => {
    let mounted = true;
    const doScroll = () => {
      if (mounted && shouldScroll && elementRef.current) {
        elementRef.current.scrollIntoView({
          behavior: instant ? 'instant' : 'smooth',
          block: 'center',
        });
      }
    };

    const timeout = setTimeout(doScroll, 15);
    return () => {
      mounted = false;
      clearTimeout(timeout);
    };
  }, [elementRef, shouldScroll, instant]);
};
