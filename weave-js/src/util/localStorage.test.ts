import {getStorage, safeLocalStorage} from '../core/util/localStorage';

describe('Localstorage w/ error handling', () => {
  describe('feature detect local storage', () => {
    test('true when available', () => {
      // @ts-ignore
      const storage = getStorage({
        setItem: () => {},
        removeItem: () => {},
      });
      expect(storage.isAvailable).toBe(true);
    });
    test('false when unavailable', () => {
      // @ts-ignore
      const storage = getStorage(null);
      expect(storage.isAvailable).toBe(false);
    });
  });

  test('localstorage works', () => {
    safeLocalStorage.setItem('foo', 'bar');
    expect(safeLocalStorage.getItem('foo')).toBe('bar');
    safeLocalStorage.removeItem('foo');
    expect(safeLocalStorage.getItem('foo')).toBe(null);
    safeLocalStorage.setItem('foo1', 'bar');
    safeLocalStorage.setItem('foo2', 'bar');
    safeLocalStorage.clear();
    expect(safeLocalStorage.getItem('foo1')).toBe(null);
    expect(safeLocalStorage.getItem('foo2')).toBe(null);
  });

  test('clear should noop when not available', () => {
    expect(() => {
      safeLocalStorage.clear();
    }).not.toThrow();
  });

  test('getItem should return null when not available', () => {
    expect(safeLocalStorage.getItem('foo')).toBeNull();
  });

  test('removeItem should noop when not available', () => {
    expect(() => {
      safeLocalStorage.removeItem('foo');
    }).not.toThrow();
  });

  test('setItem should noop when not available', () => {
    expect(() => {
      safeLocalStorage.setItem('foo', 'bar');
    }).not.toThrow();
  });
});
