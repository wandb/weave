import {detect} from 'detect-browser';

const browser = detect();

export const isFirefox = browser?.name === 'firefox';
export const isSafari = browser?.name === 'safari';

// navigator.platform is deprecated, so fallback to navigator.userAgent
export const isMac =
  navigator.platform?.startsWith('Mac') ?? navigator.userAgent.includes('Mac');
