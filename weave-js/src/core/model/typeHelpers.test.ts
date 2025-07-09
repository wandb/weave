import {
  allObjPaths,
  dict,
  isAssignableTo,
  isListLike,
  list,
  listObjectTypePassTags,
  maybe,
  taggedValue,
  typedDict,
  union,
} from './helpers';
import {Union} from './types';

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
  describe('basic functionality', () => {
    it('handles empty array', () => {
      expect(union([])).toEqual('invalid');
    });

    it('handles single member', () => {
      expect(union(['string'])).toEqual('string');
      expect(union([typedDict({a: 'number'})])).toEqual(
        typedDict({a: 'number'})
      );
    });

    it('handles simple types', () => {
      expect(union(['string', 'number'])).toEqual({
        type: 'union',
        members: ['string', 'number'],
      });
    });

    it('removes duplicate simple types', () => {
      expect(union(['string', 'string', 'number', 'string'])).toEqual({
        type: 'union',
        members: ['string', 'number'],
      });
    });

    it('flattens nested unions', () => {
      const nestedUnion = {
        type: 'union' as const,
        members: ['string' as const, 'number' as const],
      };
      expect(union([nestedUnion, 'boolean'])).toEqual({
        type: 'union',
        members: ['string', 'number', 'boolean'],
      });
    });
  });

  describe('typedDict deduplication', () => {
    it('removes duplicate typedDicts with same properties', () => {
      const td1 = typedDict({a: 'number', b: 'string'});
      const td2 = typedDict({a: 'number', b: 'string'});
      const td3 = typedDict({b: 'string', a: 'number'}); // different order, same type

      const result = union([td1, td2, td3]);
      expect(result).toEqual(td1);
    });

    it('preserves different typedDicts', () => {
      const td1 = typedDict({a: 'number'});
      const td2 = typedDict({b: 'string'});
      const td3 = typedDict({a: 'string'}); // same key, different type

      const result = union([td1, td2, td3]);
      expect(result).toEqual({
        type: 'union',
        members: [td1, td2, td3],
      });
    });

    it('handles complex nested types in typedDict properties', () => {
      const td1 = typedDict({
        a: list('number'),
        b: maybe('string'),
        c: dict('boolean'),
      });
      const td2 = typedDict({
        a: list('number'),
        b: maybe('string'),
        c: dict('boolean'),
      });

      const result = union([td1, td2]);
      expect(result).toEqual(td1);
    });

    it('handles typedDicts with notRequiredKeys', () => {
      const td1 = typedDict({a: 'number', b: 'string'}, ['b']);
      const td2 = typedDict({a: 'number', b: 'string'}, ['b']);
      const td3 = typedDict({a: 'number', b: 'string'}); // no notRequiredKeys

      const result = union([td1, td2, td3]);
      expect(result).toEqual(union([td1, td3]));
    });

    it('handles typedDicts with union properties', () => {
      const td1 = typedDict({
        a: union(['string', 'number']),
        b: 'boolean',
      });
      const td2 = typedDict({
        a: union(['number', 'string']), // different order in union
        b: 'boolean',
      });

      const result = union([td1, td2]);
      expect(result).toEqual(td1);
    });
  });

  describe('mixed type deduplication', () => {
    it('handles mix of typedDicts and other types', () => {
      const td1 = typedDict({a: 'number'});
      const td2 = typedDict({a: 'number'}); // duplicate
      const listType = list('string');

      const result = union([td1, 'string', td2, listType, 'string']);
      expect(result).toEqual({
        type: 'union',
        members: [td1, 'string', listType],
      });
    });

    it('preserves assignable but not equal types', () => {
      const l1 = list('number', 1, 5); // min 1, max 5
      const l2 = list('number', 2, 4); // min 2, max 4
      const l3 = list('number'); // no bounds

      const result = union([l1, l2, l3]);
      // These are assignable in some directions but not equal
      expect(result).toEqual({
        type: 'union',
        members: [l1, l2, l3],
      });
    });
  });

  describe('tagged value handling', () => {
    it('flattens tagged unions and merges by tag', () => {
      const tag = typedDict({source: 'string'});
      const taggedUnion = taggedValue(tag, union(['number', 'string']));

      const result = union([taggedUnion, 'boolean']);
      // Tagged values with the same tag get merged back together
      expect(result).toEqual({
        type: 'union',
        members: ['boolean', taggedValue(tag, union(['number', 'string']))],
      });
    });

    it('merges tagged values with same tags', () => {
      const tag = typedDict({source: 'string'});
      const tv1 = taggedValue(tag, 'number');
      const tv2 = taggedValue(tag, 'string');
      const tv3 = taggedValue(tag, 'number'); // duplicate

      const result = union([tv1, tv2, tv3]);
      expect(result).toEqual(taggedValue(tag, union(['number', 'string'])));
    });

    it('preserves tagged values with different tags', () => {
      const tag1 = typedDict({source: 'string'});
      const tag2 = typedDict({origin: 'string'});
      const tv1 = taggedValue(tag1, 'number');
      const tv2 = taggedValue(tag2, 'number');

      const result = union([tv1, tv2]);
      expect(result).toEqual({
        type: 'union',
        members: [tv1, tv2],
      });
    });

    it('flattens and groups tagged values by tag', () => {
      const tag1 = typedDict({source: 'string'});
      const tag2 = typedDict({origin: 'string'});

      // Create a union with tagged values that have different tags
      const result = union([
        taggedValue(tag1, 'number'),
        taggedValue(tag2, 'number'),
        taggedValue(tag1, 'string'),
      ]);

      // Should be a union with 2 members
      expect((result as Union).type).toEqual('union');
      expect((result as Union).members.length).toEqual(2);

      // Find the members
      const members = (result as any).members;
      const tag1Member = members.find(
        (m: any) =>
          m.type === 'tagged' && m.tag.propertyTypes.source === 'string'
      );
      const tag2Member = members.find(
        (m: any) =>
          m.type === 'tagged' && m.tag.propertyTypes.origin === 'string'
      );

      // tag1 values should be merged into a union
      expect(tag1Member).toBeDefined();
      expect(tag1Member.value.type).toEqual('union');
      expect(tag1Member.value.members).toEqual(['number', 'string']);

      // tag2 should stay as is
      expect(tag2Member).toBeDefined();
      expect(tag2Member.value).toEqual('number');
    });
  });

  describe('edge cases', () => {
    it('handles self-referential structures gracefully', () => {
      // This test ensures the JSON.stringify fallback doesn't break on circular references
      const td1 = typedDict({a: 'number'});
      const td2 = typedDict({b: list('any')});

      // Create a complex type that might stress the system
      const complexType = union([
        td1,
        td2,
        list(union([td1, td2])),
        maybe(dict(union([td1, td2]))),
      ]);

      // Should not throw
      expect(() => union([complexType, complexType])).not.toThrow();
    });

    it('preserves order for non-deduplicated types', () => {
      const td1 = typedDict({a: 'number'});
      const td2 = typedDict({b: 'string'});
      const td3 = typedDict({c: 'boolean'});

      const result = union([td1, td2, td3]);
      expect(result).toEqual({
        type: 'union',
        members: [td1, td2, td3],
      });
    });
  });
});
