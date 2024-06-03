/**
 * This implementation was created with assistance from ChatGPT, an AI developed by OpenAI.
 */

import {insertPath, Path, PathList} from './callsTableColumnsUtil';

describe('insertPath', () => {
  test('should return the same list if P is already in L', () => {
    const L: PathList = [['a'], ['a', 'b'], ['a', 'b', 'c']];
    const P: Path = ['a', 'b'];
    const result = insertPath(L, P);
    expect(result).toEqual(L);
  });

  test('should insert P in the correct position when L is empty', () => {
    const L: PathList = [];
    const P: Path = ['a'];
    const result = insertPath(L, P);
    expect(result).toEqual([['a']]);
  });

  test('should insert P before the first element with a prefix of P', () => {
    const L: PathList = [['a'], ['a', 'b'], ['a', 'b', 'c']];
    const P: Path = ['a', 'b', 'c', 'd'];
    const result = insertPath(L, P);
    expect(result).toEqual([
      ['a'],
      ['a', 'b'],
      ['a', 'b', 'c'],
      ['a', 'b', 'c', 'd'],
    ]);
  });

  test('should insert P after the last element with a prefix of C', () => {
    const L: PathList = [['a'], ['a', 'b'], ['a', 'c']];
    const P: Path = ['a', 'b', 'd'];
    const result = insertPath(L, P);
    expect(result).toEqual([['a'], ['a', 'b'], ['a', 'b', 'd'], ['a', 'c']]);
  });

  test('should insert P after the last element with a prefix of C', () => {
    const L: PathList = [['a'], ['a', 'b'], ['a', 'b', 'c'], ['a', 'c']];
    const P: Path = ['a', 'b', 'd'];
    const result = insertPath(L, P);
    expect(result).toEqual([
      ['a'],
      ['a', 'b'],
      ['a', 'b', 'c'],
      ['a', 'b', 'd'],
      ['a', 'c'],
    ]);
  });

  test('should handle inserting at the end', () => {
    const L: PathList = [['a'], ['a', 'b']];
    const P: Path = ['b'];
    const result = insertPath(L, P);
    expect(result).toEqual([['a'], ['a', 'b'], ['b']]);
  });
});
