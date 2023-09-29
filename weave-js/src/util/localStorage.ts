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
      console.error(
        `Error attempting to set item: "${key}" from storage. Storage may not be available in this environment.`
      );
    }
  };

export const key =
  (storage: MaybeStorage) => (index: number) => {
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

export const length =
  (storage: MaybeStorage) => () => {
    try {
      // @ts-ignore
      return storage.length
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
    key: key(storage),
    length: length(storage),
  };
}
/**
 * Safe wrappers around local storage
 * LocalStorage will fail in certain environments (like private mode) and those
 * failed operations should no-op instead of throwing errors.
 *
 * These functions work indentically to the standard localStorage API.
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
