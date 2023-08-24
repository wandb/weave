import {fixColNameForVega} from './queryResult';

describe('queryResult tests', () => {
  describe('fixColNameForVega() should', () => {
    test('handle strings', () => {
      const result = fixColNameForVega('test');
      expect(result).toEqual('test');
    });

    test('replaces ./ with _', () => {
      const result = fixColNameForVega('t./est');
      expect(result).toEqual('t_est');
    });

    test('handle numbers', () => {
      const result = fixColNameForVega(1);
      expect(result).toEqual('1');
    });
  });
});
