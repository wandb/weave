import {
  allObjPaths,
  isAssignableTo,
  isListLike,
  list,
  listObjectTypePassTags,
  taggedValue,
  typedDict,
  union,
} from './helpers';
import {Type} from './types';

describe('allObjPaths', () => {
  it('simple case', () => {
    expect(allObjPaths(typedDict({a: 'number'}))).toEqual([
      {path: ['a'], type: 'number'},
    ]);
  });
});

describe('listObjectTypePassTags', () => {
  const runTag = typedDict({run: 'run'});
  const projectTag = typedDict({project: 'project'});
  const randValue = typedDict({rand: 'number'});
  const randList = list(randValue);
  const taggedList = taggedValue(runTag, randList);
  it('handles untagged list of objects', () => {
    expect(listObjectTypePassTags(randList)).toEqual(randValue);
  });
  it('handles list of objects with tags', () => {
    expect(listObjectTypePassTags(taggedList)).toEqual(
      taggedValue(runTag, randValue)
    );
  });
  it('handles nested lists of objects with tags', () => {
    const nestedTaggedList = taggedValue(projectTag, list(taggedList));
    let unnestedTaggedList = listObjectTypePassTags(nestedTaggedList);
    expect(
      isAssignableTo(unnestedTaggedList, taggedValue(runTag, 'any'))
    ).toBeTruthy();
    expect(
      isAssignableTo(unnestedTaggedList, taggedValue(projectTag, 'any'))
    ).toBeTruthy();

    unnestedTaggedList = listObjectTypePassTags(unnestedTaggedList);
    expect(
      isAssignableTo(unnestedTaggedList, taggedValue(runTag, 'any'))
    ).toBeTruthy();
    expect(
      isAssignableTo(unnestedTaggedList, taggedValue(projectTag, 'any'))
    ).toBeTruthy();
  });
  it('handles deeply nested lists of objects with tags', () => {
    let nestedTaggedList = taggedValue(projectTag, list(taggedList));
    for (let i = 0; i < 10; i++) {
      nestedTaggedList = taggedValue(projectTag, list(nestedTaggedList));
    }
    nestedTaggedList = taggedValue(runTag, list(nestedTaggedList));

    // I want the top level run tag to be preserved as I unnest
    expect(
      isAssignableTo(nestedTaggedList, taggedValue(runTag, 'any'))
    ).toBeTruthy();
    while (isListLike(nestedTaggedList)) {
      nestedTaggedList = listObjectTypePassTags(nestedTaggedList);
      expect(
        isAssignableTo(nestedTaggedList, taggedValue(runTag, 'any'))
      ).toBeTruthy();
    }
    // Expect the project tag and run tag to be preserved as I unnest
    expect(
      isAssignableTo(nestedTaggedList, taggedValue(projectTag, 'any'))
    ).toBeTruthy();
  });
});

describe('union', () => {
  it('empty array returns invalid', () => {
    expect(union([])).toEqual('invalid');
  });

  it('single member returns the member itself', () => {
    expect(union(['string'])).toEqual('string');
    expect(union(['number'])).toEqual('number');
    expect(union([{type: 'list', objectType: 'string'}])).toEqual({
      type: 'list',
      objectType: 'string',
    });
  });

  it('flattens nested unions', () => {
    const nestedUnion = union([
      'string',
      {type: 'union', members: ['number', 'boolean']},
    ]);
    expect(nestedUnion).toEqual({
      type: 'union',
      members: ['string', 'number', 'boolean'],
    });
  });

  it('removes duplicate simple types', () => {
    expect(union(['string', 'string', 'number', 'string'])).toEqual({
      type: 'union',
      members: ['string', 'number'],
    });
  });

  it('removes duplicate complex types', () => {
    const listType = {type: 'list', objectType: 'string'} as const;
    expect(union([listType, listType])).toEqual(listType);
  });

  it('removes assignable duplicates', () => {
    // Test that types that are mutually assignable are deduplicated
    const result = union(['int', 'int', 'number']);
    expect(result).toEqual({
      type: 'union',
      members: ['int', 'number'],
    });
  });

  it('handles tagged values correctly', () => {
    const tag1 = typedDict({tag1: 'string'});
    const tag2 = typedDict({tag2: 'number'});
    const tagged1 = taggedValue(tag1, 'string');
    const tagged2 = taggedValue(tag2, 'boolean');

    const result = union([tagged1, tagged2]);
    expect(result).toEqual({
      type: 'union',
      members: [tagged1, tagged2],
    });
  });

  it('merges tagged values with same tags', () => {
    const tag = typedDict({tag1: 'string'});
    const tagged1 = taggedValue(tag, 'string');
    const tagged2 = taggedValue(tag, 'number');

    const result = union([tagged1, tagged2]);
    expect(result).toEqual({
      type: 'tagged',
      tag: tag,
      value: {type: 'union', members: ['string', 'number']},
    });
  });

  it('flattens tagged values containing unions', () => {
    const tag = typedDict({tag1: 'string'});
    const taggedUnion = taggedValue(tag, {
      type: 'union',
      members: ['string', 'number'],
    });

    const result = union([taggedUnion, 'boolean']);
    expect(result).toEqual({
      type: 'union',
      members: [
        taggedValue(tag, 'string'),
        taggedValue(tag, 'number'),
        'boolean',
      ],
    });
  });

  it('handles maybe types (none unions)', () => {
    const result = union(['none', 'string', 'none']);
    expect(result).toEqual({
      type: 'union',
      members: ['none', 'string'],
    });
  });

  it('preserves order for non-duplicate members', () => {
    const result = union(['boolean', 'string', 'number']);
    expect(result).toEqual({
      type: 'union',
      members: ['boolean', 'string', 'number'],
    });
  });

  it('handles complex nested structures', () => {
    const tag1 = typedDict({tag1: 'string'});
    const tag2 = typedDict({tag2: 'number'});
    const nestedUnion = {
      type: 'union' as const,
      members: [taggedValue(tag1, 'string'), taggedValue(tag1, 'number')],
    };

    const result = union([nestedUnion, taggedValue(tag2, 'boolean'), 'none']);

    // Should flatten the nested union and keep all unique tagged values
    expect(result).toEqual({
      type: 'union',
      members: [
        {
          type: 'tagged',
          tag: tag1,
          value: {type: 'union', members: ['string', 'number']},
        },
        taggedValue(tag2, 'boolean'),
        'none',
      ],
    });
  });

  it('handles const types', () => {
    const const1 = {
      type: 'const' as const,
      valType: 'string' as const,
      val: 'hello',
    };
    const const2 = {
      type: 'const' as const,
      valType: 'string' as const,
      val: 'world',
    };
    const const3 = {
      type: 'const' as const,
      valType: 'string' as const,
      val: 'hello',
    };

    const result = union([const1, const2, const3]);
    // const1 and const3 should be deduplicated
    expect(result).toEqual({
      type: 'union',
      members: [const1, const2],
    });
  });

  it('handles typed dicts in unions', () => {
    const dict1 = typedDict({a: 'string', b: 'number'});
    const dict2 = typedDict({a: 'string', c: 'boolean'});

    const result = union([dict1, dict2]);
    expect(result).toEqual({
      type: 'union',
      members: [dict1, dict2],
    });
  });

  it('handles lists with different constraints', () => {
    const list1 = list('string', 1, 5);
    const list2 = list('string', 2, 10);
    const list3 = list('string', 1, 5); // duplicate of list1

    const result = union([list1, list2, list3]);
    expect(result).toEqual({
      type: 'union',
      members: [list1, list2],
    });
  });

  it('handles file types', () => {
    const file1 = {type: 'file' as const, extension: 'json'};
    const file2 = {
      type: 'file' as const,
      extension: 'json',
      wbObjectType: {type: 'table' as const, columnTypes: {}},
    };

    const result = union([file1, file2]);
    expect(result).toEqual({
      type: 'union',
      members: [file1, file2],
    });
  });

  it('handles function types', () => {
    const func1 = {
      type: 'function' as const,
      inputTypes: {arg1: 'string' as const},
      outputType: 'number' as const,
    };
    const func2 = {
      type: 'function' as const,
      inputTypes: {arg1: 'string' as const},
      outputType: 'string' as const,
    };

    const result = union([func1, func2]);
    expect(result).toEqual({
      type: 'union',
      members: [func1, func2],
    });
  });

  it('handles table types', () => {
    const table1 = {
      type: 'table' as const,
      columnTypes: {col1: 'string' as const},
    };
    const table2 = {
      type: 'table' as const,
      columnTypes: {col1: 'number' as const},
    };

    const result = union([table1, table2]);
    expect(result).toEqual({
      type: 'union',
      members: [table1, table2],
    });
  });

  it('performance: handles large unions efficiently', () => {
    // Create a large array with many duplicates
    const members: Type[] = [];
    for (let i = 0; i < 100; i++) {
      members.push('string');
      members.push('number');
      members.push({type: 'list' as const, objectType: 'string' as const});
    }

    const startTime = Date.now();
    const result = union(members);
    const endTime = Date.now();

    // Should complete quickly (less than 100ms for 300 items)
    expect(endTime - startTime).toBeLessThan(100);

    // Should deduplicate correctly
    expect(result).toEqual({
      type: 'union',
      members: ['string', 'number', {type: 'list', objectType: 'string'}],
    });
  });

  it('correctly identifies same JSON structure as duplicates', () => {
    const obj1 = {
      type: 'typedDict' as const,
      propertyTypes: {a: 'string' as const, b: 'number' as const},
    };
    const obj2 = {
      type: 'typedDict' as const,
      propertyTypes: {a: 'string' as const, b: 'number' as const},
    };

    const result = union([obj1, obj2]);
    expect(result).toEqual(obj1);
  });

  it('handles deeply nested tagged values', () => {
    const tag1 = typedDict({level1: 'string'});
    const tag2 = typedDict({level2: 'number'});
    const tag3 = typedDict({level3: 'boolean'});

    const deeplyTagged = taggedValue(
      tag1,
      taggedValue(tag2, taggedValue(tag3, 'string'))
    );

    const result = union([deeplyTagged, 'number']);
    expect(result).toEqual({
      type: 'union',
      members: [deeplyTagged, 'number'],
    });
  });

  it('handles media types', () => {
    const image = {type: 'image-file' as const};
    const video = {type: 'video-file' as const};
    const audio = {type: 'audio-file' as const};

    const result = union([image, video, audio, image]);
    expect(result).toEqual({
      type: 'union',
      members: [image, video, audio],
    });
  });

  it('handles timestamp types', () => {
    const timestamp1 = {type: 'timestamp' as const};
    const timestamp2 = {type: 'timestamp' as const};

    const result = union([timestamp1, timestamp2, 'string']);
    expect(result).toEqual({
      type: 'union',
      members: [timestamp1, 'string'],
    });
  });

  it('handles dict types', () => {
    const dict1 = {type: 'dict' as const, objectType: 'string'};
    const dict2 = {type: 'dict' as const, objectType: 'number'};
    const dict3 = {type: 'dict' as const, objectType: 'string'}; // duplicate

    const result = union([dict1, dict2, dict3]);
    expect(result).toEqual({
      type: 'union',
      members: [dict1, dict2],
    });
  });

  it('preserves notRequiredKeys in typedDict unions', () => {
    const dict1 = typedDict({a: 'string'}, ['a']);
    const dict2 = typedDict({a: 'string', b: 'number'}, ['b']);

    const result = union([dict1, dict2]);
    expect(result).toEqual({
      type: 'union',
      members: [dict1, dict2],
    });
  });

  it('handles ndarray types', () => {
    const ndarray1 = {type: 'ndarray' as const, shape: [2, 3]};
    const ndarray2 = {type: 'ndarray' as const, shape: [2, 3]};

    const result = union([ndarray1, ndarray2]);
    expect(result).toEqual(ndarray1);
  });

  it('handles dir types', () => {
    const dir1 = {type: 'dir' as const};
    const dir2 = {type: 'dir' as const};

    const result = union([dir1, dir2, 'string']);
    expect(result).toEqual({
      type: 'union',
      members: [dir1, 'string'],
    });
  });

  it('handles joined-table and partitioned-table types', () => {
    const joined = {type: 'joined-table' as const, columnTypes: {}};
    const partitioned = {type: 'partitioned-table' as const, columnTypes: {}};

    const result = union([joined, partitioned, joined]);
    expect(result).toEqual({
      type: 'union',
      members: [joined, partitioned],
    });
  });

  it('correctly handles union with only tagged values of same tag', () => {
    const tag = typedDict({myTag: 'string'});
    const tagged1 = taggedValue(tag, 'string');
    const tagged2 = taggedValue(tag, 'number');
    const tagged3 = taggedValue(tag, 'boolean');

    const result = union([tagged1, tagged2, tagged3]);
    expect(result).toEqual({
      type: 'tagged',
      tag: tag,
      value: {
        type: 'union',
        members: ['string', 'number', 'boolean'],
      },
    });
  });

  it('handles mixed tagged and non-tagged values', () => {
    const tag = typedDict({myTag: 'string'});
    const tagged1 = taggedValue(tag, 'string');
    const tagged2 = taggedValue(tag, 'number');

    const result = union([tagged1, tagged2, 'boolean', 'string']);
    expect(result).toEqual({
      type: 'union',
      members: [
        {
          type: 'tagged',
          tag: tag,
          value: {type: 'union', members: ['string', 'number']},
        },
        'boolean',
        'string',
      ],
    });
  });
});
