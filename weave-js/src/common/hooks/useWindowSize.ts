import _ from 'lodash';
import {useLayoutEffect, useState} from 'react';

import {LARGE_BREAKPOINT, MEDIUM_BREAKPOINT} from '../css/breakpoints.styles';

export type ResponsiveSize = 'small' | 'medium' | 'large';

export interface WindowSize {
  width: number;
  height: number;
  responsiveSize: ResponsiveSize;
}

const getResponsiveSize = (width: number): ResponsiveSize => {
  if (width < MEDIUM_BREAKPOINT) {
    return 'small';
  }
  if (width < LARGE_BREAKPOINT) {
    return 'medium';
  }
  return 'large';
};

const windowSize: WindowSize = {
  width: window.innerWidth,
  height: window.innerHeight,
  responsiveSize: getResponsiveSize(window.innerWidth),
};

function refreshWindowSize() {
  windowSize.width = window.innerWidth;
  windowSize.height = window.innerHeight;
  windowSize.responsiveSize = getResponsiveSize(window.innerWidth);
}

const componentsWatchingWindowSize: Set<() => void> = new Set();

function renderWatchingComponents() {
  for (const renderComponent of componentsWatchingWindowSize) {
    renderComponent();
  }
}

const initWindowResizeListener = _.once(() => {
  window.addEventListener('resize', () => {
    refreshWindowSize(); // cheap. ok to run on every tick.
    renderWatchingComponents(); // expensive. ensure all renders are throttled.
  });
  refreshWindowSize();
});

export function useRenderOnWindowResize(throttleMS = 200): void {
  initWindowResizeListener();
  const [, forceRender] = useState({});
  useLayoutEffect(() => {
    const throttledRender = _.throttle(() => forceRender({}), throttleMS);
    componentsWatchingWindowSize.add(throttledRender);
    return () => {
      componentsWatchingWindowSize.delete(throttledRender);
    };
    // eslint-disable-next-line
  }, []);
}

export function useWindowSize(throttleMS?: number): WindowSize {
  useRenderOnWindowResize(throttleMS);
  return windowSize;
}
