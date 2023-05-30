// Copied from app/src/util/browser
import {detect} from 'detect-browser';

const browser = detect();

export const isFirefox = browser?.name === 'firefox';
export const isSafari = browser?.name === 'safari';

// End browser

// Copied from app/src/util/animation

export function skipTransition(element: HTMLElement, disableDuration = 0) {
  const original = element.style.transition;
  element.style.transition = 'none';
  window.setTimeout(() => {
    element.style.transition = original;
  }, disableDuration);
}

// End copied from animation
