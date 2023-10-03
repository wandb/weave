import {isQuotaExceededError, safeLocalStorage} from '../util/localStorage';

const UNDEFINED_VALUE = '__undefined__';

export class LocalStorageBackedLRU<T extends {} = {}> {
  private scanIndex: number;

  constructor(
    private readonly maxBytesPerEntry: number = 1e6,
    private readonly prefix: string = 'wv_'
  ) {
    // LocalStorage is limited to 5MB, so we'll use 1MB as our default for the maxBytesPerEntry
    this.maxBytesPerEntry = maxBytesPerEntry;
    this.scanIndex = 0;
  }

  public setAsync(key: string, value: T): Promise<boolean> {
    return new Promise(resolve => {
      resolve(this.set(key, value));
    });
  }

  public set(key: string, value: T): boolean {
    this.del(key);
    const valStr =
      value === undefined ? UNDEFINED_VALUE : JSON.stringify(value);
    const size = valStr.length;
    if (size > this.maxBytesPerEntry) {
      return false;
    }

    while (true) {
      try {
        this.prefixedLocalStorageSetItem(key, valStr);
        return true;
      } catch (e) {
        if (isQuotaExceededError(e)) {
          const removed = this.removeLeastRecentlyUsed();
          // Try to free up some space
          if (!removed) {
            console.error(
              'Unable to save to localStorage. Memory limit exceeded, even after freeing up space.'
            );
            return false;
          }
        } else {
          console.error('Unexpected error saving to localStorage', e);
          return false;
        }
      }
    }
  }

  public get(key: string): T | null | undefined {
    const valStr = this.prefixedLocalStorageGetItem(key);
    if (!valStr) {
      return null;
    }
    if (valStr === UNDEFINED_VALUE) {
      return undefined as any;
    }
    const value = JSON.parse(valStr);
    this.del(key);
    this.set(key, value);
    return value;
  }

  public del(key: string): void {
    const itemStr = this.prefixedLocalStorageGetItem(key);
    if (itemStr) {
      this.prefixedLocalStorageRemoveItem(key);
    }
  }

  public has(key: string): boolean {
    return this.prefixedLocalStorageGetItem(key) != null;
  }

  public reset(): void {
    this.scanIndex = 0;
    while (this.removeLeastRecentlyUsed()) {
      // Keep removing until we can't anymore
    }
    this.scanIndex = 0;
  }

  private removeLeastRecentlyUsed(): boolean {
    while (this.scanIndex < safeLocalStorage.length()) {
      const prefixedKey = safeLocalStorage.key(this.scanIndex);
      if (prefixedKey.startsWith(this.prefix)) {
        // Only consider keys that start with our prefix
        safeLocalStorage.removeItem(prefixedKey);
        return true;
      }
      this.scanIndex++;
    }
    return false;
  }

  private prefixedLocalStorageSetItem(key: string, value: string): void {
    safeLocalStorage.setItem(this.prefix + key, value);
  }

  private prefixedLocalStorageGetItem(key: string): string | null {
    return safeLocalStorage.getItem(this.prefix + key);
  }

  private prefixedLocalStorageRemoveItem(key: string): void {
    safeLocalStorage.removeItem(this.prefix + key);
  }
}
