import {deltaStringToMilliseconds} from './PanelDateRange';

describe('deltaStringToMilliseconds', () => {
  it('Parses seconds', () => {
    expect(deltaStringToMilliseconds('42s')).toEqual(42 * 1000);
  });
  it('Parses minutes', () => {
    expect(deltaStringToMilliseconds('90m')).toEqual(90 * 60 * 1000);
  });
  it('Parses months', () => {
    // Always uses 30 days per month
    expect(deltaStringToMilliseconds('2mo')).toEqual(
      2 * 30 * 24 * 60 * 60 * 1000
    );
  });
  it('Parses minutes and seconds', () => {
    expect(deltaStringToMilliseconds('10m30s')).toEqual((10 * 60 + 30) * 1000);
    expect(deltaStringToMilliseconds('10m 30s')).toEqual((10 * 60 + 30) * 1000);
    expect(deltaStringToMilliseconds('10m, 30s')).toEqual(
      (10 * 60 + 30) * 1000
    );
  });
  it('Parses seconds and minutes', () => {
    expect(deltaStringToMilliseconds('30s 10m')).toEqual((10 * 60 + 30) * 1000);
  });
  it('Returns null on repeated units', () => {
    expect(deltaStringToMilliseconds('10s 20s')).toBeNull();
  });
  it('Handles leading and trailing whitespace', () => {
    expect(deltaStringToMilliseconds(' 42s ')).toEqual(42 * 1000);
  });
  it('Ignores extra text', () => {
    expect(deltaStringToMilliseconds('42sec')).toEqual(42 * 1000);
    expect(deltaStringToMilliseconds('add 42s')).toEqual(42 * 1000);
  });
  it('Returns null for negative numeric values', () => {
    expect(deltaStringToMilliseconds('-42s')).toBeNull();
  });
  it('Returns null when no units present', () => {
    expect(deltaStringToMilliseconds('')).toBeNull();
    expect(deltaStringToMilliseconds('    ')).toBeNull();
    expect(deltaStringToMilliseconds('blah')).toBeNull();
  });
});
