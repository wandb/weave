import {
  allObjPaths,
  isAssignableTo,
  isListLike,
  list,
  listObjectTypePassTags,
  taggedValue,
  typedDict,
} from './helpers';

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
