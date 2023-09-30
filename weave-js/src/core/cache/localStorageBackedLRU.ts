import {safeLocalStorage} from '../util/localStorage';

export class LocalStorageBackedLRU<T extends {} = {}> {
  public set(key: string, value: T): boolean {
    this.del(key);
    const valStr = JSON.stringify(value);
    let setDone = false;
    let hasError = false;
    while (!setDone && !hasError) {
      try {
        safeLocalStorage.setItem(key, valStr);
        setDone = true;
      } catch (e) {
        if (isQuotaExceededError(e)) {
          // Try to free up some space
          if (safeLocalStorage.length() > 0) {
            this.removeLeastRecentlyUsed();
          } else {
            console.error(
              'Unable to save to localStorage. Memory limit exceeded, even after freeing up space.'
            );
            hasError = true;
          }
        } else {
          console.error('Unexpected error saving to localStorage', e);
          hasError = true;
        }
      }
    }

    return setDone;
  }

  public get(key: string): T | null {
    const valStr = safeLocalStorage.getItem(key);
    if (!valStr) {
      return null;
    }
    const value = JSON.parse(valStr);
    this.del(key);
    this.set(key, value);
    return value;
  }

  public del(key: string): void {
    const itemStr = safeLocalStorage.getItem(key);
    if (itemStr) {
      safeLocalStorage.removeItem(key);
    }
  }

  public has(key: string): boolean {
    return safeLocalStorage.getItem(key) !== null;
  }

  public reset(): void {
    safeLocalStorage.clear();
  }

  private removeLeastRecentlyUsed(): void {
    const key = safeLocalStorage.key(0);
    if (key) {
      this.del(key);
    }
  }
}

function isQuotaExceededError(e: any): boolean {
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
