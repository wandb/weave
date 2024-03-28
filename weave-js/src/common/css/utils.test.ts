import {Color, hexToRGB} from './utils';

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

describe('Color.fromHex', () => {
  it('parses six value syntax', () => {
    const c = Color.fromHex('#123456');
    expect(c.r).toEqual(18);
    expect(c.g).toEqual(52);
    expect(c.b).toEqual(86);
    expect(c.a).toEqual(undefined);
  });
  it('parses three value syntax', () => {
    const c = Color.fromHex('#fab');
    expect(c.r).toEqual(255);
    expect(c.g).toEqual(170);
    expect(c.b).toEqual(187);
    expect(c.a).toEqual(undefined);
  });
});
