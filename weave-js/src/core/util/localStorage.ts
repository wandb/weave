// These two declarations are required until we deprecate weave typescript
// service. We don't consider "dom" as part of the compileOptions.lib
// which is correct, because it is a node service. However, this file
// safely handles when window / Storage is not available. Therefore, this
// type declaration is a safe workaround for cross-service compatibility.

declare var window: any;
declare type Storage = any;

// you can simulate this in Firefox by going to about:config in the nav bar and then
// setting dom.storage.enabled to false.
type MaybeStorage = Storage | null;

export function detectStorage(storage: MaybeStorage) {
  if (!storage) {
    return false;
  }

  try {
    storage.setItem('feature-detect-storage', '1');
    storage.removeItem('feature-detect-storage');
    return true;
  } catch (e) {
    return false;
  }
}

export const clear = (storage: MaybeStorage) => () => {
  try {
    // @ts-ignore
    storage.clear();
  } catch (e) {
    console.error(
      'Error attempting to clear storage. Storage may not be available in this environment.'
    );
  }
};

export const getItem = (storage: MaybeStorage) => (key: string) => {
  try {
    // @ts-ignore
    return storage.getItem(key);
  } catch (e) {
    console.error(
      `Error attempting to retrieve item: "${key}" from storage. Storage may not be available in this environment.`
    );
    return null;
  }
};

export const removeItem = (storage: MaybeStorage) => (key: string) => {
  try {
    // @ts-ignore
    storage.removeItem(key);
  } catch (e) {
    console.error(
      `Error attempting to remove item: "${key}" from storage. Storage may not be available in this environment.`
    );
  }
};

export const setItem =
  (storage: MaybeStorage) => (key: string, value: string) => {
    try {
      // @ts-ignore
      storage.setItem(key, value);
    } catch (e) {
      if (isQuotaExceededError(e)) {
        throw e;
      }
      console.error(
        `Error attempting to set item: "${key}" from storage. Storage may not be available in this environment.`
      );
    }
  };

export function isQuotaExceededError(e: any): boolean {
  let quotaExceeded = false;
  if (e) {
    if (e.code) {
      switch (e.code) {
        case 22:
          // Chrome and Safari
          quotaExceeded = true;
          break;
        case 1014:
          // Firefox
          if (e.name === 'NS_ERROR_DOM_QUOTA_REACHED') {
            quotaExceeded = true;
          }
          break;
      }
    } else if (e.number === -2147024882) {
      // Internet Explorer 8
      quotaExceeded = true;
    }
  }
  return quotaExceeded;
}

export const keyAt = (storage: MaybeStorage) => (index: number) => {
  try {
    // @ts-ignore
    return storage.key(index);
  } catch (e) {
    console.error(
      `Error attempting to get key: "${index}" from storage. Storage may not be available in this environment.`
    );
  }
  return null;
};

export const length = (storage: MaybeStorage) => () => {
  try {
    // @ts-ignore
    return storage.length;
  } catch (e) {
    console.error(
      `Error attempting to get length from storage. Storage may not be available in this environment.`
    );
  }
  return 0;
};

export function getStorage(storage: Storage | null) {
  return {
    clear: clear(storage),
    isAvailable: detectStorage(storage),
    getItem: getItem(storage),
    removeItem: removeItem(storage),
    setItem: setItem(storage),
    key: keyAt(storage), // maintain compatibility with localStorage API
    length: length(storage),
  };
}
/**
 * Safe wrappers around local storage
 * LocalStorage will fail in certain environments (like private mode) and those
 * failed operations should no-op instead of throwing errors.
 *
 * These functions work identically to the standard localStorage API.
 * ```
 * import localStorage from './localStorage';
 * localStorage.setItem('foo', 'bar');
 * localStorage.getItem('foo');
 * ```
 */
let windowLocalStorage: Storage | null = null;
let windowSessionStorage: Storage | null = null;
try {
  // eslint-disable-next-line no-restricted-properties
  windowLocalStorage = window?.localStorage;
  // eslint-disable-next-line no-restricted-properties
  windowSessionStorage = window?.sessionStorage;
} catch (e) {
  console.error(
    'Error attempting to access window.localStorage. Storage may not be available in this environment.'
  );
}
export const safeLocalStorage = getStorage(windowLocalStorage);
export const safeSessionStorage = getStorage(windowSessionStorage);
