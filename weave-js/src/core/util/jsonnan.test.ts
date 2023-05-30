import {JSONparseNaN} from './jsonnan';

describe('jsonnan test', () => {
  it('fixes nan', () => {
    expect(JSONparseNaN('[{"a": 5, "b": "NaN", "c": {"d": "NaN"}}]')).toEqual([
      {
        a: 5,
        b: NaN,
        c: {
          d: NaN,
        },
      },
    ]);
  });
});
