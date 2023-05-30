import {
  isAssignableTo,
  list,
  typedDict,
  typedDictPropertyTypes,
  union,
} from './helpers';

// const handlers = [
//   {inputType: 'string' as const, id: 'string1'},
//   {inputType: 'number' as const, id: 'number1'},
//   {
//     inputType: {
//       type: 'list' as const,
//       objectType: 'number' as const,
//     },
//     id: 'array-number1',
//   },
//   {
//     inputType: {
//       type: 'dict' as const,
//       objectType: {
//         type: 'list' as const,
//         objectType: 'number' as const,
//       },
//     },
//     id: 'dict-array-number1',
//   },
// ];

describe('typesMatch', () => {
  it('file type with matching extension', () => {
    const result = isAssignableTo(
      {type: 'file', extension: 'md'},
      {type: 'file', extension: 'md'}
    );
    expect(result).toEqual(true);
  });
  it('file type with different extension', () => {
    const result = isAssignableTo(
      {type: 'file', extension: 'md'},
      {type: 'file', extension: 'txt'}
    );
    expect(result).toEqual(false);
  });
  it('file type with matching wbObjectType', () => {
    const result = isAssignableTo(
      {type: 'file', wbObjectType: {type: 'image-file'}},
      {type: 'file', wbObjectType: {type: 'image-file'}}
    );
    expect(result).toEqual(true);
  });
  it('file type with different wbObjectType', () => {
    const result = isAssignableTo(
      {type: 'file', wbObjectType: {type: 'image-file'}},
      {type: 'file', wbObjectType: {type: 'table', columnTypes: {}}}
    );
    expect(result).toEqual(false);
  });
  it('file type with extension and wbObjectType', () => {
    const result = isAssignableTo(
      {type: 'file', extension: 'md', wbObjectType: {type: 'image-file'}},
      {
        type: 'file',
        extension: 'txt',
        wbObjectType: {type: 'table', columnTypes: {}},
      }
    );
    expect(result).toEqual(false);
  });

  it('number[] is assignable to (null | number)[]', () => {
    expect(
      isAssignableTo(list('number'), list(union(['none', 'number'])))
    ).toEqual(true);
  });

  it('(null | number)[] is assignable to (null | number)[]', () => {
    expect(
      isAssignableTo(
        list(union(['none', 'number'])),
        list(union(['none', 'number']))
      )
    ).toEqual(true);
  });

  // Tensor type not enabled now
  // it('tensor assignments', () => {
  //   expect(
  //     TypeHelpers.isAssignableTo(TypeHelpers.list('number'), Types.tensor('number'))
  //   ).toEqual(true);
  //   expect(
  //     TypeHelpers.isAssignableTo(
  //       TypeHelpers.list(TypeHelpers.list('number')),
  //       Types.tensor('number')
  //     )
  //   ).toEqual(true);

  //   expect(
  //     TypeHelpers.isAssignableTo(
  //       TypeHelpers.list(TypeHelpers.list('number')),
  //       Types.tensor('string')
  //     )
  //   ).toEqual(false);

  //   expect(
  //     TypeHelpers.isAssignableTo(
  //       TypeHelpers.list(TypeHelpers.list(TypeHelpers.union(['none', 'number']))),
  //       Types.tensor(TypeHelpers.union(['none', 'number']))
  //     )
  //   ).toEqual(true);
  // });
});

describe('typedDictPropertyTypes', () => {
  it('creates maybe when key missing from union member', () => {
    expect(
      typedDictPropertyTypes(
        union([typedDict({a: 'string', b: 'number'}), typedDict({a: 'string'})])
      )
    ).toEqual({a: 'string', b: union(['number', 'none'])});
  });
});
