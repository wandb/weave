import {trimEndChar} from './string';

describe('trimEndChar', () => {
  it('handles end char does not exist', () => {
    expect(trimEndChar('abc', 'd')).toEqual('abc');
  });
  it('ignores trim char not at end', () => {
    expect(trimEndChar('abc', 'b')).toEqual('abc');
  });
  it('removes all trim char', () => {
    expect(trimEndChar('abccccc', 'c')).toEqual('ab');
  });
  it('returns empty string if entirely trim char', () => {
    expect(trimEndChar('ccccc', 'c')).toEqual('');
  });
});
