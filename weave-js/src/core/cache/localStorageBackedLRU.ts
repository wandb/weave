import {isQuotaExceededError, safeLocalStorage} from '../util/localStorage';

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

  public set(key: string, value: T): void {
    setTimeout(() => this.setDirect(key, value), 1);
  }

  public get(key: string): T | null {
    const valStr = this.prefixedLocalStorageGetItem(key);
    if (!valStr) {
      return null;
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
    return this.prefixedLocalStorageGetItem(key) !== null;
  }

  public reset(): void {
    this.scanIndex = 0;
    while (this.removeLeastRecentlyUsed()) {
      // Keep removing until we can't anymore
    }
    this.scanIndex = 0;
  }
  private setDirect(key: string, value: T): void {
    this.del(key);
    const valStr = JSON.stringify(value);
    const size = valStr.length;
    if (size > this.maxBytesPerEntry) {
      return;
    }

    while (true) {
      try {
        this.prefixedLocalStorageSetItem(key, valStr);
        break;
      } catch (e) {
        if (isQuotaExceededError(e)) {
          const removed = this.removeLeastRecentlyUsed();
          // Try to free up some space
          if (!removed) {
            console.error(
              'Unable to save to localStorage. Memory limit exceeded, even after freeing up space.'
            );
            break;
          }
        } else {
          console.error('Unexpected error saving to localStorage', e);
          break;
        }
      }
    }
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
