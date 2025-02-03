import {getValidPinModel, removeAlwaysLeft} from './pin';

describe('removeAlwaysLeft', () => {
  it('removes an alwaysLeft item from left', () => {
    const result = removeAlwaysLeft({left: ['checkbox', 'foo']}, ['checkbox']);
    expect(result).toEqual({
      left: ['foo'],
    });
  });
  it('removes multiple alwaysLeft items from left', () => {
    const result = removeAlwaysLeft({left: ['checkbox', 'foo', 'bar']}, [
      'bar',
      'checkbox',
    ]);
    expect(result).toEqual({
      left: ['foo'],
    });
  });
  it('does not change when cols are not in left', () => {
    const result = removeAlwaysLeft({left: ['checkbox', 'foo']}, ['bar']);
    expect(result).toEqual({
      left: ['checkbox', 'foo'],
    });
  });
  it('does not change when no left', () => {
    const result = removeAlwaysLeft({right: ['checkbox', 'foo']}, ['checkbox']);
    expect(result).toEqual({
      right: ['checkbox', 'foo'],
    });
  });
});

describe('getValidPinModel', () => {
  it('parses a valid pin model', () => {
    const parsed = getValidPinModel(
      '{"left": ["CustomCheckbox", "op_name", "feedback"]}'
    );
    expect(parsed).toEqual({
      left: ['CustomCheckbox', 'op_name', 'feedback'],
    });
  });
  it('includes alwaysLeft items when left is specified', () => {
    const parsed = getValidPinModel('{"left": ["foo"]}', null, ['checkbox']);
    expect(parsed).toEqual({
      left: ['checkbox', 'foo'],
    });
  });
  it('includes alwaysLeft items when left is not specified', () => {
    const parsed = getValidPinModel('{}', null, ['checkbox']);
    expect(parsed).toEqual({
      left: ['checkbox'],
    });
  });
  it('moves alwaysLeft items to front', () => {
    const parsed = getValidPinModel('{"left": ["foo", "checkbox"]}', null, [
      'checkbox',
    ]);
    expect(parsed).toEqual({
      left: ['checkbox', 'foo'],
    });
  });

  it('returns {} on non-object with no explicit default', () => {
    const parsed = getValidPinModel('[]');
    expect(parsed).toEqual({});
  });
  it('returns {} on invalid pin value with no explicit default', () => {
    const parsed = getValidPinModel('{"lef": ["foo"]}');
    expect(parsed).toEqual({});
  });
  it('returns default on non-object', () => {
    const parsed = getValidPinModel('[]', {left: ['checkbox']});
    expect(parsed).toEqual({
      left: ['checkbox'],
    });
  });
});
