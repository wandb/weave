import {list, typedDict, union} from '../../../core/model/helpers';
import {typesAreConcattable} from './util';

describe('typesAreConcattable', () => {
  it('Matches union types', () => {
    const colsRunOne = {
      id: union(['none', 'string']),
      prediction: union(['none', 'number']),
      truth: union(['none', 'number']),
    };
    const colsRunTwo = {...colsRunOne, has_img: union(['none', 'number'])};
    const colsRunThree = {...colsRunTwo, test: union(['none', 'number'])};
    const toType = list(union([typedDict(colsRunTwo), typedDict(colsRunOne)]));
    const type = list(
      union([
        typedDict(colsRunThree),
        typedDict(colsRunTwo),
        typedDict(colsRunOne),
      ])
    );
    expect(typesAreConcattable(type, toType)).toBe(true);
  });

  it('Matches union types that contain typedDict', () => {
    const colsRunOne = {
      id: union(['none', 'string']),
      prediction: union(['none', 'number']),
      truth: union(['none', 'number']),
    };
    const colsRunTwo = {...colsRunOne, prediction: union(['none', 'number'])};
    const toType = list(typedDict(colsRunOne));
    const type = list(union([typedDict(colsRunTwo), typedDict(colsRunOne)]));
    expect(typesAreConcattable(type, toType)).toBe(true);
  });

  it('Fails when union member of type do not contain all keys of toType', () => {
    const toType = list(
      union([
        typedDict({
          id: union(['none', 'string']),
          prediction: union(['none', 'number']),
        }),
      ])
    );
    const type = list(
      union([
        typedDict({id: union(['none', 'string'])}),
        typedDict({
          id: union(['none', 'string']),
          truth: union(['none', 'number']),
        }),
      ])
    );
    expect(typesAreConcattable(type, toType)).toBe(false);
  });

  it('matches simple typed dicts', () => {
    const type1 = typedDict({a: 'number', b: 'string'});
    const type2 = typedDict({a: 'number', b: 'string'});
    expect(typesAreConcattable(type1, type2)).toBe(true);
  });

  it('fails when typed dict is missing properties', () => {
    const type1 = typedDict({a: 'number'});
    const type2 = typedDict({a: 'number', b: 'string'});
    expect(typesAreConcattable(type2, type1)).toBe(true); // type1 can be assigned to type2
    expect(typesAreConcattable(type1, type2)).toBe(false); // type2 cannot be assigned to type1
  });

  it('fails when union contains non-typed dict', () => {
    const baseType = typedDict({a: 'number'});
    const unionType = union(['string', typedDict({a: 'number'})]);
    expect(typesAreConcattable(unionType, baseType)).toBe(false);
  });
});
