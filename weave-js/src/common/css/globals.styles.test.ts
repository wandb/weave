import {hexToRGB} from './globals.styles';

describe('hexToRGB', () => {
  it('converts six value syntax', () => {
    expect(hexToRGB('#FFFFFF')).toEqual('rgb(255, 255, 255)');
    expect(hexToRGB('#ffaabb')).toEqual('rgb(255, 170, 187)');
    expect(hexToRGB('#123456')).toEqual('rgb(18, 52, 86)');
    expect(hexToRGB('#000000')).toEqual('rgb(0, 0, 0)');
  });
  it('converts three value syntax', () => {
    expect(hexToRGB('#FFF')).toEqual('rgb(255, 255, 255)');
    expect(hexToRGB('#fab')).toEqual('rgb(255, 170, 187)');
    expect(hexToRGB('#000')).toEqual('rgb(0, 0, 0)');
  });
  it('throws when missing an octothorpe', () => {
    expect(() => hexToRGB('FFF')).toThrow();
  });
  it('throws when given invalid formats', () => {
    expect(() => hexToRGB('#FFFF')).toThrow();
    expect(() => hexToRGB('#ggg')).toThrow();
  });
});
