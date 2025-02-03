import {sanitizeString} from './sanitizeSecrets';

describe('sanitizeString', () => {
  test('does not change clean string', () => {
    expect(sanitizeString('foo')).toEqual('foo');
  });
  test('does not change non-literal value', () => {
    expect(sanitizeString('"api_key": api_key')).toEqual('"api_key": api_key');
  });
  test('does sanitize literal value - double quotes', () => {
    expect(sanitizeString('"api_key": "abc"')).toEqual(
      '<Redacted: string contains api_key pattern>'
    );
  });
  test('does sanitize literal value - single quotes', () => {
    expect(sanitizeString('"api_key": \'abc\'')).toEqual(
      '<Redacted: string contains api_key pattern>'
    );
  });
  test('does sanitize known bad keys', () => {
    expect(sanitizeString('"auth_headers": \'abc\'')).toEqual(
      '<Redacted: string contains auth_headers pattern>'
    );
    expect(sanitizeString('"Authorization": \'abc\'')).toEqual(
      '<Redacted: string contains Authorization pattern>'
    );
  });
});
