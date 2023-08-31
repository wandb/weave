import _ from 'lodash';

import {isTruthy, Struct} from './types';

export const getCookie = (cookieName: string): string => {
  const cookieStrs = getCookieStrs();
  for (const cookieStr of cookieStrs) {
    const keyVal = cookieStrToKeyVal(cookieStr, false);
    if (keyVal == null) {
      continue;
    }
    if (keyVal[0] === cookieName) {
      return keyVal[1];
    }
  }
  return '';
};

export const getCookieBool = (key: string): boolean => {
  const cookieStrs = getCookieStrs();
  for (const cookieStr of cookieStrs) {
    const keyVal = cookieStrToKeyVal(cookieStr);
    if (keyVal == null) {
      continue;
    }
    if (keyVal[0] === key) {
      return true;
    }
  }
  return false;
};

export const getAllCookies = () => {
  const cookieStrs = getCookieStrs();
  const data: {[key: string]: string | string[]} = {};
  for (const cookieStr of cookieStrs) {
    const keyVal = cookieStrToKeyVal(cookieStr);
    if (keyVal == null) {
      continue;
    }
    const [key, val] = keyVal;
    if (data[key] == null) {
      data[key] = val;
    } else if (!_.isArray(data[key])) {
      data[key] = [data[key] as string, val];
    } else {
      (data[key] as string[]).push(val);
    }
  }
  return data;
};

const getCookieStrs = () => {
  const str = decodeURIComponent(document.cookie);
  return str
    .split(';')
    .filter(s => s !== '')
    .map(s => s.trim());
};

const cookieStrToKeyVal = (cookieStr: string, warn: boolean = true) => {
  const sepI = cookieStr.indexOf('=');
  if (sepI < 1) {
    if (warn) {
      console.warn('Invalid cookie', cookieStr);
    }
    return null;
  }
  const key = cookieStr.slice(0, sepI);
  const val = cookieStr.slice(sepI + 1);
  return [key, val] as const;
};

const {host} = window.location;
const isLocalhost = host.includes('localhost');
const hostWithoutSubdomain = host
  .replace('app.', '')
  .replace('beta.wandb', 'wandb');
const unsetExpiresValue = 'Thu, 01 Jan 1970 00:00:00 UTC';

let prodCookieAttrs = `domain=${hostWithoutSubdomain}; SameSite=strict; path=/; secure`;
let devCookieAttrs = `domain=${host}; SameSite=strict; path=/`;
if (isLocalhost) {
  prodCookieAttrs = 'path=/';
  devCookieAttrs = 'path=/';
}

export function setCookie(key: string, value: string, expires?: Date): void {
  setDocumentCookie({
    key,
    value,
    expires: expires != null ? expires.toUTCString() : undefined,
  });
}

export function unsetCookie(key: string): void {
  setDocumentCookie({
    key,
    value: ``,
    expires: unsetExpiresValue,
  });
}

type SetDocumentCookieParams = {
  key: string;
  value: string;
  expires?: string;
  maxAgeSeconds?: number;
};

function setDocumentCookie({
  key,
  value,
  expires,
  maxAgeSeconds,
}: SetDocumentCookieParams): void {
  if (!key) {
    return;
  }

  const keyValStr = `${key}=${value}`;
  const expiryStr = getExpiryStr();

  for (const attrsStr of [prodCookieAttrs, devCookieAttrs]) {
    document.cookie = [keyValStr, expiryStr, attrsStr]
      .filter(isTruthy)
      .join('; ');
  }

  function getExpiryStr(): string {
    if (expires != null) {
      return `expires=${expires}`;
    }
    if (maxAgeSeconds != null) {
      return `max-age=${maxAgeSeconds}`;
    }
    return ``;
  }
}

// See host/src/cookies.ts
const FIREBASE_COOKIE_KEY = `__session`;

export function getFirebaseCookie(key: string): string | null {
  return getFirebaseCookiesObject()[key] ?? null;
}

function getFirebaseCookiesObject(): Struct<string> {
  try {
    const firebaseCookiesJSON = getCookie(FIREBASE_COOKIE_KEY);
    if (!firebaseCookiesJSON) {
      return {};
    }
    return JSON.parse(firebaseCookiesJSON);
  } catch (err) {
    console.error(`Error getting firebase cookies: ${err}`);
    return {};
  }
}
