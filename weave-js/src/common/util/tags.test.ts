import {isInvalidTag} from './tags';

describe('validateTag() should', () => {
  test('only allow hyphens, colons and underscores as special characters', () => {
    const validTagNames = [
      'valid-tag-name',
      'ThisIsAlsoValid',
      'And_So_Is:This',
      'spaces are valid',
    ];
    validTagNames.forEach(tagName => {
      const result = isInvalidTag(tagName);
      expect(result).toBe(false);
    });

    const invalidTagNames = ['InvalidChars!@#$%^&*(){}[]"\',./;|\\'];
    invalidTagNames.forEach(tagName => {
      const result = isInvalidTag(tagName);
      expect(result).toBe(true);
    });
  });
});
