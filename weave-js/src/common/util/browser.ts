import {detect} from 'detect-browser';

const browser = detect();

export const isFirefox = browser?.name === 'firefox';
export const isSafari = browser?.name === 'safari';

// navigator.platform is deprecated, so fallback to navigator.userAgent
export const isMac = () => {
  const platform = navigator.platform || '';
  const userAgent = navigator.userAgent || '';
  const appVersion = navigator.appVersion || '';
  const checkString = (str: string) => /Mac|iPhone|iPod|iPad/i.test(str);
  return (
    checkString(platform) || checkString(userAgent) || checkString(appVersion)
  );
};
