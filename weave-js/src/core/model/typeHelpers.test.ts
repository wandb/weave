import {allObjPaths, typedDict} from './helpers';

describe('allObjPaths', () => {
  it('simple case', () => {
    expect(allObjPaths(typedDict({a: 'number'}))).toEqual([
      {path: ['a'], type: 'number'},
    ]);
  });
});
