import {trimEndChar, trimStartChar} from './string';

describe('trimStartChar', () => {
  it('handles start char does not exist', () => {
    expect(trimStartChar('abc', 'd')).toEqual('abc');
  });
  it('ignores trim char not at start', () => {
    expect(trimStartChar('abc', 'b')).toEqual('abc');
  });
  it('removes all trim char', () => {
    expect(trimStartChar('aaaaabc', 'a')).toEqual('bc');
  });
  it('returns empty string if entirely trim char', () => {
    expect(trimStartChar('aaaaa', 'a')).toEqual('');
  });
});

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
