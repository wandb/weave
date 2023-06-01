import _ from 'lodash';

import {
  concreteTaggedValue,
  list,
  mappableNullableTaggableVal,
  mappableNullableTaggableValAsync,
  maybe,
  mntTypeApply,
  mntTypeStrip,
  mntValueApply,
  tableRowValue,
  taggableValAsync,
  taggedValue,
  typedDict,
  union,
  withTableRowTag,
} from './model';
import {typedDictPathType, typedDictPathVal} from './model/helpers2';
import {standardOpType, standardOpValue} from './ops/helpers';

const delayedResult = (res: any) => {
  return new Promise(resolve => {
    setTimeout(() => resolve(res), 1);
  });
};

// Tagged value constructor without all the logic of TypeHelpers.concreteTaggedValue
// for test purposes.
const rawTaggedValue = (tag: any, value: any) => {
  return {_tag: tag, _value: value};
};

describe('opPathTypes', () => {
  it('a', () => {
    expect(typedDictPathType(typedDict({a: 'number'}), ['a'])).toEqual(
      'number'
    );
  });

  it('a.b', () => {
    expect(
      typedDictPathType(typedDict({a: typedDict({b: 'number'})}), ['a', 'b'])
    ).toEqual('number');
  });

  it('a.b', () => {
    const row1Type = withTableRowTag(typedDict({a: 'number', b: 'string'}), {
      type: 'table',
      columnTypes: {},
    });
    const row2Type = withTableRowTag(typedDict({a: 'number', b: 'string'}), {
      type: 'table',
      columnTypes: {},
    });
    const joinRowType = typedDict({
      '0': maybe(row1Type),
      '1': maybe(row2Type),
    });
    expect(typedDictPathType(joinRowType, ['*', 'a'])).toEqual(
      typedDict({
        '0': maybe(
          withTableRowTag('number', {
            type: 'table',
            columnTypes: {},
          })
        ),
        '1': maybe(
          withTableRowTag('number', {
            type: 'table',
            columnTypes: {},
          })
        ),
      })
    );
  });

  it('*.b', () => {
    expect(
      typedDictPathType(
        typedDict({
          a: typedDict({b: 'number'}),
          c: typedDict({b: 'number'}),
        }),
        ['*', 'b']
      )
    ).toEqual(typedDict({a: 'number', c: 'number'}));
  });

  it('union with missing member keys', () => {
    expect(
      typedDictPathType(
        union([
          typedDict({a: 'string', b: 'number'}),
          typedDict({a: 'string'}),
        ]),
        ['b']
      )
    ).toEqual(union(['number', 'none']));
  });

  describe('nested tagged path', () => {
    const objType = typedDict({
      0: tableRowValue(
        typedDict({
          c: 'string',
          t_2: tableRowValue(
            typedDict({
              b: 'string',
              t_1: tableRowValue(
                typedDict({
                  a: 'string',
                })
              ),
            })
          ),
        })
      ),
    });
    const obj = {
      '0': {
        _tag: 'tag1',
        _value: {
          c: 'c',
          t_2: {
            _tag: 'tag2',
            _value: {
              b: 'b',
              t_1: {
                _tag: 'tag3',
                _value: {
                  a: 'a',
                },
              },
            },
          },
        },
      },
    };
    it('val *.t_2.t_1.a', () => {
      expect(typedDictPathType(objType, ['*', 't_2', 't_1', 'a'])).toEqual(
        typedDict({
          0: tableRowValue(tableRowValue(tableRowValue('string'))),
        })
      );
      expect(typedDictPathVal(obj, ['*', 't_2', 't_1', 'a'])).toEqual({
        '0': {
          _tag: {_tag: {_tag: 'tag1', _value: 'tag2'}, _value: 'tag3'},
          _value: 'a',
        },
      });
    });

    it('val *.*.t_1.a', () => {
      expect(typedDictPathType(objType, ['*', '*', 't_1', 'a'])).toEqual(
        typedDict({
          0: tableRowValue(
            typedDict({
              c: 'none',
              t_2: tableRowValue(tableRowValue('string')),
            })
          ),
        })
      );
      expect(typedDictPathVal(obj, ['*', '*', 't_1', 'a'])).toEqual({
        '0': {
          _tag: 'tag1',
          _value: {
            c: null,
            t_2: {_tag: {_tag: 'tag2', _value: 'tag3'}, _value: 'a'},
          },
        },
      });
    });
  });

  describe('table row nested obj', () => {
    const objType = tableRowValue(
      typedDict({
        c: 'string',
        t_2: tableRowValue(
          typedDict({
            b: 'string',
            t_1: tableRowValue(
              typedDict({
                a: 'string',
              })
            ),
          })
        ),
      })
    );
    const obj = {
      _tag: 'tag1',
      _value: {
        c: 'c',
        t_2: {
          _tag: 'tag2',
          _value: {
            b: 'b',
            t_1: {
              _tag: 'tag3',
              _value: {
                a: 'a',
              },
            },
          },
        },
      },
    };
    it('val *.t_1.a', () => {
      expect(typedDictPathType(objType, ['*', 't_1', 'a'])).toEqual(
        tableRowValue(
          typedDict({
            c: 'none',
            t_2: tableRowValue(tableRowValue('string')),
          })
        )
      );
      expect(typedDictPathVal(obj, ['*', 't_1', 'a'])).toEqual({
        _tag: 'tag1',
        _value: {
          c: null,
          t_2: {_tag: {_tag: 'tag2', _value: 'tag3'}, _value: 'a'},
        },
      });
    });

    it('val *.*.a', () => {
      expect(typedDictPathType(objType, ['*', '*', 'a'])).toEqual(
        tableRowValue(
          typedDict({
            c: 'none',
            t_2: tableRowValue(
              typedDict({
                b: 'none',
                t_1: tableRowValue('string'),
              })
            ),
          })
        )
      );

      expect(typedDictPathVal(obj, ['*', '*', 'a'])).toEqual({
        _tag: 'tag1',
        _value: {
          c: null,
          t_2: {
            _tag: 'tag2',
            _value: {
              b: null,
              t_1: {
                _tag: 'tag3',
                _value: 'a',
              },
            },
          },
        },
      });
    });
  });

  describe('simple sync', () => {
    it('mappableNullableTaggableVal', async () => {
      const obj = {
        _tag: 'tag1',
        _value: [{_tag: 'tag2', _value: 4}, {_tag: 'tag2', _value: 6}, null],
      };
      const result = await mappableNullableTaggableVal(obj, v => v + 5);
      expect(result).toEqual({
        _tag: 'tag1',
        _value: [{_tag: 'tag2', _value: 9}, {_tag: 'tag2', _value: 11}, null],
      });
    });
  });

  describe('async', () => {
    it('taggableValAsync', async () => {
      const obj = {
        _tag: 'tag1',
        _value: 4,
      };
      const result = await taggableValAsync(obj, async (v: number) =>
        delayedResult(v + 5)
      );
      expect(result).toEqual({_tag: 'tag1', _value: 9});
    });
    it('mappableNullableTaggableValAsync', async () => {
      const obj = {
        _tag: 'tag1',
        _value: [{_tag: 'tag2', _value: 4}, {_tag: 'tag2', _value: 6}, null],
      };
      const result = await mappableNullableTaggableValAsync(obj, async v =>
        delayedResult(v + 5)
      );
      expect(result).toEqual({
        _tag: 'tag1',
        _value: [{_tag: 'tag2', _value: 9}, {_tag: 'tag2', _value: 11}, null],
      });
    });
  });
});

describe('standardOp', () => {
  describe('simple cases', () => {
    it('in: string, ret: number', () => {
      expect(standardOpType('string', t => 'number')).toEqual('number');
    });
    it('in: none, ret: number', () => {
      expect(standardOpType('none', t => 'number')).toEqual('none');
    });
    it('in: string[], ret: number', () => {
      expect(standardOpType(list('string'), t => 'number')).toEqual(
        list('number')
      );
    });
    it('in: none[], ret: number', () => {
      expect(standardOpType(list('none'), t => 'number')).toEqual(list('none'));
    });
    it('in: none, ret: tagged', () => {
      expect(
        standardOpType('none', t =>
          taggedValue(typedDict({l1: 'string'}), 'number')
        )
        // TODO: should this be tagged({l1: 'none'}, 'none') ?
      ).toEqual('none');
    });
  });

  describe('union cases', () => {
    it('in: union | string, ret: number', () => {
      expect(standardOpType(union(['string', 'none']), t => 'number')).toEqual(
        union(['none', 'number'])
      );
    });
    it('in: List<union | string>, ret: number', () => {
      expect(
        standardOpType(list(union(['string', 'none'])), t => 'number')
      ).toEqual(list(union(['none', 'number'])));
    });
    it('in: none | List<string | none>, ret: number', () => {
      expect(
        standardOpType(
          union(['none', list(union(['string', 'none']))]),
          t => 'number'
        )
      ).toEqual(union(['none', list(union(['none', 'number']))]));
    });

    it('in: none | string | List<string | none>, ret: number', () => {
      // This gives maybe('number')
      expect(
        standardOpType(
          union(['none', 'string', list(union(['string', 'none']))]),
          t => 'number'
        )
      ).toEqual(
        // TODO: pretty odd.
        union(['none', 'number'])
      );
    });
  });

  describe('tagged cases', () => {
    // input is tagged, we should preserve
    it('tagged input, untagged ret', () => {
      expect(
        standardOpType(
          taggedValue(typedDict({l1: 'string'}), 'string'),
          t => 'number'
        )
      ).toEqual(taggedValue(typedDict({l1: 'string'}), 'number'));
    });

    // Basic tag merge
    it('tagged input, tagged ret', () => {
      expect(
        standardOpType(taggedValue(typedDict({l1: 'string'}), 'string'), t =>
          taggedValue(typedDict({l2: 'boolean'}), 'number')
        )
      ).toEqual(
        taggedValue(
          taggedValue(typedDict({l1: 'string'}), typedDict({l2: 'boolean'})),
          'number'
        )
      );
    });
  });

  describe('union tagged cases', () => {
    // input none | Tagged
    it('in: none | tagged, ret: tagged', () => {
      expect(
        standardOpType(
          union(['none', taggedValue(typedDict({l1: 'string'}), 'string')]),
          t => taggedValue(typedDict({l2: 'boolean'}), 'number')
        )
      ).toEqual(
        union([
          'none',
          taggedValue(
            taggedValue(typedDict({l1: 'string'}), typedDict({l2: 'boolean'})),
            'number'
          ),
        ])
      );
    });

    // ret none | Tagged
    // Note this one is an example of what we don't want
    it('in: tagged, ret: none | tagged', () => {
      expect(
        standardOpType(taggedValue(typedDict({l1: 'string'}), 'string'), t =>
          union(['none', taggedValue(typedDict({l2: 'boolean'}), 'number')])
        )
      ).toEqual(
        union([
          taggedValue(typedDict({l1: 'string'}), 'none'),
          taggedValue(
            taggedValue(typedDict({l1: 'string'}), typedDict({l2: 'boolean'})),
            'number'
          ),
        ])
      );
    });

    // This is what we do want
    it('in: tagged, ret: tagged<number | none>', () => {
      expect(
        standardOpType(taggedValue(typedDict({l1: 'string'}), 'string'), t =>
          taggedValue(typedDict({l2: 'boolean'}), union(['number', 'none']))
        )
      ).toEqual(
        taggedValue(
          taggedValue(typedDict({l1: 'string'}), typedDict({l2: 'boolean'})),
          union(['number', 'none'])
        )
      );
    });

    // Union with none is fine
    it('in: tagged | none, ret: tagged<number | none>', () => {
      expect(
        standardOpType(
          union(['none', taggedValue(typedDict({l1: 'string'}), 'string')]),
          t =>
            taggedValue(typedDict({l2: 'boolean'}), union(['number', 'none']))
        )
      ).toEqual(
        union([
          'none',
          taggedValue(
            taggedValue(typedDict({l1: 'string'}), typedDict({l2: 'boolean'})),
            union(['number', 'none'])
          ),
        ])
      );
    });

    it('in: tagged<none | string>, ret: tagged<number>', () => {
      expect(
        standardOpType(
          taggedValue(typedDict({l1: 'string'}), union(['none', 'string'])),
          t => taggedValue(typedDict({l2: 'boolean'}), 'number')
        )
      ).toEqual(
        union([
          taggedValue(typedDict({l1: 'string'}), 'none'),
          taggedValue(
            taggedValue(typedDict({l1: 'string'}), typedDict({l2: 'boolean'})),
            'number'
          ),
        ])
      );
    });

    it('type in: tagged<none | string>, ret: tagged<none | number>', () => {
      expect(
        standardOpType(
          taggedValue(typedDict({l1: 'string'}), union(['none', 'string'])),
          t =>
            taggedValue(typedDict({l2: 'boolean'}), union(['number', 'none']))
        )
      ).toEqual(
        union([
          taggedValue(typedDict({l1: 'string'}), 'none'),
          taggedValue(
            taggedValue(typedDict({l1: 'string'}), typedDict({l2: 'boolean'})),
            union(['number', 'none'])
          ),
        ])
      );
    });
    it('  val in: tagged<string>, ret: tagged<number>', () => {
      expect(
        standardOpValue(rawTaggedValue({l1: 'string'}, 'a'), t =>
          rawTaggedValue({l2: 'boolean'}, 5)
        )
      ).toEqual(
        rawTaggedValue(rawTaggedValue({l1: 'string'}, {l2: 'boolean'}), 5)
      );
    });
    it('  val in: tagged<string>, ret: tagged<none>', () => {
      expect(
        standardOpValue(rawTaggedValue({l1: 'string'}, 'a'), t =>
          rawTaggedValue({l2: 'boolean'}, null)
        )
      ).toEqual(
        rawTaggedValue(rawTaggedValue({l1: 'string'}, {l2: 'boolean'}), null)
      );
    });
    it('  val in: tagged<none>, ret: tagged<number>', () => {
      expect(
        standardOpValue(rawTaggedValue({l1: 'string'}, null), t =>
          rawTaggedValue({l2: 'boolean'}, 5)
        )
        // Note: this probably isn't ideal! we lose the downstream tag which means
        // we can't walk back up the tag chain as soon as we encounter a null. Its
        // definitely possible to fix this behavior.
      ).toEqual(rawTaggedValue({l1: 'string'}, null));
    });
    it('  val in: tagged<none>, ret: tagged<none>', () => {
      expect(
        standardOpValue(rawTaggedValue({l1: 'string'}, null), t =>
          rawTaggedValue({l2: 'boolean'}, null)
        )
      ).toEqual(rawTaggedValue({l1: 'string'}, null));
    });
  });

  describe('array + tagged cases', () => {
    // TODO: consider if we want this one to distribute
    it('in: tagged<array>, ret: tagged', () => {
      expect(
        standardOpType(
          taggedValue(typedDict({l1: 'string'}), list('string')),
          t => taggedValue(typedDict({l2: 'boolean'}), 'number')
        )
      ).toEqual(
        taggedValue(
          typedDict({l1: 'string'}),
          list(taggedValue(typedDict({l2: 'boolean'}), 'number'))
        )
      );
    });

    it('in: array<tagged>, ret: tagged', () => {
      expect(
        standardOpType(
          list(taggedValue(typedDict({l1: 'string'}), 'string')),
          t => taggedValue(typedDict({l2: 'boolean'}), 'number')
        )
      ).toEqual(
        list(
          taggedValue(
            taggedValue(typedDict({l1: 'string'}), typedDict({l2: 'boolean'})),
            'number'
          )
        )
      );
    });

    // TODO: do we want to distribute outer tag?
    it('in: tagged<array<tagged>>, ret: tagged', () => {
      expect(
        standardOpType(
          taggedValue(
            typedDict({l3: 'boolean'}),
            list(taggedValue(typedDict({l1: 'string'}), 'string'))
          ),
          t => taggedValue(typedDict({l2: 'boolean'}), 'number')
        )
      ).toEqual(
        taggedValue(
          typedDict({l3: 'boolean'}),
          list(
            taggedValue(
              taggedValue(
                typedDict({l1: 'string'}),
                typedDict({l2: 'boolean'})
              ),
              'number'
            )
          )
        )
      );
    });

    it('in: none | tagged<array<tagged>>, ret: tagged', () => {
      expect(
        standardOpType(
          union([
            'none',
            taggedValue(
              typedDict({l3: 'boolean'}),
              list(taggedValue(typedDict({l1: 'string'}), 'string'))
            ),
          ]),
          t => taggedValue(typedDict({l2: 'boolean'}), 'number')
        )
      ).toEqual(
        union([
          'none',
          taggedValue(
            typedDict({l3: 'boolean'}),
            list(
              taggedValue(
                taggedValue(
                  typedDict({l1: 'string'}),
                  typedDict({l2: 'boolean'})
                ),
                'number'
              )
            )
          ),
        ])
      );
    });

    it('in: none | tagged<array<tagged | none>>, ret: tagged', () => {
      expect(
        standardOpType(
          union([
            'none',
            taggedValue(
              typedDict({l3: 'boolean'}),
              list(taggedValue(typedDict({l1: 'string'}), maybe('string')))
            ),
          ]),
          t => taggedValue(typedDict({l2: 'boolean'}), 'number')
        )
      ).toEqual(
        union([
          'none',
          taggedValue(
            typedDict({l3: 'boolean'}),
            list(
              union([
                taggedValue(typedDict({l1: 'string'}), 'none'),
                taggedValue(
                  taggedValue(
                    typedDict({l1: 'string'}),
                    typedDict({l2: 'boolean'})
                  ),
                  'number'
                ),
              ])
            )
          ),
        ])
      );
    });

    it('in: tagged<array>, ret: tagged<number | none>', () => {
      expect(
        standardOpType(
          taggedValue(typedDict({l1: 'string'}), list('string')),
          t => taggedValue(typedDict({l2: 'boolean'}), maybe('number'))
        )
      ).toEqual(
        taggedValue(
          typedDict({l1: 'string'}),
          list(taggedValue(typedDict({l2: 'boolean'}), maybe('number')))
        )
      );
    });

    it('in: none | tagged<array<tagged>>, ret: tagged<none | number>', () => {
      expect(
        standardOpType(
          union([
            'none',
            taggedValue(
              typedDict({l3: 'boolean'}),
              list(taggedValue(typedDict({l1: 'string'}), 'string'))
            ),
          ]),
          t => taggedValue(typedDict({l2: 'boolean'}), maybe('number'))
        )
      ).toEqual(
        union([
          'none',
          taggedValue(
            typedDict({l3: 'boolean'}),
            list(
              taggedValue(
                taggedValue(
                  typedDict({l1: 'string'}),
                  typedDict({l2: 'boolean'})
                ),
                maybe('number')
              )
            )
          ),
        ])
      );
    });

    it('in: none | tagged<array<tagged | none>>, ret: tagged<none | number>', () => {
      expect(
        standardOpType(
          union([
            'none',
            taggedValue(
              typedDict({l3: 'boolean'}),
              list(taggedValue(typedDict({l1: 'string'}), maybe('string')))
            ),
          ]),
          t => taggedValue(typedDict({l2: 'boolean'}), maybe('number'))
        )
      ).toEqual(
        union([
          'none',
          taggedValue(
            typedDict({l3: 'boolean'}),
            list(
              union([
                taggedValue(typedDict({l1: 'string'}), 'none'),
                taggedValue(
                  taggedValue(
                    typedDict({l1: 'string'}),
                    typedDict({l2: 'boolean'})
                  ),
                  maybe('number')
                ),
              ])
            )
          ),
        ])
      );
    });
  });
});

describe('mntTypeApply', () => {
  describe('(dims=0, tags=false, nones=false)', () => {
    /*
    Cases:
      T
      List<T>
      Maybe<T>
      Tagged<T>
      List<List<T>>
      Maybe<List<T>>
      Tagged<List<T>>
      List<Maybe<T>>
      Tagged<Maybe<T>>
      List<Tagged<T>>
      Maybe<Tagged<T>>
      List<List<List<T>>>
      Maybe<List<List<T>>>
      Tagged<List<List<T>>>
      List<Maybe<List<T>>>
      Tagged<Maybe<List<T>>>
      List<Tagged<List<T>>>
      Maybe<Tagged<List<T>>>
      List<List<Maybe<T>>>
      Maybe<List<Maybe<T>>>
      Tagged<List<Maybe<T>>>
      List<Tagged<Maybe<T>>>
      Maybe<Tagged<Maybe<T>>>
      List<List<Tagged<T>>>
      Maybe<List<Tagged<T>>>
      Tagged<List<Tagged<T>>>
      List<Maybe<Tagged<T>>>
      Tagged<Maybe<Tagged<T>>>
    */
    it('in: T', () => {
      expect(
        mntTypeApply('string', t => {
          expect(t).toEqual('string');
          return 'number';
        })
      ).toEqual('number');
    });

    it('in: List<T>', () => {
      expect(
        mntTypeApply(list('string', 1, 2), t => {
          expect(t).toEqual('string');
          return 'number';
        })
      ).toEqual(list('number', 1, 2));
    });

    it('in: Maybe<T>', () => {
      expect(
        mntTypeApply(maybe('string'), t => {
          expect(t).toEqual('string');
          return 'number';
        })
      ).toEqual(maybe('number'));
    });

    it('in: Tagged<T>', () => {
      expect(
        mntTypeApply(taggedValue('boolean', 'string'), t => {
          expect(t).toEqual('string');
          return 'number';
        })
      ).toEqual(taggedValue('boolean', 'number'));
    });

    it('in: List<List<T>>', () => {
      expect(
        mntTypeApply(list(list('string', 1, 2), 3, 4), t => {
          expect(t).toEqual('string');
          return 'number';
        })
      ).toEqual(list(list('number', 1, 2), 3, 4));
    });

    it('in: Maybe<List<T>>', () => {
      expect(
        mntTypeApply(maybe(list('string', 1, 2)), t => {
          expect(t).toEqual('string');
          return 'number';
        })
      ).toEqual(maybe(list('number', 1, 2)));
    });

    it('in: Tagged<List<T>>', () => {
      expect(
        mntTypeApply(taggedValue('boolean', list('string', 1, 2)), t => {
          expect(t).toEqual('string');
          return 'number';
        })
      ).toEqual(taggedValue('boolean', list('number', 1, 2)));
    });

    it('in: List<Maybe<T>>', () => {
      expect(
        mntTypeApply(list(maybe('string'), 1, 2), t => {
          expect(t).toEqual('string');
          return 'number';
        })
      ).toEqual(list(maybe('number'), 1, 2));
    });

    it('in: Tagged<Maybe<T>>', () => {
      expect(
        mntTypeApply(taggedValue('boolean', maybe('string')), t => {
          expect(t).toEqual('string');
          return 'number';
        })
      ).toEqual(taggedValue('boolean', maybe('number')));
    });

    it('in: List<Tagged<T>>', () => {
      expect(
        mntTypeApply(list(taggedValue('boolean', 'string'), 1, 2), t => {
          expect(t).toEqual('string');
          return 'number';
        })
      ).toEqual(list(taggedValue('boolean', 'number'), 1, 2));
    });

    it('in: Maybe<Tagged<T>>', () => {
      expect(
        mntTypeApply(maybe(taggedValue('boolean', 'string')), t => {
          expect(t).toEqual('string');
          return 'number';
        })
      ).toEqual(maybe(taggedValue('boolean', 'number')));
    });

    it('in: List<List<List<T>>>', () => {
      expect(
        mntTypeApply(list(list(list('string', 1, 2), 3, 4), 5, 6), t => {
          expect(t).toEqual('string');
          return 'number';
        })
      ).toEqual(list(list(list('number', 1, 2), 3, 4), 5, 6));
    });

    it('in: Maybe<List<List<T>>>', () => {
      expect(
        mntTypeApply(maybe(list(list('string', 1, 2), 3, 4)), t => {
          expect(t).toEqual('string');
          return 'number';
        })
      ).toEqual(maybe(list(list('number', 1, 2), 3, 4)));
    });

    it('in: Tagged<List<List<T>>>', () => {
      expect(
        mntTypeApply(
          taggedValue('boolean', list(list('string', 1, 2), 3, 4)),
          t => {
            expect(t).toEqual('string');
            return 'number';
          }
        )
      ).toEqual(taggedValue('boolean', list(list('number', 1, 2), 3, 4)));
    });

    it('in: List<Maybe<List<T>>>', () => {
      expect(
        mntTypeApply(list(maybe(list('string', 1, 2)), 3, 4), t => {
          expect(t).toEqual('string');
          return 'number';
        })
      ).toEqual(list(maybe(list('number', 1, 2)), 3, 4));
    });

    it('in: Tagged<Maybe<List<T>>>', () => {
      expect(
        mntTypeApply(taggedValue('boolean', maybe(list('string', 1, 2))), t => {
          expect(t).toEqual('string');
          return 'number';
        })
      ).toEqual(taggedValue('boolean', maybe(list('number', 1, 2))));
    });

    it('in: List<Tagged<List<T>>>', () => {
      expect(
        mntTypeApply(
          list(taggedValue('boolean', list('string', 1, 2)), 5, 6),
          t => {
            expect(t).toEqual('string');
            return 'number';
          }
        )
      ).toEqual(list(taggedValue('boolean', list('number', 1, 2)), 5, 6));
    });

    it('in: Maybe<Tagged<List<T>>>', () => {
      expect(
        mntTypeApply(maybe(taggedValue('boolean', list('string', 1, 2))), t => {
          expect(t).toEqual('string');
          return 'number';
        })
      ).toEqual(maybe(taggedValue('boolean', list('number', 1, 2))));
    });

    it('in: List<List<Maybe<T>>>', () => {
      expect(
        mntTypeApply(list(list(maybe('string'), 1, 2), 3, 4), t => {
          expect(t).toEqual('string');
          return 'number';
        })
      ).toEqual(list(list(maybe('number'), 1, 2), 3, 4));
    });

    it('in: Maybe<List<Maybe<T>>>', () => {
      expect(
        mntTypeApply(maybe(list(maybe('string'), 1, 2)), t => {
          expect(t).toEqual('string');
          return 'number';
        })
      ).toEqual(maybe(list(maybe('number'), 1, 2)));
    });

    it('in: Tagged<List<Maybe<T>>>', () => {
      expect(
        mntTypeApply(taggedValue('boolean', list(maybe('string'), 1, 2)), t => {
          expect(t).toEqual('string');
          return 'number';
        })
      ).toEqual(taggedValue('boolean', list(maybe('number'), 1, 2)));
    });

    it('in: List<Tagged<Maybe<T>>>', () => {
      expect(
        mntTypeApply(list(taggedValue('boolean', maybe('string')), 1, 2), t => {
          expect(t).toEqual('string');
          return 'number';
        })
      ).toEqual(list(taggedValue('boolean', maybe('number')), 1, 2));
    });

    it('in: Maybe<Tagged<Maybe<T>>>', () => {
      expect(
        mntTypeApply(maybe(taggedValue('boolean', maybe('string'))), t => {
          expect(t).toEqual('string');
          return 'number';
        })
      ).toEqual(maybe(taggedValue('boolean', maybe('number'))));
    });

    it('in: List<List<Tagged<T>>>', () => {
      expect(
        mntTypeApply(
          list(list(taggedValue('boolean', 'string'), 1, 2), 3, 4),
          t => {
            expect(t).toEqual('string');
            return 'number';
          }
        )
      ).toEqual(list(list(taggedValue('boolean', 'number'), 1, 2), 3, 4));
    });

    it('in: Maybe<List<Tagged<T>>>', () => {
      expect(
        mntTypeApply(maybe(list(taggedValue('boolean', 'string'), 1, 2)), t => {
          expect(t).toEqual('string');
          return 'number';
        })
      ).toEqual(maybe(list(taggedValue('boolean', 'number'), 1, 2)));
    });

    it('in: Tagged<List<Tagged<T>>>', () => {
      expect(
        mntTypeApply(
          taggedValue('boolean', list(taggedValue('run', 'string'), 1, 2)),
          t => {
            expect(t).toEqual('string');
            return 'number';
          }
        )
      ).toEqual(
        taggedValue('boolean', list(taggedValue('run', 'number'), 1, 2))
      );
    });

    it('in: List<Maybe<Tagged<T>>>', () => {
      expect(
        mntTypeApply(list(maybe(taggedValue('boolean', 'string')), 1, 2), t => {
          expect(t).toEqual('string');
          return 'number';
        })
      ).toEqual(list(maybe(taggedValue('boolean', 'number')), 1, 2));
    });

    it('in: Tagged<Maybe<Tagged<T>>>', () => {
      expect(
        mntTypeApply(
          taggedValue('boolean', maybe(taggedValue('run', 'string'))),
          t => {
            expect(t).toEqual('string');
            return 'number';
          }
        )
      ).toEqual(taggedValue('boolean', maybe(taggedValue('run', 'number'))));
    });
  });

  describe('(dims=0, tags=false, nones=true)', () => {
    /*
    Cases:
      T
      List<T>
      Maybe<T>
      Tagged<T>
      List<List<T>>
      Maybe<List<T>>
      Tagged<List<T>>
      List<Maybe<T>>
      Tagged<Maybe<T>>
      List<Tagged<T>>
      Maybe<Tagged<T>>
      List<List<List<T>>>
      Maybe<List<List<T>>>
      Tagged<List<List<T>>>
      List<Maybe<List<T>>>
      Tagged<Maybe<List<T>>>
      List<Tagged<List<T>>>
      Maybe<Tagged<List<T>>>
      List<List<Maybe<T>>>
      Maybe<List<Maybe<T>>>
      Tagged<List<Maybe<T>>>
      List<Tagged<Maybe<T>>>
      Maybe<Tagged<Maybe<T>>>
      List<List<Tagged<T>>>
      Maybe<List<Tagged<T>>>
      Tagged<List<Tagged<T>>>
      List<Maybe<Tagged<T>>>
      Tagged<Maybe<Tagged<T>>>
    */
    it('in: T', () => {
      expect(
        mntTypeApply(
          'string',
          t => {
            expect(t).toEqual('string');
            return 'number';
          },
          {nones: true}
        )
      ).toEqual('number');
    });

    it('in: List<T>', () => {
      expect(
        mntTypeApply(
          list('string', 1, 2),
          t => {
            expect(t).toEqual('string');
            return 'number';
          },
          {nones: true}
        )
      ).toEqual(list('number', 1, 2));
    });

    it('in: Maybe<T>', () => {
      const types = new Set(['none', 'string']);
      expect(
        mntTypeApply(
          maybe('string'),
          t => {
            expect(types.has(t as any)).toBe(true);
            types.delete(t as any);
            return 'number';
          },
          {nones: true}
        )
      ).toEqual('number');
      expect(types.values.length).toEqual(0);
    });

    it('in: Tagged<T>', () => {
      expect(
        mntTypeApply(
          taggedValue('boolean', 'string'),
          t => {
            expect(t).toEqual('string');
            return 'number';
          },
          {nones: true}
        )
      ).toEqual(taggedValue('boolean', 'number'));
    });

    it('in: List<List<T>>', () => {
      expect(
        mntTypeApply(
          list(list('string', 1, 2), 3, 4),
          t => {
            expect(t).toEqual('string');
            return 'number';
          },
          {nones: true}
        )
      ).toEqual(list(list('number', 1, 2), 3, 4));
    });

    it('in: Maybe<List<T>>', () => {
      const types = new Set(['none', 'string']);
      expect(
        mntTypeApply(
          maybe(list('string', 1, 2)),
          t => {
            expect(types.has(t as any)).toBe(true);
            types.delete(t as any);
            return 'number';
          },
          {nones: true}
        )
      ).toEqual(union(['number', list('number', 1, 2)]));
      expect(types.values.length).toEqual(0);
    });

    it('in: Tagged<List<T>>', () => {
      expect(
        mntTypeApply(
          taggedValue('boolean', list('string', 1, 2)),
          t => {
            expect(t).toEqual('string');
            return 'number';
          },
          {nones: true}
        )
      ).toEqual(taggedValue('boolean', list('number', 1, 2)));
    });

    it('in: List<Maybe<T>>', () => {
      const types = new Set(['none', 'string']);
      expect(
        mntTypeApply(
          list(maybe('string'), 1, 2),
          t => {
            expect(types.has(t as any)).toBe(true);
            types.delete(t as any);
            return 'number';
          },
          {nones: true}
        )
      ).toEqual(list('number', 1, 2));
      expect(types.values.length).toEqual(0);
    });

    it('in: Tagged<Maybe<T>>', () => {
      const types = new Set(['none', 'string']);
      expect(
        mntTypeApply(
          taggedValue('boolean', maybe('string')),
          t => {
            expect(types.has(t as any)).toBe(true);
            types.delete(t as any);
            return 'number';
          },
          {nones: true}
        )
      ).toEqual(taggedValue('boolean', 'number'));
      expect(types.values.length).toEqual(0);
    });

    it('in: List<Tagged<T>>', () => {
      expect(
        mntTypeApply(
          list(taggedValue('boolean', 'string'), 1, 2),
          t => {
            expect(t).toEqual('string');
            return 'number';
          },
          {nones: true}
        )
      ).toEqual(list(taggedValue('boolean', 'number'), 1, 2));
    });

    it('in: Maybe<Tagged<T>>', () => {
      const types = new Set(['none', 'string']);
      expect(
        mntTypeApply(
          maybe(taggedValue('boolean', 'string')),
          t => {
            expect(types.has(t as any)).toBe(true);
            types.delete(t as any);
            return 'number';
          },
          {nones: true}
        )
      ).toEqual(union(['number', taggedValue('boolean', 'number')]));
      expect(types.values.length).toEqual(0);
    });

    it('in: List<List<List<T>>>', () => {
      expect(
        mntTypeApply(
          list(list(list('string', 1, 2), 3, 4), 5, 6),
          t => {
            expect(t).toEqual('string');
            return 'number';
          },
          {nones: true}
        )
      ).toEqual(list(list(list('number', 1, 2), 3, 4), 5, 6));
    });

    it('in: Maybe<List<List<T>>>', () => {
      const types = new Set(['none', 'string']);
      expect(
        mntTypeApply(
          maybe(list(list('string', 1, 2), 3, 4)),
          t => {
            expect(types.has(t as any)).toBe(true);
            types.delete(t as any);
            return 'number';
          },
          {nones: true}
        )
      ).toEqual(union(['number', list(list('number', 1, 2), 3, 4)]));
      expect(types.values.length).toEqual(0);
    });

    it('in: Tagged<List<List<T>>>', () => {
      expect(
        mntTypeApply(
          taggedValue('boolean', list(list('string', 1, 2), 3, 4)),
          t => {
            expect(t).toEqual('string');
            return 'number';
          },
          {nones: true}
        )
      ).toEqual(taggedValue('boolean', list(list('number', 1, 2), 3, 4)));
    });

    it('in: List<Maybe<List<T>>>', () => {
      const types = new Set(['none', 'string']);
      expect(
        mntTypeApply(
          list(maybe(list('string', 1, 2)), 3, 4),
          t => {
            expect(types.has(t as any)).toBe(true);
            types.delete(t as any);
            return 'number';
          },
          {nones: true}
        )
      ).toEqual(list(union(['number', list('number', 1, 2)]), 3, 4));
      expect(types.values.length).toEqual(0);
    });

    it('in: Tagged<Maybe<List<T>>>', () => {
      const types = new Set(['none', 'string']);
      expect(
        mntTypeApply(
          taggedValue('boolean', maybe(list('string', 1, 2))),
          t => {
            expect(types.has(t as any)).toBe(true);
            types.delete(t as any);
            return 'number';
          },
          {nones: true}
        )
      ).toEqual(
        taggedValue('boolean', union(['number', list('number', 1, 2)]))
      );
      expect(types.values.length).toEqual(0);
    });

    it('in: List<Tagged<List<T>>>', () => {
      expect(
        mntTypeApply(
          list(taggedValue('boolean', list('string', 1, 2)), 5, 6),
          t => {
            expect(t).toEqual('string');
            return 'number';
          },
          {nones: true}
        )
      ).toEqual(list(taggedValue('boolean', list('number', 1, 2)), 5, 6));
    });

    it('in: Maybe<Tagged<List<T>>>', () => {
      const types = new Set(['none', 'string']);
      expect(
        mntTypeApply(
          maybe(taggedValue('boolean', list('string', 1, 2))),
          t => {
            expect(types.has(t as any)).toBe(true);
            types.delete(t as any);
            return 'number';
          },
          {nones: true}
        )
      ).toEqual(
        union(['number', taggedValue('boolean', list('number', 1, 2))])
      );
      expect(types.values.length).toEqual(0);
    });

    it('in: List<List<Maybe<T>>>', () => {
      const types = new Set(['none', 'string']);
      expect(
        mntTypeApply(
          list(list(maybe('string'), 1, 2), 3, 4),
          t => {
            expect(types.has(t as any)).toBe(true);
            types.delete(t as any);
            return 'number';
          },
          {nones: true}
        )
      ).toEqual(list(list('number', 1, 2), 3, 4));
      expect(types.values.length).toEqual(0);
    });

    it('in: Maybe<List<Maybe<T>>>', () => {
      const types = new Set(['none', 'string']);
      expect(
        mntTypeApply(
          maybe(list(maybe('string'), 1, 2)),
          t => {
            expect(types.has(t as any)).toBe(true);
            types.delete(t as any);
            return 'number';
          },
          {nones: true}
        )
      ).toEqual(union(['number', list('number', 1, 2)]));
      expect(types.values.length).toEqual(0);
    });

    it('in: Tagged<List<Maybe<T>>>', () => {
      const types = new Set(['none', 'string']);
      expect(
        mntTypeApply(
          taggedValue('boolean', list(maybe('string'), 1, 2)),
          t => {
            expect(types.has(t as any)).toBe(true);
            types.delete(t as any);
            return 'number';
          },
          {nones: true}
        )
      ).toEqual(taggedValue('boolean', list('number', 1, 2)));
      expect(types.values.length).toEqual(0);
    });

    it('in: List<Tagged<Maybe<T>>>', () => {
      const types = new Set(['none', 'string']);
      expect(
        mntTypeApply(
          list(taggedValue('boolean', maybe('string')), 1, 2),
          t => {
            expect(types.has(t as any)).toBe(true);
            types.delete(t as any);
            return 'number';
          },
          {nones: true}
        )
      ).toEqual(list(taggedValue('boolean', 'number'), 1, 2));
      expect(types.values.length).toEqual(0);
    });

    it('in: Maybe<Tagged<Maybe<T>>>', () => {
      const types = new Set(['none', 'string']);
      expect(
        mntTypeApply(
          maybe(taggedValue('boolean', maybe('string'))),
          t => {
            expect(types.has(t as any)).toBe(true);
            types.delete(t as any);
            return 'number';
          },
          {nones: true}
        )
      ).toEqual(union(['number', taggedValue('boolean', 'number')]));
      expect(types.values.length).toEqual(0);
    });

    it('in: List<List<Tagged<T>>>', () => {
      expect(
        mntTypeApply(
          list(list(taggedValue('boolean', 'string'), 1, 2), 3, 4),
          t => {
            expect(t).toEqual('string');
            return 'number';
          },
          {nones: true}
        )
      ).toEqual(list(list(taggedValue('boolean', 'number'), 1, 2), 3, 4));
    });

    it('in: Maybe<List<Tagged<T>>>', () => {
      const types = new Set(['none', 'string']);
      expect(
        mntTypeApply(
          maybe(list(taggedValue('boolean', 'string'), 1, 2)),
          t => {
            expect(types.has(t as any)).toBe(true);
            types.delete(t as any);
            return 'number';
          },
          {nones: true}
        )
      ).toEqual(
        union(['number', list(taggedValue('boolean', 'number'), 1, 2)])
      );
      expect(types.values.length).toEqual(0);
    });

    it('in: Tagged<List<Tagged<T>>>', () => {
      expect(
        mntTypeApply(
          taggedValue('boolean', list(taggedValue('run', 'string'), 1, 2)),
          t => {
            expect(t).toEqual('string');
            return 'number';
          },
          {nones: true}
        )
      ).toEqual(
        taggedValue('boolean', list(taggedValue('run', 'number'), 1, 2))
      );
    });

    it('in: List<Maybe<Tagged<T>>>', () => {
      const types = new Set(['none', 'string']);
      expect(
        mntTypeApply(
          list(maybe(taggedValue('boolean', 'string')), 1, 2),
          t => {
            expect(types.has(t as any)).toBe(true);
            types.delete(t as any);
            return 'number';
          },
          {nones: true}
        )
      ).toEqual(
        list(union(['number', taggedValue('boolean', 'number')]), 1, 2)
      );
      expect(types.values.length).toEqual(0);
    });

    it('in: Tagged<Maybe<Tagged<T>>>', () => {
      const types = new Set(['none', 'string']);
      expect(
        mntTypeApply(
          taggedValue('boolean', maybe(taggedValue('run', 'string'))),
          t => {
            expect(types.has(t as any)).toBe(true);
            types.delete(t as any);
            return 'number';
          },
          {nones: true}
        )
      ).toEqual(
        taggedValue('boolean', union(['number', taggedValue('run', 'number')]))
      );
      expect(types.values.length).toEqual(0);
    });
  });

  describe('(dims=0, tags=true, nones=false)', () => {
    /*
    Cases:
      T
      List<T>
      Maybe<T>
      Tagged<T>
      List<List<T>>
      Maybe<List<T>>
      Tagged<List<T>>
      List<Maybe<T>>
      Tagged<Maybe<T>>
      List<Tagged<T>>
      Maybe<Tagged<T>>
      List<List<List<T>>>
      Maybe<List<List<T>>>
      Tagged<List<List<T>>>
      List<Maybe<List<T>>>
      Tagged<Maybe<List<T>>>
      List<Tagged<List<T>>>
      Maybe<Tagged<List<T>>>
      List<List<Maybe<T>>>
      Maybe<List<Maybe<T>>>
      Tagged<List<Maybe<T>>>
      List<Tagged<Maybe<T>>>
      Maybe<Tagged<Maybe<T>>>
      List<List<Tagged<T>>>
      Maybe<List<Tagged<T>>>
      Tagged<List<Tagged<T>>>
      List<Maybe<Tagged<T>>>
      Tagged<Maybe<Tagged<T>>>
    */
    it('in: T', () => {
      expect(
        mntTypeApply(
          'string',
          t => {
            expect(t).toEqual('string');
            return 'number';
          },
          {tags: true}
        )
      ).toEqual('number');
    });

    it('in: List<T>', () => {
      expect(
        mntTypeApply(
          list('string', 1, 2),
          t => {
            expect(t).toEqual('string');
            return 'number';
          },
          {tags: true}
        )
      ).toEqual(list('number', 1, 2));
    });

    it('in: Maybe<T>', () => {
      expect(
        mntTypeApply(
          maybe('string'),
          t => {
            expect(t).toEqual('string');
            return 'number';
          },
          {tags: true}
        )
      ).toEqual(maybe('number'));
    });

    it('in: Tagged<T>', () => {
      expect(
        mntTypeApply(
          taggedValue('boolean', 'string'),
          t => {
            expect(t).toEqual(taggedValue('boolean', 'string'));
            return taggedValue('string', 'number');
          },
          {tags: true}
        )
      ).toEqual(taggedValue('string', 'number'));
    });

    it('in: List<List<T>>', () => {
      expect(
        mntTypeApply(
          list(list('string', 1, 2), 3, 4),
          t => {
            expect(t).toEqual('string');
            return 'number';
          },
          {tags: true}
        )
      ).toEqual(list(list('number', 1, 2), 3, 4));
    });

    it('in: Maybe<List<T>>', () => {
      expect(
        mntTypeApply(
          maybe(list('string', 1, 2)),
          t => {
            expect(t).toEqual('string');
            return 'number';
          },
          {tags: true}
        )
      ).toEqual(maybe(list('number', 1, 2)));
    });

    it('in: Tagged<List<T>>', () => {
      expect(
        mntTypeApply(
          taggedValue('boolean', list('string', 1, 2)),
          t => {
            expect(t).toEqual(taggedValue('boolean', 'string'));
            return taggedValue('string', 'number');
          },
          {tags: true}
        )
      ).toEqual(list(taggedValue('string', 'number'), 1, 2));
    });

    it('in: List<Maybe<T>>', () => {
      expect(
        mntTypeApply(
          list(maybe('string'), 1, 2),
          t => {
            expect(t).toEqual('string');
            return 'number';
          },
          {tags: true}
        )
      ).toEqual(list(maybe('number'), 1, 2));
    });

    it('in: Tagged<Maybe<T>>', () => {
      expect(
        mntTypeApply(
          taggedValue('boolean', maybe('string')),
          t => {
            expect(t).toEqual(taggedValue('boolean', 'string'));
            return taggedValue('string', 'number');
          },
          {tags: true}
        )
      ).toEqual(
        union([taggedValue('boolean', 'none'), taggedValue('string', 'number')])
      );
    });

    it('in: List<Tagged<T>>', () => {
      expect(
        mntTypeApply(
          list(taggedValue('boolean', 'string'), 1, 2),
          t => {
            expect(t).toEqual(taggedValue('boolean', 'string'));
            return taggedValue('string', 'number');
          },
          {tags: true}
        )
      ).toEqual(list(taggedValue('string', 'number'), 1, 2));
    });

    it('in: Maybe<Tagged<T>>', () => {
      expect(
        mntTypeApply(
          maybe(taggedValue('boolean', 'string')),
          t => {
            expect(t).toEqual(taggedValue('boolean', 'string'));
            return taggedValue('string', 'number');
          },
          {tags: true}
        )
      ).toEqual(maybe(taggedValue('string', 'number')));
    });

    it('in: List<List<List<T>>>', () => {
      expect(
        mntTypeApply(
          list(list(list('string', 1, 2), 3, 4), 5, 6),
          t => {
            expect(t).toEqual('string');
            return 'number';
          },
          {tags: true}
        )
      ).toEqual(list(list(list('number', 1, 2), 3, 4), 5, 6));
    });

    it('in: Maybe<List<List<T>>>', () => {
      expect(
        mntTypeApply(
          maybe(list(list('string', 1, 2), 3, 4)),
          t => {
            expect(t).toEqual('string');
            return 'number';
          },
          {tags: true}
        )
      ).toEqual(maybe(list(list('number', 1, 2), 3, 4)));
    });

    it('in: Tagged<List<List<T>>>', () => {
      expect(
        mntTypeApply(
          taggedValue('boolean', list(list('string', 1, 2), 3, 4)),
          t => {
            expect(t).toEqual(taggedValue('boolean', 'string'));
            return taggedValue('string', 'number');
          },
          {tags: true}
        )
      ).toEqual(list(list(taggedValue('string', 'number'), 1, 2), 3, 4));
    });

    it('in: List<Maybe<List<T>>>', () => {
      expect(
        mntTypeApply(
          list(maybe(list('string', 1, 2)), 3, 4),
          t => {
            expect(t).toEqual('string');
            return 'number';
          },
          {tags: true}
        )
      ).toEqual(list(maybe(list('number', 1, 2)), 3, 4));
    });

    it('in: Tagged<Maybe<List<T>>>', () => {
      expect(
        mntTypeApply(
          taggedValue('boolean', maybe(list('string', 1, 2))),
          t => {
            expect(t).toEqual(taggedValue('boolean', 'string'));
            return taggedValue('string', 'number');
          },
          {tags: true}
        )
      ).toEqual(
        union([
          taggedValue('boolean', 'none'),
          list(taggedValue('string', 'number'), 1, 2),
        ])
      );
    });

    it('in: List<Tagged<List<T>>>', () => {
      expect(
        mntTypeApply(
          list(taggedValue('boolean', list('string', 1, 2)), 5, 6),
          t => {
            expect(t).toEqual(taggedValue('boolean', 'string'));
            return taggedValue('string', 'number');
          },
          {tags: true}
        )
      ).toEqual(list(list(taggedValue('string', 'number'), 1, 2), 5, 6));
    });

    it('in: Maybe<Tagged<List<T>>>', () => {
      expect(
        mntTypeApply(
          maybe(taggedValue('boolean', list('string', 1, 2))),
          t => {
            expect(t).toEqual(taggedValue('boolean', 'string'));
            return taggedValue('string', 'number');
          },
          {tags: true}
        )
      ).toEqual(maybe(list(taggedValue('string', 'number'), 1, 2)));
    });

    it('in: List<List<Maybe<T>>>', () => {
      expect(
        mntTypeApply(
          list(list(maybe('string'), 1, 2), 3, 4),
          t => {
            expect(t).toEqual('string');
            return 'number';
          },
          {tags: true}
        )
      ).toEqual(list(list(maybe('number'), 1, 2), 3, 4));
    });

    it('in: Maybe<List<Maybe<T>>>', () => {
      expect(
        mntTypeApply(
          maybe(list(maybe('string'), 1, 2)),
          t => {
            expect(t).toEqual('string');
            return 'number';
          },
          {tags: true}
        )
      ).toEqual(maybe(list(maybe('number'), 1, 2)));
    });

    it('in: Tagged<List<Maybe<T>>>', () => {
      expect(
        mntTypeApply(
          taggedValue('boolean', list(maybe('string'), 1, 2)),
          t => {
            expect(t).toEqual(taggedValue('boolean', 'string'));
            return taggedValue('string', 'number');
          },
          {tags: true}
        )
      ).toEqual(
        list(
          union([
            taggedValue('boolean', 'none'),
            taggedValue('string', 'number'),
          ]),
          1,
          2
        )
      );
    });

    it('in: List<Tagged<Maybe<T>>>', () => {
      expect(
        mntTypeApply(
          list(taggedValue('boolean', maybe('string')), 1, 2),
          t => {
            expect(t).toEqual(taggedValue('boolean', 'string'));
            return taggedValue('string', 'number');
          },
          {tags: true}
        )
      ).toEqual(
        list(
          union([
            taggedValue('boolean', 'none'),
            taggedValue('string', 'number'),
          ]),
          1,
          2
        )
      );
    });

    it('in: Maybe<Tagged<Maybe<T>>>', () => {
      expect(
        mntTypeApply(
          maybe(taggedValue('boolean', maybe('string'))),
          t => {
            expect(t).toEqual(taggedValue('boolean', 'string'));
            return taggedValue('string', 'number');
          },
          {tags: true}
        )
      ).toEqual(
        maybe(
          union([
            taggedValue('boolean', 'none'),
            taggedValue('string', 'number'),
          ])
        )
      );
    });

    it('in: List<List<Tagged<T>>>', () => {
      expect(
        mntTypeApply(
          list(list(taggedValue('boolean', 'string'), 1, 2), 3, 4),
          t => {
            expect(t).toEqual(taggedValue('boolean', 'string'));
            return taggedValue('string', 'number');
          },
          {tags: true}
        )
      ).toEqual(list(list(taggedValue('string', 'number'), 1, 2), 3, 4));
    });

    it('in: Maybe<List<Tagged<T>>>', () => {
      expect(
        mntTypeApply(
          maybe(list(taggedValue('boolean', 'string'), 1, 2)),
          t => {
            expect(t).toEqual(taggedValue('boolean', 'string'));
            return taggedValue('string', 'number');
          },
          {tags: true}
        )
      ).toEqual(maybe(list(taggedValue('string', 'number'), 1, 2)));
    });

    it('in: Tagged<List<Tagged<T>>>', () => {
      expect(
        mntTypeApply(
          taggedValue('boolean', list(taggedValue('run', 'string'), 1, 2)),
          t => {
            expect(t).toEqual(
              taggedValue(taggedValue('boolean', 'run'), 'string')
            );
            return taggedValue('string', 'number');
          },
          {tags: true}
        )
      ).toEqual(list(taggedValue('string', 'number'), 1, 2));
    });

    it('in: List<Maybe<Tagged<T>>>', () => {
      expect(
        mntTypeApply(
          list(maybe(taggedValue('boolean', 'string')), 1, 2),
          t => {
            expect(t).toEqual(taggedValue('boolean', 'string'));
            return taggedValue('string', 'number');
          },
          {tags: true}
        )
      ).toEqual(list(maybe(taggedValue('string', 'number')), 1, 2));
    });

    it('in: Tagged<Maybe<Tagged<T>>>', () => {
      expect(
        mntTypeApply(
          taggedValue('boolean', maybe(taggedValue('run', 'string'))),
          t => {
            expect(t).toEqual(
              taggedValue(taggedValue('boolean', 'run'), 'string')
            );
            return taggedValue('string', 'number');
          },
          {tags: true}
        )
      ).toEqual(
        union([taggedValue('boolean', 'none'), taggedValue('string', 'number')])
      );
    });
  });

  describe('(dims=1, tags=false, nones=false)', () => {
    /*
    Cases:
      T
      List<T>
      Maybe<T>
      Tagged<T>
      List<List<T>>
      Maybe<List<T>>
      Tagged<List<T>>
      List<Maybe<T>>
      Tagged<Maybe<T>>
      List<Tagged<T>>
      Maybe<Tagged<T>>
      List<List<List<T>>>
      Maybe<List<List<T>>>
      Tagged<List<List<T>>>
      List<Maybe<List<T>>>
      Tagged<Maybe<List<T>>>
      List<Tagged<List<T>>>
      Maybe<Tagged<List<T>>>
      List<List<Maybe<T>>>
      Maybe<List<Maybe<T>>>
      Tagged<List<Maybe<T>>>
      List<Tagged<Maybe<T>>>
      Maybe<Tagged<Maybe<T>>>
      List<List<Tagged<T>>>
      Maybe<List<Tagged<T>>>
      Tagged<List<Tagged<T>>>
      List<Maybe<Tagged<T>>>
      Tagged<Maybe<Tagged<T>>>
    */
    it('in: T', () => {
      expect(
        mntTypeApply(
          'string',
          t => {
            return 'number';
          },
          {dims: 1}
        )
      ).toEqual(
        'invalid' // invalid input
      );
    });

    it('in: List<T>', () => {
      expect(
        mntTypeApply(
          list('string', 1, 2),
          t => {
            expect(t).toEqual(list('string', 1, 2));
            return 'number';
          },
          {dims: 1}
        )
      ).toEqual('number');
    });

    it('in: Maybe<T>', () => {
      expect(
        mntTypeApply(
          maybe('string'),
          t => {
            return 'number';
          },
          {dims: 1}
        )
      ).toEqual(
        'invalid' // invalid input
      );
    });

    it('in: Tagged<T>', () => {
      expect(
        mntTypeApply(
          taggedValue('boolean', 'string'),
          t => {
            return 'number';
          },
          {dims: 1}
        )
      ).toEqual(
        'invalid' // invalid input
      );
    });

    it('in: List<List<T>>', () => {
      expect(
        mntTypeApply(
          list(list('string', 1, 2), 3, 4),
          t => {
            expect(t).toEqual(list('string', 1, 2));
            return 'number';
          },
          {dims: 1}
        )
      ).toEqual(list('number', 3, 4));
    });

    it('in: Maybe<List<T>>', () => {
      expect(
        mntTypeApply(
          maybe(list('string', 1, 2)),
          t => {
            expect(t).toEqual(list('string', 1, 2));
            return 'number';
          },
          {dims: 1}
        )
      ).toEqual(maybe('number'));
    });

    it('in: Tagged<List<T>>', () => {
      expect(
        mntTypeApply(
          taggedValue('boolean', list('string', 1, 2)),
          t => {
            expect(t).toEqual(list('string', 1, 2));
            return 'number';
          },
          {dims: 1}
        )
      ).toEqual(taggedValue('boolean', 'number'));
    });

    it('in: List<Maybe<T>>', () => {
      expect(
        mntTypeApply(
          list(maybe('string'), 1, 2),
          t => {
            expect(t).toEqual(list(maybe('string'), 1, 2));
            return 'number';
          },
          {dims: 1}
        )
      ).toEqual('number');
    });

    it('in: Tagged<Maybe<T>>', () => {
      expect(
        mntTypeApply(
          taggedValue('boolean', maybe('string')),
          t => {
            return 'number';
          },
          {dims: 1}
        )
      ).toEqual(
        'invalid' // invalid input
      );
    });

    it('in: List<Tagged<T>>', () => {
      expect(
        mntTypeApply(
          list(taggedValue('boolean', 'string'), 1, 2),
          t => {
            expect(t).toEqual(list(taggedValue('boolean', 'string'), 1, 2));
            return 'number';
          },
          {dims: 1}
        )
      ).toEqual('number');
    });

    it('in: Maybe<Tagged<T>>', () => {
      expect(
        mntTypeApply(
          maybe(taggedValue('boolean', 'string')),
          t => {
            return 'number';
          },
          {dims: 1}
        )
      ).toEqual(
        'invalid' // invalid input
      );
    });

    it('in: List<List<List<T>>>', () => {
      expect(
        mntTypeApply(
          list(list(list('string', 1, 2), 3, 4), 5, 6),
          t => {
            expect(t).toEqual(list('string', 1, 2));
            return 'number';
          },
          {dims: 1}
        )
      ).toEqual(list(list('number', 3, 4), 5, 6));
    });

    it('in: Maybe<List<List<T>>>', () => {
      expect(
        mntTypeApply(
          maybe(list(list('string', 1, 2), 3, 4)),
          t => {
            expect(t).toEqual(list('string', 1, 2));
            return 'number';
          },
          {dims: 1}
        )
      ).toEqual(maybe(list('number', 3, 4)));
    });

    it('in: Tagged<List<List<T>>>', () => {
      expect(
        mntTypeApply(
          taggedValue('boolean', list(list('string', 1, 2), 3, 4)),
          t => {
            expect(t).toEqual(list('string', 1, 2));
            return 'number';
          },
          {dims: 1}
        )
      ).toEqual(taggedValue('boolean', list('number', 3, 4)));
    });

    it('in: List<Maybe<List<T>>>', () => {
      expect(
        mntTypeApply(
          list(maybe(list('string', 1, 2)), 3, 4),
          t => {
            expect(t).toEqual(list('string', 1, 2));
            return 'number';
          },
          {dims: 1}
        )
      ).toEqual(list(maybe('number'), 3, 4));
    });

    it('in: Tagged<Maybe<List<T>>>', () => {
      expect(
        mntTypeApply(
          taggedValue('boolean', maybe(list('string', 1, 2))),
          t => {
            expect(t).toEqual(list('string', 1, 2));
            return 'number';
          },
          {dims: 1}
        )
      ).toEqual(taggedValue('boolean', maybe('number')));
    });

    it('in: List<Tagged<List<T>>>', () => {
      expect(
        mntTypeApply(
          list(taggedValue('boolean', list('string', 1, 2)), 5, 6),
          t => {
            expect(t).toEqual(list('string', 1, 2));
            return 'number';
          },
          {dims: 1}
        )
      ).toEqual(list(taggedValue('boolean', 'number'), 5, 6));
    });

    it('in: Maybe<Tagged<List<T>>>', () => {
      expect(
        mntTypeApply(
          maybe(taggedValue('boolean', list('string', 1, 2))),
          t => {
            expect(t).toEqual(list('string', 1, 2));
            return 'number';
          },
          {dims: 1}
        )
      ).toEqual(maybe(taggedValue('boolean', 'number')));
    });

    it('in: List<List<Maybe<T>>>', () => {
      expect(
        mntTypeApply(
          list(list(maybe('string'), 1, 2), 3, 4),
          t => {
            expect(t).toEqual(list(maybe('string'), 1, 2));
            return 'number';
          },
          {dims: 1}
        )
      ).toEqual(list('number', 3, 4));
    });

    it('in: Maybe<List<Maybe<T>>>', () => {
      expect(
        mntTypeApply(
          maybe(list(maybe('string'), 1, 2)),
          t => {
            expect(t).toEqual(list(maybe('string'), 1, 2));
            return 'number';
          },
          {dims: 1}
        )
      ).toEqual(maybe('number'));
    });

    it('in: Tagged<List<Maybe<T>>>', () => {
      expect(
        mntTypeApply(
          taggedValue('boolean', list(maybe('string'), 1, 2)),
          t => {
            expect(t).toEqual(list(maybe('string'), 1, 2));
            return 'number';
          },
          {dims: 1}
        )
      ).toEqual(taggedValue('boolean', 'number'));
    });

    it('in: List<Tagged<Maybe<T>>>', () => {
      expect(
        mntTypeApply(
          list(taggedValue('boolean', maybe('string')), 1, 2),
          t => {
            expect(t).toEqual(
              list(taggedValue('boolean', maybe('string')), 1, 2)
            );
            return 'number';
          },
          {dims: 1}
        )
      ).toEqual('number');
    });

    it('in: Maybe<Tagged<Maybe<T>>>', () => {
      expect(
        mntTypeApply(
          maybe(taggedValue('boolean', maybe('string'))),
          t => {
            return 'number';
          },
          {dims: 1}
        )
      ).toEqual(
        'invalid' // invalid input
      );
    });

    it('in: List<List<Tagged<T>>>', () => {
      expect(
        mntTypeApply(
          list(list(taggedValue('boolean', 'string'), 1, 2), 3, 4),
          t => {
            expect(t).toEqual(list(taggedValue('boolean', 'string'), 1, 2));
            return 'number';
          },
          {dims: 1}
        )
      ).toEqual(list('number', 3, 4));
    });

    it('in: Maybe<List<Tagged<T>>>', () => {
      expect(
        mntTypeApply(
          maybe(list(taggedValue('boolean', 'string'), 1, 2)),
          t => {
            expect(t).toEqual(list(taggedValue('boolean', 'string'), 1, 2));
            return 'number';
          },
          {dims: 1}
        )
      ).toEqual(maybe('number'));
    });

    it('in: Tagged<List<Tagged<T>>>', () => {
      expect(
        mntTypeApply(
          taggedValue('boolean', list(taggedValue('run', 'string'), 1, 2)),
          t => {
            expect(t).toEqual(list(taggedValue('run', 'string'), 1, 2));
            return 'number';
          },
          {dims: 1}
        )
      ).toEqual(taggedValue('boolean', 'number'));
    });

    it('in: List<Maybe<Tagged<T>>>', () => {
      expect(
        mntTypeApply(
          list(maybe(taggedValue('boolean', 'string')), 1, 2),
          t => {
            expect(t).toEqual(
              list(maybe(taggedValue('boolean', 'string')), 1, 2)
            );
            return 'number';
          },
          {dims: 1}
        )
      ).toEqual('number');
    });

    it('in: Tagged<Maybe<Tagged<T>>>', () => {
      expect(
        mntTypeApply(
          taggedValue('boolean', maybe(taggedValue('run', 'string'))),
          t => {
            return 'number';
          },
          {dims: 1}
        )
      ).toEqual(
        'invalid' // invalid input
      );
    });
  });
});

describe('mntTypeStrip', () => {
  describe('(dims=0, tags=false, nones=false)', () => {
    /*
    Cases:
      T
      List<T>
      Maybe<T>
      Tagged<T>
      List<List<T>>
      Maybe<List<T>>
      Tagged<List<T>>
      List<Maybe<T>>
      Tagged<Maybe<T>>
      List<Tagged<T>>
      Maybe<Tagged<T>>
      List<List<List<T>>>
      Maybe<List<List<T>>>
      Tagged<List<List<T>>>
      List<Maybe<List<T>>>
      Tagged<Maybe<List<T>>>
      List<Tagged<List<T>>>
      Maybe<Tagged<List<T>>>
      List<List<Maybe<T>>>
      Maybe<List<Maybe<T>>>
      Tagged<List<Maybe<T>>>
      List<Tagged<Maybe<T>>>
      Maybe<Tagged<Maybe<T>>>
      List<List<Tagged<T>>>
      Maybe<List<Tagged<T>>>
      Tagged<List<Tagged<T>>>
      List<Maybe<Tagged<T>>>
      Tagged<Maybe<Tagged<T>>>
    */
    it('in: T', () => {
      expect(mntTypeStrip('string')).toEqual('string');
    });

    it('in: List<T>', () => {
      expect(mntTypeStrip(list('string', 1, 2))).toEqual('string');
    });

    it('in: Maybe<T>', () => {
      expect(mntTypeStrip(maybe('string'))).toEqual('string');
    });

    it('in: Tagged<T>', () => {
      expect(mntTypeStrip(taggedValue('boolean', 'string'))).toEqual('string');
    });

    it('in: List<List<T>>', () => {
      expect(mntTypeStrip(list(list('string', 1, 2), 3, 4))).toEqual('string');
    });

    it('in: Maybe<List<T>>', () => {
      expect(mntTypeStrip(maybe(list('string', 1, 2)))).toEqual('string');
    });

    it('in: Tagged<List<T>>', () => {
      expect(
        mntTypeStrip(taggedValue('boolean', list('string', 1, 2)))
      ).toEqual('string');
    });

    it('in: List<Maybe<T>>', () => {
      expect(mntTypeStrip(list(maybe('string'), 1, 2))).toEqual('string');
    });

    it('in: Tagged<Maybe<T>>', () => {
      expect(mntTypeStrip(taggedValue('boolean', maybe('string')))).toEqual(
        'string'
      );
    });

    it('in: List<Tagged<T>>', () => {
      expect(
        mntTypeStrip(list(taggedValue('boolean', 'string'), 1, 2))
      ).toEqual('string');
    });

    it('in: Maybe<Tagged<T>>', () => {
      expect(mntTypeStrip(maybe(taggedValue('boolean', 'string')))).toEqual(
        'string'
      );
    });

    it('in: List<List<List<T>>>', () => {
      expect(
        mntTypeStrip(list(list(list('string', 1, 2), 3, 4), 5, 6))
      ).toEqual('string');
    });

    it('in: Maybe<List<List<T>>>', () => {
      expect(mntTypeStrip(maybe(list(list('string', 1, 2), 3, 4)))).toEqual(
        'string'
      );
    });

    it('in: Tagged<List<List<T>>>', () => {
      expect(
        mntTypeStrip(taggedValue('boolean', list(list('string', 1, 2), 3, 4)))
      ).toEqual('string');
    });

    it('in: List<Maybe<List<T>>>', () => {
      expect(mntTypeStrip(list(maybe(list('string', 1, 2)), 3, 4))).toEqual(
        'string'
      );
    });

    it('in: Tagged<Maybe<List<T>>>', () => {
      expect(
        mntTypeStrip(taggedValue('boolean', maybe(list('string', 1, 2))))
      ).toEqual('string');
    });

    it('in: List<Tagged<List<T>>>', () => {
      expect(
        mntTypeStrip(list(taggedValue('boolean', list('string', 1, 2)), 5, 6))
      ).toEqual('string');
    });

    it('in: Maybe<Tagged<List<T>>>', () => {
      expect(
        mntTypeStrip(maybe(taggedValue('boolean', list('string', 1, 2))))
      ).toEqual('string');
    });

    it('in: List<List<Maybe<T>>>', () => {
      expect(mntTypeStrip(list(list(maybe('string'), 1, 2), 3, 4))).toEqual(
        'string'
      );
    });

    it('in: Maybe<List<Maybe<T>>>', () => {
      expect(mntTypeStrip(maybe(list(maybe('string'), 1, 2)))).toEqual(
        'string'
      );
    });

    it('in: Tagged<List<Maybe<T>>>', () => {
      expect(
        mntTypeStrip(taggedValue('boolean', list(maybe('string'), 1, 2)))
      ).toEqual('string');
    });

    it('in: List<Tagged<Maybe<T>>>', () => {
      expect(
        mntTypeStrip(list(taggedValue('boolean', maybe('string')), 1, 2))
      ).toEqual('string');
    });

    it('in: Maybe<Tagged<Maybe<T>>>', () => {
      expect(
        mntTypeStrip(maybe(taggedValue('boolean', maybe('string'))))
      ).toEqual('string');
    });

    it('in: List<List<Tagged<T>>>', () => {
      expect(
        mntTypeStrip(list(list(taggedValue('boolean', 'string'), 1, 2), 3, 4))
      ).toEqual('string');
    });

    it('in: Maybe<List<Tagged<T>>>', () => {
      expect(
        mntTypeStrip(maybe(list(taggedValue('boolean', 'string'), 1, 2)))
      ).toEqual('string');
    });

    it('in: Tagged<List<Tagged<T>>>', () => {
      expect(
        mntTypeStrip(
          taggedValue('boolean', list(taggedValue('run', 'string'), 1, 2))
        )
      ).toEqual('string');
    });

    it('in: List<Maybe<Tagged<T>>>', () => {
      expect(
        mntTypeStrip(list(maybe(taggedValue('boolean', 'string')), 1, 2))
      ).toEqual('string');
    });

    it('in: Tagged<Maybe<Tagged<T>>>', () => {
      expect(
        mntTypeStrip(
          taggedValue('boolean', maybe(taggedValue('run', 'string')))
        )
      ).toEqual('string');
    });
  });

  describe('(dims=0, tags=false, nones=true)', () => {
    /*
    Cases:
      T
      List<T>
      Maybe<T>
      Tagged<T>
      List<List<T>>
      Maybe<List<T>>
      Tagged<List<T>>
      List<Maybe<T>>
      Tagged<Maybe<T>>
      List<Tagged<T>>
      Maybe<Tagged<T>>
      List<List<List<T>>>
      Maybe<List<List<T>>>
      Tagged<List<List<T>>>
      List<Maybe<List<T>>>
      Tagged<Maybe<List<T>>>
      List<Tagged<List<T>>>
      Maybe<Tagged<List<T>>>
      List<List<Maybe<T>>>
      Maybe<List<Maybe<T>>>
      Tagged<List<Maybe<T>>>
      List<Tagged<Maybe<T>>>
      Maybe<Tagged<Maybe<T>>>
      List<List<Tagged<T>>>
      Maybe<List<Tagged<T>>>
      Tagged<List<Tagged<T>>>
      List<Maybe<Tagged<T>>>
      Tagged<Maybe<Tagged<T>>>
    */
    it('in: T', () => {
      expect(mntTypeStrip('string', {nones: true})).toEqual('string');
    });

    it('in: List<T>', () => {
      expect(
        mntTypeStrip(list('string', 1, 2), {
          nones: true,
        })
      ).toEqual('string');
    });

    it('in: Maybe<T>', () => {
      expect(mntTypeStrip(maybe('string'), {nones: true})).toEqual(
        maybe('string')
      );
    });

    it('in: Tagged<T>', () => {
      expect(
        mntTypeStrip(taggedValue('boolean', 'string'), {
          nones: true,
        })
      ).toEqual('string');
    });

    it('in: List<List<T>>', () => {
      expect(
        mntTypeStrip(list(list('string', 1, 2), 3, 4), {
          nones: true,
        })
      ).toEqual('string');
    });

    it('in: Maybe<List<T>>', () => {
      expect(
        mntTypeStrip(maybe(list('string', 1, 2)), {
          nones: true,
        })
      ).toEqual(maybe('string'));
    });

    it('in: Tagged<List<T>>', () => {
      expect(
        mntTypeStrip(taggedValue('boolean', list('string', 1, 2)), {
          nones: true,
        })
      ).toEqual('string');
    });

    it('in: List<Maybe<T>>', () => {
      expect(
        mntTypeStrip(list(maybe('string'), 1, 2), {
          nones: true,
        })
      ).toEqual(maybe('string'));
    });

    it('in: Tagged<Maybe<T>>', () => {
      expect(
        mntTypeStrip(taggedValue('boolean', maybe('string')), {
          nones: true,
        })
      ).toEqual(maybe('string'));
    });

    it('in: List<Tagged<T>>', () => {
      expect(
        mntTypeStrip(list(taggedValue('boolean', 'string'), 1, 2), {
          nones: true,
        })
      ).toEqual('string');
    });

    it('in: Maybe<Tagged<T>>', () => {
      expect(
        mntTypeStrip(maybe(taggedValue('boolean', 'string')), {
          nones: true,
        })
      ).toEqual(maybe('string'));
    });

    it('in: List<List<List<T>>>', () => {
      expect(
        mntTypeStrip(list(list(list('string', 1, 2), 3, 4), 5, 6), {
          nones: true,
        })
      ).toEqual('string');
    });

    it('in: Maybe<List<List<T>>>', () => {
      expect(
        mntTypeStrip(maybe(list(list('string', 1, 2), 3, 4)), {
          nones: true,
        })
      ).toEqual(maybe('string'));
    });

    it('in: Tagged<List<List<T>>>', () => {
      expect(
        mntTypeStrip(taggedValue('boolean', list(list('string', 1, 2), 3, 4)), {
          nones: true,
        })
      ).toEqual('string');
    });

    it('in: List<Maybe<List<T>>>', () => {
      expect(
        mntTypeStrip(list(maybe(list('string', 1, 2)), 3, 4), {
          nones: true,
        })
      ).toEqual(maybe('string'));
    });

    it('in: Tagged<Maybe<List<T>>>', () => {
      expect(
        mntTypeStrip(taggedValue('boolean', maybe(list('string', 1, 2))), {
          nones: true,
        })
      ).toEqual(maybe('string'));
    });

    it('in: List<Tagged<List<T>>>', () => {
      expect(
        mntTypeStrip(list(taggedValue('boolean', list('string', 1, 2)), 5, 6), {
          nones: true,
        })
      ).toEqual('string');
    });

    it('in: Maybe<Tagged<List<T>>>', () => {
      expect(
        mntTypeStrip(maybe(taggedValue('boolean', list('string', 1, 2))), {
          nones: true,
        })
      ).toEqual(maybe('string'));
    });

    it('in: List<List<Maybe<T>>>', () => {
      expect(
        mntTypeStrip(list(list(maybe('string'), 1, 2), 3, 4), {
          nones: true,
        })
      ).toEqual(maybe('string'));
    });

    it('in: Maybe<List<Maybe<T>>>', () => {
      expect(
        mntTypeStrip(maybe(list(maybe('string'), 1, 2)), {nones: true})
      ).toEqual(maybe('string'));
    });

    it('in: Tagged<List<Maybe<T>>>', () => {
      expect(
        mntTypeStrip(taggedValue('boolean', list(maybe('string'), 1, 2)), {
          nones: true,
        })
      ).toEqual(maybe('string'));
    });

    it('in: List<Tagged<Maybe<T>>>', () => {
      expect(
        mntTypeStrip(list(taggedValue('boolean', maybe('string')), 1, 2), {
          nones: true,
        })
      ).toEqual(maybe('string'));
    });

    it('in: Maybe<Tagged<Maybe<T>>>', () => {
      expect(
        mntTypeStrip(maybe(taggedValue('boolean', maybe('string'))), {
          nones: true,
        })
      ).toEqual(maybe('string'));
    });

    it('in: List<List<Tagged<T>>>', () => {
      expect(
        mntTypeStrip(list(list(taggedValue('boolean', 'string'), 1, 2), 3, 4), {
          nones: true,
        })
      ).toEqual('string');
    });

    it('in: Maybe<List<Tagged<T>>>', () => {
      expect(
        mntTypeStrip(maybe(list(taggedValue('boolean', 'string'), 1, 2)), {
          nones: true,
        })
      ).toEqual(maybe('string'));
    });

    it('in: Tagged<List<Tagged<T>>>', () => {
      expect(
        mntTypeStrip(
          taggedValue('boolean', list(taggedValue('run', 'string'), 1, 2)),
          {nones: true}
        )
      ).toEqual('string');
    });

    it('in: List<Maybe<Tagged<T>>>', () => {
      expect(
        mntTypeStrip(list(maybe(taggedValue('boolean', 'string')), 1, 2), {
          nones: true,
        })
      ).toEqual(maybe('string'));
    });

    it('in: Tagged<Maybe<Tagged<T>>>', () => {
      expect(
        mntTypeStrip(
          taggedValue('boolean', maybe(taggedValue('run', 'string'))),
          {nones: true}
        )
      ).toEqual(maybe('string'));
    });
  });

  describe('(dims=0, tags=true, nones=false)', () => {
    /*
    Cases:
      T
      List<T>
      Maybe<T>
      Tagged<T>
      List<List<T>>
      Maybe<List<T>>
      Tagged<List<T>>
      List<Maybe<T>>
      Tagged<Maybe<T>>
      List<Tagged<T>>
      Maybe<Tagged<T>>
      List<List<List<T>>>
      Maybe<List<List<T>>>
      Tagged<List<List<T>>>
      List<Maybe<List<T>>>
      Tagged<Maybe<List<T>>>
      List<Tagged<List<T>>>
      Maybe<Tagged<List<T>>>
      List<List<Maybe<T>>>
      Maybe<List<Maybe<T>>>
      Tagged<List<Maybe<T>>>
      List<Tagged<Maybe<T>>>
      Maybe<Tagged<Maybe<T>>>
      List<List<Tagged<T>>>
      Maybe<List<Tagged<T>>>
      Tagged<List<Tagged<T>>>
      List<Maybe<Tagged<T>>>
      Tagged<Maybe<Tagged<T>>>
    */
    it('in: T', () => {
      expect(mntTypeStrip('string', {tags: true})).toEqual('string');
    });

    it('in: List<T>', () => {
      expect(
        mntTypeStrip(list('string', 1, 2), {
          tags: true,
        })
      ).toEqual('string');
    });

    it('in: Maybe<T>', () => {
      expect(mntTypeStrip(maybe('string'), {tags: true})).toEqual('string');
    });

    it('in: Tagged<T>', () => {
      expect(
        mntTypeStrip(taggedValue('boolean', 'string'), {
          tags: true,
        })
      ).toEqual(taggedValue('boolean', 'string'));
    });

    it('in: List<List<T>>', () => {
      expect(
        mntTypeStrip(list(list('string', 1, 2), 3, 4), {
          tags: true,
        })
      ).toEqual('string');
    });

    it('in: Maybe<List<T>>', () => {
      expect(
        mntTypeStrip(maybe(list('string', 1, 2)), {
          tags: true,
        })
      ).toEqual('string');
    });

    it('in: Tagged<List<T>>', () => {
      expect(
        mntTypeStrip(taggedValue('boolean', list('string', 1, 2)), {
          tags: true,
        })
      ).toEqual(taggedValue('boolean', 'string'));
    });

    it('in: List<Maybe<T>>', () => {
      expect(
        mntTypeStrip(list(maybe('string'), 1, 2), {
          tags: true,
        })
      ).toEqual('string');
    });

    it('in: Tagged<Maybe<T>>', () => {
      expect(
        mntTypeStrip(taggedValue('boolean', maybe('string')), {
          tags: true,
        })
      ).toEqual(taggedValue('boolean', 'string'));
    });

    it('in: List<Tagged<T>>', () => {
      expect(
        mntTypeStrip(list(taggedValue('boolean', 'string'), 1, 2), {
          tags: true,
        })
      ).toEqual(taggedValue('boolean', 'string'));
    });

    it('in: Maybe<Tagged<T>>', () => {
      expect(
        mntTypeStrip(maybe(taggedValue('boolean', 'string')), {
          tags: true,
        })
      ).toEqual(taggedValue('boolean', 'string'));
    });

    it('in: List<List<List<T>>>', () => {
      expect(
        mntTypeStrip(list(list(list('string', 1, 2), 3, 4), 5, 6), {
          tags: true,
        })
      ).toEqual('string');
    });

    it('in: Maybe<List<List<T>>>', () => {
      expect(
        mntTypeStrip(maybe(list(list('string', 1, 2), 3, 4)), {
          tags: true,
        })
      ).toEqual('string');
    });

    it('in: Tagged<List<List<T>>>', () => {
      expect(
        mntTypeStrip(taggedValue('boolean', list(list('string', 1, 2), 3, 4)), {
          tags: true,
        })
      ).toEqual(taggedValue('boolean', 'string'));
    });

    it('in: List<Maybe<List<T>>>', () => {
      expect(
        mntTypeStrip(list(maybe(list('string', 1, 2)), 3, 4), {
          tags: true,
        })
      ).toEqual('string');
    });

    it('in: Tagged<Maybe<List<T>>>', () => {
      expect(
        mntTypeStrip(taggedValue('boolean', maybe(list('string', 1, 2))), {
          tags: true,
        })
      ).toEqual(taggedValue('boolean', 'string'));
    });

    it('in: List<Tagged<List<T>>>', () => {
      expect(
        mntTypeStrip(list(taggedValue('boolean', list('string', 1, 2)), 5, 6), {
          tags: true,
        })
      ).toEqual(taggedValue('boolean', 'string'));
    });

    it('in: Maybe<Tagged<List<T>>>', () => {
      expect(
        mntTypeStrip(maybe(taggedValue('boolean', list('string', 1, 2))), {
          tags: true,
        })
      ).toEqual(taggedValue('boolean', 'string'));
    });

    it('in: List<List<Maybe<T>>>', () => {
      expect(
        mntTypeStrip(list(list(maybe('string'), 1, 2), 3, 4), {
          tags: true,
        })
      ).toEqual('string');
    });

    it('in: Maybe<List<Maybe<T>>>', () => {
      expect(
        mntTypeStrip(maybe(list(maybe('string'), 1, 2)), {tags: true})
      ).toEqual('string');
    });

    it('in: Tagged<List<Maybe<T>>>', () => {
      expect(
        mntTypeStrip(taggedValue('boolean', list(maybe('string'), 1, 2)), {
          tags: true,
        })
      ).toEqual(taggedValue('boolean', 'string'));
    });

    it('in: List<Tagged<Maybe<T>>>', () => {
      expect(
        mntTypeStrip(list(taggedValue('boolean', maybe('string')), 1, 2), {
          tags: true,
        })
      ).toEqual(taggedValue('boolean', 'string'));
    });

    it('in: Maybe<Tagged<Maybe<T>>>', () => {
      expect(
        mntTypeStrip(maybe(taggedValue('boolean', maybe('string'))), {
          tags: true,
        })
      ).toEqual(taggedValue('boolean', 'string'));
    });

    it('in: List<List<Tagged<T>>>', () => {
      expect(
        mntTypeStrip(list(list(taggedValue('boolean', 'string'), 1, 2), 3, 4), {
          tags: true,
        })
      ).toEqual(taggedValue('boolean', 'string'));
    });

    it('in: Maybe<List<Tagged<T>>>', () => {
      expect(
        mntTypeStrip(maybe(list(taggedValue('boolean', 'string'), 1, 2)), {
          tags: true,
        })
      ).toEqual(taggedValue('boolean', 'string'));
    });

    it('in: Tagged<List<Tagged<T>>>', () => {
      expect(
        mntTypeStrip(
          taggedValue('boolean', list(taggedValue('run', 'string'), 1, 2)),
          {tags: true}
        )
      ).toEqual(taggedValue(taggedValue('boolean', 'run'), 'string'));
    });

    it('in: List<Maybe<Tagged<T>>>', () => {
      expect(
        mntTypeStrip(list(maybe(taggedValue('boolean', 'string')), 1, 2), {
          tags: true,
        })
      ).toEqual(taggedValue('boolean', 'string'));
    });

    it('in: Tagged<Maybe<Tagged<T>>>', () => {
      expect(
        mntTypeStrip(
          taggedValue('boolean', maybe(taggedValue('run', 'string'))),
          {tags: true}
        )
      ).toEqual(taggedValue(taggedValue('boolean', 'run'), 'string'));
    });
  });

  describe('(dims=1, tags=false, nones=false)', () => {
    /*
    Cases:
      T
      List<T>
      Maybe<T>
      Tagged<T>
      List<List<T>>
      Maybe<List<T>>
      Tagged<List<T>>
      List<Maybe<T>>
      Tagged<Maybe<T>>
      List<Tagged<T>>
      Maybe<Tagged<T>>
      List<List<List<T>>>
      Maybe<List<List<T>>>
      Tagged<List<List<T>>>
      List<Maybe<List<T>>>
      Tagged<Maybe<List<T>>>
      List<Tagged<List<T>>>
      Maybe<Tagged<List<T>>>
      List<List<Maybe<T>>>
      Maybe<List<Maybe<T>>>
      Tagged<List<Maybe<T>>>
      List<Tagged<Maybe<T>>>
      Maybe<Tagged<Maybe<T>>>
      List<List<Tagged<T>>>
      Maybe<List<Tagged<T>>>
      Tagged<List<Tagged<T>>>
      List<Maybe<Tagged<T>>>
      Tagged<Maybe<Tagged<T>>>
    */
    it('in: T', () => {
      expect(mntTypeStrip('string', {dims: 1})).toEqual(
        'invalid' // invalid input
      );
    });

    it('in: List<T>', () => {
      expect(mntTypeStrip(list('string', 1, 2), {dims: 1})).toEqual(
        list('string', 1, 2)
      );
    });

    it('in: Maybe<T>', () => {
      expect(mntTypeStrip(maybe('string'), {dims: 1})).toEqual(
        'invalid' // invalid input
      );
    });

    it('in: Tagged<T>', () => {
      expect(
        mntTypeStrip(taggedValue('boolean', 'string'), {
          dims: 1,
        })
      ).toEqual(
        'invalid' // invalid input
      );
    });

    it('in: List<List<T>>', () => {
      expect(
        mntTypeStrip(list(list('string', 1, 2), 3, 4), {
          dims: 1,
        })
      ).toEqual(list('string', 1, 2));
    });

    it('in: Maybe<List<T>>', () => {
      expect(mntTypeStrip(maybe(list('string', 1, 2)), {dims: 1})).toEqual(
        list('string', 1, 2)
      );
    });

    it('in: Tagged<List<T>>', () => {
      expect(
        mntTypeStrip(taggedValue('boolean', list('string', 1, 2)), {
          dims: 1,
        })
      ).toEqual(list('string', 1, 2));
    });

    it('in: List<Maybe<T>>', () => {
      expect(mntTypeStrip(list(maybe('string'), 1, 2), {dims: 1})).toEqual(
        list(maybe('string'), 1, 2)
      );
    });

    it('in: Tagged<Maybe<T>>', () => {
      expect(
        mntTypeStrip(taggedValue('boolean', maybe('string')), {dims: 1})
      ).toEqual(
        'invalid' // invalid input
      );
    });

    it('in: List<Tagged<T>>', () => {
      expect(
        mntTypeStrip(list(taggedValue('boolean', 'string'), 1, 2), {
          dims: 1,
        })
      ).toEqual(list(taggedValue('boolean', 'string'), 1, 2));
    });

    it('in: Maybe<Tagged<T>>', () => {
      expect(
        mntTypeStrip(maybe(taggedValue('boolean', 'string')), {dims: 1})
      ).toEqual(
        'invalid' // invalid input
      );
    });

    it('in: List<List<List<T>>>', () => {
      expect(
        mntTypeStrip(list(list(list('string', 1, 2), 3, 4), 5, 6), {
          dims: 1,
        })
      ).toEqual(list('string', 1, 2));
    });

    it('in: Maybe<List<List<T>>>', () => {
      expect(
        mntTypeStrip(maybe(list(list('string', 1, 2), 3, 4)), {dims: 1})
      ).toEqual(list('string', 1, 2));
    });

    it('in: Tagged<List<List<T>>>', () => {
      expect(
        mntTypeStrip(taggedValue('boolean', list(list('string', 1, 2), 3, 4)), {
          dims: 1,
        })
      ).toEqual(list('string', 1, 2));
    });

    it('in: List<Maybe<List<T>>>', () => {
      expect(
        mntTypeStrip(list(maybe(list('string', 1, 2)), 3, 4), {dims: 1})
      ).toEqual(list('string', 1, 2));
    });

    it('in: Tagged<Maybe<List<T>>>', () => {
      expect(
        mntTypeStrip(taggedValue('boolean', maybe(list('string', 1, 2))), {
          dims: 1,
        })
      ).toEqual(list('string', 1, 2));
    });

    it('in: List<Tagged<List<T>>>', () => {
      expect(
        mntTypeStrip(list(taggedValue('boolean', list('string', 1, 2)), 5, 6), {
          dims: 1,
        })
      ).toEqual(list('string', 1, 2));
    });

    it('in: Maybe<Tagged<List<T>>>', () => {
      expect(
        mntTypeStrip(maybe(taggedValue('boolean', list('string', 1, 2))), {
          dims: 1,
        })
      ).toEqual(list('string', 1, 2));
    });

    it('in: List<List<Maybe<T>>>', () => {
      expect(
        mntTypeStrip(list(list(maybe('string'), 1, 2), 3, 4), {dims: 1})
      ).toEqual(list(maybe('string'), 1, 2));
    });

    it('in: Maybe<List<Maybe<T>>>', () => {
      expect(
        mntTypeStrip(maybe(list(maybe('string'), 1, 2)), {dims: 1})
      ).toEqual(list(maybe('string'), 1, 2));
    });

    it('in: Tagged<List<Maybe<T>>>', () => {
      expect(
        mntTypeStrip(taggedValue('boolean', list(maybe('string'), 1, 2)), {
          dims: 1,
        })
      ).toEqual(list(maybe('string'), 1, 2));
    });

    it('in: List<Tagged<Maybe<T>>>', () => {
      expect(
        mntTypeStrip(list(taggedValue('boolean', maybe('string')), 1, 2), {
          dims: 1,
        })
      ).toEqual(list(taggedValue('boolean', maybe('string')), 1, 2));
    });

    it('in: Maybe<Tagged<Maybe<T>>>', () => {
      expect(
        mntTypeStrip(maybe(taggedValue('boolean', maybe('string'))), {
          dims: 1,
        })
      ).toEqual(
        'invalid' // invalid input
      );
    });

    it('in: List<List<Tagged<T>>>', () => {
      expect(
        mntTypeStrip(list(list(taggedValue('boolean', 'string'), 1, 2), 3, 4), {
          dims: 1,
        })
      ).toEqual(list(taggedValue('boolean', 'string'), 1, 2));
    });

    it('in: Maybe<List<Tagged<T>>>', () => {
      expect(
        mntTypeStrip(maybe(list(taggedValue('boolean', 'string'), 1, 2)), {
          dims: 1,
        })
      ).toEqual(list(taggedValue('boolean', 'string'), 1, 2));
    });

    it('in: Tagged<List<Tagged<T>>>', () => {
      expect(
        mntTypeStrip(
          taggedValue('boolean', list(taggedValue('run', 'string'), 1, 2)),
          {dims: 1}
        )
      ).toEqual(list(taggedValue('run', 'string'), 1, 2));
    });

    it('in: List<Maybe<Tagged<T>>>', () => {
      expect(
        mntTypeStrip(list(maybe(taggedValue('boolean', 'string')), 1, 2), {
          dims: 1,
        })
      ).toEqual(list(maybe(taggedValue('boolean', 'string')), 1, 2));
    });

    it('in: Tagged<Maybe<Tagged<T>>>', () => {
      expect(
        mntTypeStrip(
          taggedValue('boolean', maybe(taggedValue('run', 'string'))),
          {dims: 1}
        )
      ).toEqual(
        'invalid' // invalid input
      );
    });
  });
});

describe('mntValueApply', () => {
  describe('(dims=0, tags=false, nones=false)', () => {
    /*
    Cases:
      T
      List<T>
      Maybe<T>
      Tagged<T>
      List<List<T>>
      Maybe<List<T>>
      Tagged<List<T>>
      List<Maybe<T>>
      Tagged<Maybe<T>>
      List<Tagged<T>>
      Maybe<Tagged<T>>
      List<List<List<T>>>
      Maybe<List<List<T>>>
      Tagged<List<List<T>>>
      List<Maybe<List<T>>>
      Tagged<Maybe<List<T>>>
      List<Tagged<List<T>>>
      Maybe<Tagged<List<T>>>
      List<List<Maybe<T>>>
      Maybe<List<Maybe<T>>>
      Tagged<List<Maybe<T>>>
      List<Tagged<Maybe<T>>>
      Maybe<Tagged<Maybe<T>>>
      List<List<Tagged<T>>>
      Maybe<List<Tagged<T>>>
      Tagged<List<Tagged<T>>>
      List<Maybe<Tagged<T>>>
      Tagged<Maybe<Tagged<T>>>
    */
    it('in: T', () => {
      expect(
        mntValueApply('string', t => {
          expect(t).toEqual('string');
          return 42;
        })
      ).toEqual(42);
    });

    it('in: List<T>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(['a', 'b', 'c'], t => {
          const res = lookup[t as string];
          delete lookup[t as string];
          return res;
        })
      ).toEqual([42, 13, 3.14]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Maybe<T>', () => {
      expect(
        mntValueApply('string', t => {
          expect(t).toEqual('string');
          return 42;
        })
      ).toEqual(42);
      expect(
        mntValueApply(null, t => {
          expect(false).toEqual(true);
          return 42;
        })
      ).toEqual(null);
    });

    it('in: Tagged<T>', () => {
      expect(
        mntValueApply(concreteTaggedValue('boolean', 'string'), t => {
          expect(t).toEqual('string');
          return 42;
        })
      ).toEqual(concreteTaggedValue('boolean', 42));
    });

    it('in: List<List<T>>', () => {
      const lookup: {[key: string]: number} = {
        a: 42,
        b: 13,
        c: 3.14,
        d: 1,
        e: 2,
        f: 3,
      };
      expect(
        mntValueApply(
          [
            ['a', 'b', 'c'],
            ['d', 'e', 'f'],
          ],
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          }
        )
      ).toEqual([
        [42, 13, 3.14],
        [1, 2, 3],
      ]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Maybe<List<T>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(['a', 'b', 'c'], t => {
          const res = lookup[t as string];
          delete lookup[t as string];
          return res;
        })
      ).toEqual([42, 13, 3.14]);
      expect(Object.keys(lookup)).toEqual([]);
      expect(
        mntValueApply(null, t => {
          expect(false).toEqual(true);
          return 42;
        })
      ).toEqual(null);
    });

    it('in: Tagged<List<T>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(concreteTaggedValue('boolean', ['a', 'b', 'c']), t => {
          const res = lookup[t as string];
          delete lookup[t as string];
          return res;
        })
      ).toEqual(concreteTaggedValue('boolean', [42, 13, 3.14]));
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: List<Maybe<T>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(['a', null, 'b', null, 'c'], t => {
          const res = lookup[t as string];
          delete lookup[t as string];
          return res;
        })
      ).toEqual([42, null, 13, null, 3.14]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Tagged<Maybe<T>>', () => {
      expect(
        mntValueApply(concreteTaggedValue('boolean', 'string'), t => {
          expect(t).toEqual('string');
          return 42;
        })
      ).toEqual(concreteTaggedValue('boolean', 42));
      expect(
        mntValueApply(concreteTaggedValue('boolean', null), t => {
          expect(false).toEqual(true);
          return 42;
        })
      ).toEqual(concreteTaggedValue('boolean', null));
    });

    it('in: List<Tagged<T>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(
          [
            concreteTaggedValue('tag-a', 'a'),
            concreteTaggedValue('tag-b', 'b'),
            concreteTaggedValue('tag-c', 'c'),
          ],
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          }
        )
      ).toEqual([
        concreteTaggedValue('tag-a', 42),
        concreteTaggedValue('tag-b', 13),
        concreteTaggedValue('tag-c', 3.14),
      ]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Maybe<Tagged<T>>', () => {
      expect(
        mntValueApply(concreteTaggedValue('boolean', 'string'), t => {
          expect(t).toEqual('string');
          return 42;
        })
      ).toEqual(concreteTaggedValue('boolean', 42));
      expect(
        mntValueApply(concreteTaggedValue('boolean', null), t => {
          expect(false).toEqual(true);
          return 42;
        })
      ).toEqual(concreteTaggedValue('boolean', null));
    });

    it('in: List<List<List<T>>>', () => {
      const lookup: {[key: string]: number} = {
        a: 42,
        b: 13,
        c: 3.14,
        d: 1,
        e: 2,
        f: 3,
        g: 4,
        h: 5,
        i: 6,
        j: 7,
        k: 8,
        l: 9,
      };
      expect(
        mntValueApply(
          [
            [
              ['a', 'b', 'c'],
              ['d', 'e', 'f'],
            ],
            [
              ['g', 'h', 'i'],
              ['j', 'k', 'l'],
            ],
          ],
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          }
        )
      ).toEqual([
        [
          [42, 13, 3.14],
          [1, 2, 3],
        ],
        [
          [4, 5, 6],
          [7, 8, 9],
        ],
      ]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Maybe<List<List<T>>>', () => {
      const lookup: {[key: string]: number} = {
        a: 42,
        b: 13,
        c: 3.14,
        d: 1,
        e: 2,
        f: 3,
      };
      expect(
        mntValueApply(
          [
            ['a', 'b', 'c'],
            ['d', 'e', 'f'],
          ],
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          }
        )
      ).toEqual([
        [42, 13, 3.14],
        [1, 2, 3],
      ]);
      expect(Object.keys(lookup)).toEqual([]);
      expect(
        mntValueApply(null, t => {
          expect(false).toEqual(true);
          return 42;
        })
      ).toEqual(null);
    });

    it('in: Tagged<List<List<T>>>', () => {
      const lookup: {[key: string]: number} = {
        a: 42,
        b: 13,
        c: 3.14,
        d: 1,
        e: 2,
        f: 3,
      };
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', [
            ['a', 'b', 'c'],
            ['d', 'e', 'f'],
          ]),
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          }
        )
      ).toEqual(
        concreteTaggedValue('boolean', [
          [42, 13, 3.14],
          [1, 2, 3],
        ])
      );
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: List<Maybe<List<T>>>', () => {
      const lookup: {[key: string]: number} = {
        a: 42,
        b: 13,
        c: 3.14,
        d: 1,
        e: 2,
        f: 3,
      };
      expect(
        mntValueApply([['a', 'b', 'c'], null, ['d', 'e', 'f']], t => {
          const res = lookup[t as string];
          delete lookup[t as string];
          return res;
        })
      ).toEqual([[42, 13, 3.14], null, [1, 2, 3]]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Tagged<Maybe<List<T>>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(concreteTaggedValue('boolean', ['a', 'b', 'c']), t => {
          const res = lookup[t as string];
          delete lookup[t as string];
          return res;
        })
      ).toEqual(concreteTaggedValue('boolean', [42, 13, 3.14]));
      expect(Object.keys(lookup)).toEqual([]);
      expect(
        mntValueApply(concreteTaggedValue('boolean', null), t => {
          expect(false).toEqual(true);
          return 42;
        })
      ).toEqual(concreteTaggedValue('boolean', null));
    });

    it('in: List<Tagged<List<T>>>', () => {
      const lookup: {[key: string]: number} = {
        a: 42,
        b: 13,
        c: 3.14,
        d: 1,
        e: 2,
        f: 3,
      };
      expect(
        mntValueApply(
          [
            concreteTaggedValue('tag-1', ['a', 'b', 'c']),
            concreteTaggedValue('tag-2', ['d', 'e', 'f']),
          ],
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          }
        )
      ).toEqual([
        concreteTaggedValue('tag-1', [42, 13, 3.14]),
        concreteTaggedValue('tag-2', [1, 2, 3]),
      ]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Maybe<Tagged<List<T>>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(concreteTaggedValue('boolean', ['a', 'b', 'c']), t => {
          const res = lookup[t as string];
          delete lookup[t as string];
          return res;
        })
      ).toEqual(concreteTaggedValue('boolean', [42, 13, 3.14]));
      expect(Object.keys(lookup)).toEqual([]);
      expect(
        mntValueApply(null, t => {
          expect(false).toEqual(true);
          return 42;
        })
      ).toEqual(null);
    });

    it('in: List<List<Maybe<T>>>', () => {
      const lookup: {[key: string]: number} = {
        a: 42,
        b: 13,
        c: 3.14,
        d: 1,
        e: 2,
        f: 3,
      };
      expect(
        mntValueApply(
          [
            ['a', null, 'b', null, 'c'],
            ['d', null, 'e', null, 'f'],
          ],
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          }
        )
      ).toEqual([
        [42, null, 13, null, 3.14],
        [1, null, 2, null, 3],
      ]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Maybe<List<Maybe<T>>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(['a', null, 'b', null, 'c'], t => {
          const res = lookup[t as string];
          delete lookup[t as string];
          return res;
        })
      ).toEqual([42, null, 13, null, 3.14]);
      expect(Object.keys(lookup)).toEqual([]);
      expect(
        mntValueApply(null, t => {
          expect(false).toEqual(true);
          return 42;
        })
      ).toEqual(null);
    });

    it('in: Tagged<List<Maybe<T>>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', ['a', null, 'b', null, 'c']),
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          }
        )
      ).toEqual(concreteTaggedValue('boolean', [42, null, 13, null, 3.14]));
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: List<Tagged<Maybe<T>>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(
          [
            concreteTaggedValue('tag-a', 'a'),
            concreteTaggedValue('tag-n1', null),
            concreteTaggedValue('tag-b', 'b'),
            concreteTaggedValue('tag-n2', null),
            concreteTaggedValue('tag-c', 'c'),
          ],
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          }
        )
      ).toEqual([
        concreteTaggedValue('tag-a', 42),
        concreteTaggedValue('tag-n1', null),
        concreteTaggedValue('tag-b', 13),
        concreteTaggedValue('tag-n2', null),
        concreteTaggedValue('tag-c', 3.14),
      ]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Maybe<Tagged<Maybe<T>>>', () => {
      expect(
        mntValueApply(concreteTaggedValue('boolean', 'string'), t => {
          expect(t).toEqual('string');
          return 42;
        })
      ).toEqual(concreteTaggedValue('boolean', 42));
      expect(
        mntValueApply(concreteTaggedValue('boolean', null), t => {
          expect(false).toEqual(true);
          return 42;
        })
      ).toEqual(concreteTaggedValue('boolean', null));
      expect(
        mntValueApply(null, t => {
          expect(false).toEqual(true);
          return 42;
        })
      ).toEqual(null);
    });

    it('in: List<List<Tagged<T>>>', () => {
      const lookup: {[key: string]: number} = {
        a: 42,
        b: 13,
        c: 3.14,
        d: 1,
        e: 2,
        f: 3,
      };
      expect(
        mntValueApply(
          [
            [
              concreteTaggedValue('tag-a', 'a'),
              concreteTaggedValue('tag-b', 'b'),
              concreteTaggedValue('tag-c', 'c'),
            ],
            [
              concreteTaggedValue('tag-d', 'd'),
              concreteTaggedValue('tag-e', 'e'),
              concreteTaggedValue('tag-f', 'f'),
            ],
          ],
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          }
        )
      ).toEqual([
        [
          concreteTaggedValue('tag-a', 42),
          concreteTaggedValue('tag-b', 13),
          concreteTaggedValue('tag-c', 3.14),
        ],
        [
          concreteTaggedValue('tag-d', 1),
          concreteTaggedValue('tag-e', 2),
          concreteTaggedValue('tag-f', 3),
        ],
      ]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Maybe<List<Tagged<T>>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(
          [
            concreteTaggedValue('tag-a', 'a'),
            concreteTaggedValue('tag-b', 'b'),
            concreteTaggedValue('tag-c', 'c'),
          ],
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          }
        )
      ).toEqual([
        concreteTaggedValue('tag-a', 42),
        concreteTaggedValue('tag-b', 13),
        concreteTaggedValue('tag-c', 3.14),
      ]);
      expect(Object.keys(lookup)).toEqual([]);
      expect(
        mntValueApply(null, t => {
          expect(false).toEqual(true);
          return 42;
        })
      ).toEqual(null);
    });

    it('in: Tagged<List<Tagged<T>>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(
          concreteTaggedValue('outer', [
            concreteTaggedValue('tag-a', 'a'),
            concreteTaggedValue('tag-b', 'b'),
            concreteTaggedValue('tag-c', 'c'),
          ]),
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          }
        )
      ).toEqual(
        concreteTaggedValue('outer', [
          concreteTaggedValue('tag-a', 42),
          concreteTaggedValue('tag-b', 13),
          concreteTaggedValue('tag-c', 3.14),
        ])
      );
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: List<Maybe<Tagged<T>>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(
          [
            concreteTaggedValue('tag-a', 'a'),
            null,
            concreteTaggedValue('tag-b', 'b'),
            null,
            concreteTaggedValue('tag-c', 'c'),
          ],
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          }
        )
      ).toEqual([
        concreteTaggedValue('tag-a', 42),
        null,
        concreteTaggedValue('tag-b', 13),
        null,
        concreteTaggedValue('tag-c', 3.14),
      ]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Tagged<Maybe<Tagged<T>>>', () => {
      expect(
        mntValueApply(
          concreteTaggedValue('outer', concreteTaggedValue('inner', 'string')),
          t => {
            expect(t).toEqual('string');
            return 42;
          }
        )
      ).toEqual(concreteTaggedValue('outer', concreteTaggedValue('inner', 42)));
      expect(
        mntValueApply(concreteTaggedValue('outer', null), t => {
          expect(false).toEqual(true);
          return 42;
        })
      ).toEqual(concreteTaggedValue('outer', null));
    });
  });

  describe('(dims=0, tags=false, nones=true)', () => {
    /*
    Cases:
      T
      List<T>
      Maybe<T>
      Tagged<T>
      List<List<T>>
      Maybe<List<T>>
      Tagged<List<T>>
      List<Maybe<T>>
      Tagged<Maybe<T>>
      List<Tagged<T>>
      Maybe<Tagged<T>>
      List<List<List<T>>>
      Maybe<List<List<T>>>
      Tagged<List<List<T>>>
      List<Maybe<List<T>>>
      Tagged<Maybe<List<T>>>
      List<Tagged<List<T>>>
      Maybe<Tagged<List<T>>>
      List<List<Maybe<T>>>
      Maybe<List<Maybe<T>>>
      Tagged<List<Maybe<T>>>
      List<Tagged<Maybe<T>>>
      Maybe<Tagged<Maybe<T>>>
      List<List<Tagged<T>>>
      Maybe<List<Tagged<T>>>
      Tagged<List<Tagged<T>>>
      List<Maybe<Tagged<T>>>
      Tagged<Maybe<Tagged<T>>>
    */
    it('in: T', () => {
      expect(
        mntValueApply(
          'string',
          t => {
            expect(t).toEqual('string');
            return 42;
          },
          {nones: true}
        )
      ).toEqual(42);
    });

    it('in: List<T>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(
          ['a', 'b', 'c'],
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {nones: true}
        )
      ).toEqual([42, 13, 3.14]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Maybe<T>', () => {
      expect(
        mntValueApply(
          'string',
          t => {
            expect(t).toEqual('string');
            return 42;
          },
          {nones: true}
        )
      ).toEqual(42);
      expect(
        mntValueApply(
          null,
          t => {
            return 42;
          },
          {nones: true}
        )
      ).toEqual(42);
    });

    it('in: Tagged<T>', () => {
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', 'string'),
          t => {
            expect(t).toEqual('string');
            return 42;
          },
          {nones: true}
        )
      ).toEqual(concreteTaggedValue('boolean', 42));
    });

    it('in: List<List<T>>', () => {
      const lookup: {[key: string]: number} = {
        a: 42,
        b: 13,
        c: 3.14,
        d: 1,
        e: 2,
        f: 3,
      };
      expect(
        mntValueApply(
          [
            ['a', 'b', 'c'],
            ['d', 'e', 'f'],
          ],
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {nones: true}
        )
      ).toEqual([
        [42, 13, 3.14],
        [1, 2, 3],
      ]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Maybe<List<T>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(
          ['a', 'b', 'c'],
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {nones: true}
        )
      ).toEqual([42, 13, 3.14]);
      expect(Object.keys(lookup)).toEqual([]);
      expect(
        mntValueApply(
          null,
          t => {
            return 42;
          },
          {nones: true}
        )
      ).toEqual(42);
    });

    it('in: Tagged<List<T>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', ['a', 'b', 'c']),
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {nones: true}
        )
      ).toEqual(concreteTaggedValue('boolean', [42, 13, 3.14]));
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: List<Maybe<T>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      let noneCount = 0;
      expect(
        mntValueApply(
          ['a', null, 'b', null, 'c'],
          t => {
            if (t == null) {
              noneCount++;
              return '' + noneCount;
            }
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {nones: true}
        )
      ).toEqual([42, '1', 13, '2', 3.14]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Tagged<Maybe<T>>', () => {
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', 'string'),
          t => {
            expect(t).toEqual('string');
            return 42;
          },
          {nones: true}
        )
      ).toEqual(concreteTaggedValue('boolean', 42));
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', null),
          t => {
            return 42;
          },
          {nones: true}
        )
      ).toEqual(concreteTaggedValue('boolean', 42));
    });

    it('in: List<Tagged<T>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(
          [
            concreteTaggedValue('tag-a', 'a'),
            concreteTaggedValue('tag-b', 'b'),
            concreteTaggedValue('tag-c', 'c'),
          ],
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {nones: true}
        )
      ).toEqual([
        concreteTaggedValue('tag-a', 42),
        concreteTaggedValue('tag-b', 13),
        concreteTaggedValue('tag-c', 3.14),
      ]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Maybe<Tagged<T>>', () => {
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', 'string'),
          t => {
            expect(t).toEqual('string');
            return 42;
          },
          {nones: true}
        )
      ).toEqual(concreteTaggedValue('boolean', 42));
      expect(
        mntValueApply(
          null,
          t => {
            return 42;
          },
          {nones: true}
        )
      ).toEqual(42);
    });

    it('in: List<List<List<T>>>', () => {
      const lookup: {[key: string]: number} = {
        a: 42,
        b: 13,
        c: 3.14,
        d: 1,
        e: 2,
        f: 3,
        g: 4,
        h: 5,
        i: 6,
        j: 7,
        k: 8,
        l: 9,
      };
      expect(
        mntValueApply(
          [
            [
              ['a', 'b', 'c'],
              ['d', 'e', 'f'],
            ],
            [
              ['g', 'h', 'i'],
              ['j', 'k', 'l'],
            ],
          ],
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {nones: true}
        )
      ).toEqual([
        [
          [42, 13, 3.14],
          [1, 2, 3],
        ],
        [
          [4, 5, 6],
          [7, 8, 9],
        ],
      ]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Maybe<List<List<T>>>', () => {
      const lookup: {[key: string]: number} = {
        a: 42,
        b: 13,
        c: 3.14,
        d: 1,
        e: 2,
        f: 3,
      };
      expect(
        mntValueApply(
          [
            ['a', 'b', 'c'],
            ['d', 'e', 'f'],
          ],
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {nones: true}
        )
      ).toEqual([
        [42, 13, 3.14],
        [1, 2, 3],
      ]);
      expect(Object.keys(lookup)).toEqual([]);
      expect(
        mntValueApply(
          null,
          t => {
            return 42;
          },
          {nones: true}
        )
      ).toEqual(42);
    });

    it('in: Tagged<List<List<T>>>', () => {
      const lookup: {[key: string]: number} = {
        a: 42,
        b: 13,
        c: 3.14,
        d: 1,
        e: 2,
        f: 3,
      };
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', [
            ['a', 'b', 'c'],
            ['d', 'e', 'f'],
          ]),
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {nones: true}
        )
      ).toEqual(
        concreteTaggedValue('boolean', [
          [42, 13, 3.14],
          [1, 2, 3],
        ])
      );
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: List<Maybe<List<T>>>', () => {
      const lookup: {[key: string]: number} = {
        a: 42,
        b: 13,
        c: 3.14,
        d: 1,
        e: 2,
        f: 3,
      };
      let noneCount = 0;
      expect(
        mntValueApply(
          [['a', 'b', 'c'], null, ['d', 'e', 'f']],
          t => {
            if (t == null) {
              noneCount++;
              return '' + noneCount;
            }
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {nones: true}
        )
      ).toEqual([[42, 13, 3.14], '1', [1, 2, 3]]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Tagged<Maybe<List<T>>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', ['a', 'b', 'c']),
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {nones: true}
        )
      ).toEqual(concreteTaggedValue('boolean', [42, 13, 3.14]));
      expect(Object.keys(lookup)).toEqual([]);
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', null),
          t => {
            return 42;
          },
          {nones: true}
        )
      ).toEqual(concreteTaggedValue('boolean', 42));
    });

    it('in: List<Tagged<List<T>>>', () => {
      const lookup: {[key: string]: number} = {
        a: 42,
        b: 13,
        c: 3.14,
        d: 1,
        e: 2,
        f: 3,
      };
      expect(
        mntValueApply(
          [
            concreteTaggedValue('tag-1', ['a', 'b', 'c']),
            concreteTaggedValue('tag-2', ['d', 'e', 'f']),
          ],
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {nones: true}
        )
      ).toEqual([
        concreteTaggedValue('tag-1', [42, 13, 3.14]),
        concreteTaggedValue('tag-2', [1, 2, 3]),
      ]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Maybe<Tagged<List<T>>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', ['a', 'b', 'c']),
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {nones: true}
        )
      ).toEqual(concreteTaggedValue('boolean', [42, 13, 3.14]));
      expect(Object.keys(lookup)).toEqual([]);
      expect(
        mntValueApply(
          null,
          t => {
            return 42;
          },
          {nones: true}
        )
      ).toEqual(42);
    });

    it('in: List<List<Maybe<T>>>', () => {
      const lookup: {[key: string]: number} = {
        a: 42,
        b: 13,
        c: 3.14,
        d: 1,
        e: 2,
        f: 3,
      };
      let noneCount = 0;
      expect(
        mntValueApply(
          [
            ['a', null, 'b', null, 'c'],
            ['d', null, 'e', null, 'f'],
          ],
          t => {
            if (t == null) {
              noneCount++;
              return '' + noneCount;
            }
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {nones: true}
        )
      ).toEqual([
        [42, '1', 13, '2', 3.14],
        [1, '3', 2, '4', 3],
      ]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Maybe<List<Maybe<T>>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      let noneCount = 0;
      expect(
        mntValueApply(
          ['a', null, 'b', null, 'c'],
          t => {
            if (t == null) {
              noneCount++;
              return '' + noneCount;
            }
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {nones: true}
        )
      ).toEqual([42, '1', 13, '2', 3.14]);
      expect(Object.keys(lookup)).toEqual([]);
      expect(
        mntValueApply(
          null,
          t => {
            return 42;
          },
          {nones: true}
        )
      ).toEqual(42);
    });

    it('in: Tagged<List<Maybe<T>>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      let noneCount = 0;
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', ['a', null, 'b', null, 'c']),
          t => {
            if (t == null) {
              noneCount++;
              return '' + noneCount;
            }
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {nones: true}
        )
      ).toEqual(concreteTaggedValue('boolean', [42, '1', 13, '2', 3.14]));
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: List<Tagged<Maybe<T>>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      let noneCount = 0;
      expect(
        mntValueApply(
          [
            concreteTaggedValue('tag-a', 'a'),
            concreteTaggedValue('tag-n1', null),
            concreteTaggedValue('tag-b', 'b'),
            concreteTaggedValue('tag-n2', null),
            concreteTaggedValue('tag-c', 'c'),
          ],
          t => {
            if (t == null) {
              noneCount++;
              return '' + noneCount;
            }
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {nones: true}
        )
      ).toEqual([
        concreteTaggedValue('tag-a', 42),
        concreteTaggedValue('tag-n1', '1'),
        concreteTaggedValue('tag-b', 13),
        concreteTaggedValue('tag-n2', '2'),
        concreteTaggedValue('tag-c', 3.14),
      ]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Maybe<Tagged<Maybe<T>>>', () => {
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', 'string'),
          t => {
            expect(t).toEqual('string');
            return 42;
          },
          {nones: true}
        )
      ).toEqual(concreteTaggedValue('boolean', 42));
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', null),
          t => {
            return 42;
          },
          {nones: true}
        )
      ).toEqual(concreteTaggedValue('boolean', 42));
      expect(
        mntValueApply(
          null,
          t => {
            return 42;
          },
          {nones: true}
        )
      ).toEqual(42);
    });

    it('in: List<List<Tagged<T>>>', () => {
      const lookup: {[key: string]: number} = {
        a: 42,
        b: 13,
        c: 3.14,
        d: 1,
        e: 2,
        f: 3,
      };
      expect(
        mntValueApply(
          [
            [
              concreteTaggedValue('tag-a', 'a'),
              concreteTaggedValue('tag-b', 'b'),
              concreteTaggedValue('tag-c', 'c'),
            ],
            [
              concreteTaggedValue('tag-d', 'd'),
              concreteTaggedValue('tag-e', 'e'),
              concreteTaggedValue('tag-f', 'f'),
            ],
          ],
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {nones: true}
        )
      ).toEqual([
        [
          concreteTaggedValue('tag-a', 42),
          concreteTaggedValue('tag-b', 13),
          concreteTaggedValue('tag-c', 3.14),
        ],
        [
          concreteTaggedValue('tag-d', 1),
          concreteTaggedValue('tag-e', 2),
          concreteTaggedValue('tag-f', 3),
        ],
      ]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Maybe<List<Tagged<T>>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(
          [
            concreteTaggedValue('tag-a', 'a'),
            concreteTaggedValue('tag-b', 'b'),
            concreteTaggedValue('tag-c', 'c'),
          ],
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {nones: true}
        )
      ).toEqual([
        concreteTaggedValue('tag-a', 42),
        concreteTaggedValue('tag-b', 13),
        concreteTaggedValue('tag-c', 3.14),
      ]);
      expect(Object.keys(lookup)).toEqual([]);
      expect(
        mntValueApply(
          null,
          t => {
            return 42;
          },
          {nones: true}
        )
      ).toEqual(42);
    });

    it('in: Tagged<List<Tagged<T>>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(
          concreteTaggedValue('outer', [
            concreteTaggedValue('tag-a', 'a'),
            concreteTaggedValue('tag-b', 'b'),
            concreteTaggedValue('tag-c', 'c'),
          ]),
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {nones: true}
        )
      ).toEqual(
        concreteTaggedValue('outer', [
          concreteTaggedValue('tag-a', 42),
          concreteTaggedValue('tag-b', 13),
          concreteTaggedValue('tag-c', 3.14),
        ])
      );
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: List<Maybe<Tagged<T>>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      let noneCount = 0;
      expect(
        mntValueApply(
          [
            concreteTaggedValue('tag-a', 'a'),
            null,
            concreteTaggedValue('tag-b', 'b'),
            null,
            concreteTaggedValue('tag-c', 'c'),
          ],
          t => {
            if (t == null) {
              noneCount++;
              return '' + noneCount;
            }
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {nones: true}
        )
      ).toEqual([
        concreteTaggedValue('tag-a', 42),
        '1',
        concreteTaggedValue('tag-b', 13),
        '2',
        concreteTaggedValue('tag-c', 3.14),
      ]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Tagged<Maybe<Tagged<T>>>', () => {
      expect(
        mntValueApply(
          concreteTaggedValue('outer', concreteTaggedValue('inner', 'string')),
          t => {
            expect(t).toEqual('string');
            return 42;
          },
          {nones: true}
        )
      ).toEqual(concreteTaggedValue('outer', concreteTaggedValue('inner', 42)));
      expect(
        mntValueApply(
          concreteTaggedValue('outer', null),
          t => {
            return 42;
          },
          {nones: true}
        )
      ).toEqual(concreteTaggedValue('outer', 42));
    });
  });

  describe('(dims=0, tags=true, nones=false)', () => {
    /*
      Cases:
        T
        List<T>
        Maybe<T>
        Tagged<T>
        List<List<T>>
        Maybe<List<T>>
        Tagged<List<T>>
        List<Maybe<T>>
        Tagged<Maybe<T>>
        List<Tagged<T>>
        Maybe<Tagged<T>>
        List<List<List<T>>>
        Maybe<List<List<T>>>
        Tagged<List<List<T>>>
        List<Maybe<List<T>>>
        Tagged<Maybe<List<T>>>
        List<Tagged<List<T>>>
        Maybe<Tagged<List<T>>>
        List<List<Maybe<T>>>
        Maybe<List<Maybe<T>>>
        Tagged<List<Maybe<T>>>
        List<Tagged<Maybe<T>>>
        Maybe<Tagged<Maybe<T>>>
        List<List<Tagged<T>>>
        Maybe<List<Tagged<T>>>
        Tagged<List<Tagged<T>>>
        List<Maybe<Tagged<T>>>
        Tagged<Maybe<Tagged<T>>>
      */
    it('in: T', () => {
      expect(
        mntValueApply(
          'string',
          t => {
            expect(t).toEqual('string');
            return 42;
          },
          {tags: true}
        )
      ).toEqual(42);
    });

    it('in: List<T>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(
          ['a', 'b', 'c'],
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {tags: true}
        )
      ).toEqual([42, 13, 3.14]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Maybe<T>', () => {
      expect(
        mntValueApply(
          'string',
          t => {
            expect(t).toEqual('string');
            return 42;
          },
          {tags: true}
        )
      ).toEqual(42);
      expect(
        mntValueApply(
          null,
          t => {
            expect(false).toEqual(true);
            return 42;
          },
          {tags: true}
        )
      ).toEqual(null);
    });

    it('in: Tagged<T>', () => {
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', 'string'),
          t => {
            expect(t).toEqual(concreteTaggedValue('boolean', 'string'));
            return 42;
          },
          {tags: true}
        )
      ).toEqual(42);
    });

    it('in: List<List<T>>', () => {
      const lookup: {[key: string]: number} = {
        a: 42,
        b: 13,
        c: 3.14,
        d: 1,
        e: 2,
        f: 3,
      };
      expect(
        mntValueApply(
          [
            ['a', 'b', 'c'],
            ['d', 'e', 'f'],
          ],
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {tags: true}
        )
      ).toEqual([
        [42, 13, 3.14],
        [1, 2, 3],
      ]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Maybe<List<T>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(
          ['a', 'b', 'c'],
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {tags: true}
        )
      ).toEqual([42, 13, 3.14]);
      expect(Object.keys(lookup)).toEqual([]);
      expect(
        mntValueApply(
          null,
          t => {
            expect(false).toEqual(true);
            return 42;
          },
          {tags: true}
        )
      ).toEqual(null);
    });

    it('in: Tagged<List<T>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', ['a', 'b', 'c']),
          t => {
            expect(t._tag).toEqual('boolean');
            t = t._value;
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {tags: true}
        )
      ).toEqual([42, 13, 3.14]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: List<Maybe<T>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(
          ['a', null, 'b', null, 'c'],
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {tags: true}
        )
      ).toEqual([42, null, 13, null, 3.14]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Tagged<Maybe<T>>', () => {
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', 'string'),
          t => {
            expect(t._tag).toEqual('boolean');
            t = t._value;
            expect(t).toEqual('string');
            return 42;
          },
          {tags: true}
        )
      ).toEqual(42);
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', null),
          t => {
            expect(false).toEqual(true);
            return 42;
          },
          {tags: true}
        )
      ).toEqual(concreteTaggedValue('boolean', null));
    });

    it('in: List<Tagged<T>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(
          [
            concreteTaggedValue('tag-a', 'a'),
            concreteTaggedValue('tag-b', 'b'),
            concreteTaggedValue('tag-c', 'c'),
          ],
          t => {
            expect(t._tag).toEqual('tag-' + t._value);
            t = t._value;
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {tags: true}
        )
      ).toEqual([42, 13, 3.14]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Maybe<Tagged<T>>', () => {
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', 'string'),
          t => {
            expect(t._tag).toEqual('boolean');
            t = t._value;
            expect(t).toEqual('string');
            return 42;
          },
          {tags: true}
        )
      ).toEqual(42);
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', null),
          t => {
            expect(false).toEqual(true);
            return 42;
          },
          {tags: true}
        )
      ).toEqual(concreteTaggedValue('boolean', null));
    });

    it('in: List<List<List<T>>>', () => {
      const lookup: {[key: string]: number} = {
        a: 42,
        b: 13,
        c: 3.14,
        d: 1,
        e: 2,
        f: 3,
        g: 4,
        h: 5,
        i: 6,
        j: 7,
        k: 8,
        l: 9,
      };
      expect(
        mntValueApply(
          [
            [
              ['a', 'b', 'c'],
              ['d', 'e', 'f'],
            ],
            [
              ['g', 'h', 'i'],
              ['j', 'k', 'l'],
            ],
          ],
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {tags: true}
        )
      ).toEqual([
        [
          [42, 13, 3.14],
          [1, 2, 3],
        ],
        [
          [4, 5, 6],
          [7, 8, 9],
        ],
      ]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Maybe<List<List<T>>>', () => {
      const lookup: {[key: string]: number} = {
        a: 42,
        b: 13,
        c: 3.14,
        d: 1,
        e: 2,
        f: 3,
      };
      expect(
        mntValueApply(
          [
            ['a', 'b', 'c'],
            ['d', 'e', 'f'],
          ],
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {tags: true}
        )
      ).toEqual([
        [42, 13, 3.14],
        [1, 2, 3],
      ]);
      expect(Object.keys(lookup)).toEqual([]);
      expect(
        mntValueApply(
          null,
          t => {
            expect(false).toEqual(true);
            return 42;
          },
          {tags: true}
        )
      ).toEqual(null);
    });

    it('in: Tagged<List<List<T>>>', () => {
      const lookup: {[key: string]: number} = {
        a: 42,
        b: 13,
        c: 3.14,
        d: 1,
        e: 2,
        f: 3,
      };
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', [
            ['a', 'b', 'c'],
            ['d', 'e', 'f'],
          ]),
          t => {
            expect(t._tag).toEqual('boolean');
            t = t._value;
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {tags: true}
        )
      ).toEqual([
        [42, 13, 3.14],
        [1, 2, 3],
      ]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: List<Maybe<List<T>>>', () => {
      const lookup: {[key: string]: number} = {
        a: 42,
        b: 13,
        c: 3.14,
        d: 1,
        e: 2,
        f: 3,
      };
      expect(
        mntValueApply(
          [['a', 'b', 'c'], null, ['d', 'e', 'f']],
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {tags: true}
        )
      ).toEqual([[42, 13, 3.14], null, [1, 2, 3]]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Tagged<Maybe<List<T>>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', ['a', 'b', 'c']),
          t => {
            expect(t._tag).toEqual('boolean');
            t = t._value;
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {tags: true}
        )
      ).toEqual([42, 13, 3.14]);
      expect(Object.keys(lookup)).toEqual([]);
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', null),
          t => {
            expect(false).toEqual(true);
            return 42;
          },
          {tags: true}
        )
      ).toEqual(concreteTaggedValue('boolean', null));
    });

    it('in: List<Tagged<List<T>>>', () => {
      const lookup: {[key: string]: number} = {
        a: 42,
        b: 13,
        c: 3.14,
        d: 1,
        e: 2,
        f: 3,
      };
      expect(
        mntValueApply(
          [
            concreteTaggedValue('tag-1', ['a', 'b', 'c']),
            concreteTaggedValue('tag-2', ['d', 'e', 'f']),
          ],
          t => {
            expect(t._tag).toEqual(
              'tag-' + (['a', 'b', 'c'].indexOf(t._value) > -1 ? '1' : '2')
            );
            t = t._value;
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {tags: true}
        )
      ).toEqual([
        [42, 13, 3.14],
        [1, 2, 3],
      ]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Maybe<Tagged<List<T>>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', ['a', 'b', 'c']),
          t => {
            expect(t._tag).toEqual('boolean');
            t = t._value;
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {tags: true}
        )
      ).toEqual([42, 13, 3.14]);
      expect(Object.keys(lookup)).toEqual([]);
      expect(
        mntValueApply(
          null,
          t => {
            expect(false).toEqual(true);
            return 42;
          },
          {tags: true}
        )
      ).toEqual(null);
    });

    it('in: List<List<Maybe<T>>>', () => {
      const lookup: {[key: string]: number} = {
        a: 42,
        b: 13,
        c: 3.14,
        d: 1,
        e: 2,
        f: 3,
      };
      expect(
        mntValueApply(
          [
            ['a', null, 'b', null, 'c'],
            ['d', null, 'e', null, 'f'],
          ],
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {tags: true}
        )
      ).toEqual([
        [42, null, 13, null, 3.14],
        [1, null, 2, null, 3],
      ]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Maybe<List<Maybe<T>>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(
          ['a', null, 'b', null, 'c'],
          t => {
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {tags: true}
        )
      ).toEqual([42, null, 13, null, 3.14]);
      expect(Object.keys(lookup)).toEqual([]);
      expect(
        mntValueApply(
          null,
          t => {
            expect(false).toEqual(true);
            return 42;
          },
          {tags: true}
        )
      ).toEqual(null);
    });

    it('in: Tagged<List<Maybe<T>>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', ['a', null, 'b', null, 'c']),
          t => {
            expect(t._tag).toEqual('boolean');
            t = t._value;
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {tags: true}
        )
      ).toEqual([
        42,
        concreteTaggedValue('boolean', null),
        13,
        concreteTaggedValue('boolean', null),
        3.14,
      ]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: List<Tagged<Maybe<T>>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(
          [
            concreteTaggedValue('tag-a', 'a'),
            concreteTaggedValue('tag-n1', null),
            concreteTaggedValue('tag-b', 'b'),
            concreteTaggedValue('tag-n2', null),
            concreteTaggedValue('tag-c', 'c'),
          ],
          t => {
            expect(t._tag).toEqual('tag-' + t._value);
            t = t._value;
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {tags: true}
        )
      ).toEqual([
        42,
        concreteTaggedValue('tag-n1', null),
        13,
        concreteTaggedValue('tag-n2', null),
        3.14,
      ]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Maybe<Tagged<Maybe<T>>>', () => {
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', 'string'),
          t => {
            expect(t._tag).toEqual('boolean');
            t = t._value;
            expect(t).toEqual('string');
            return 42;
          },
          {tags: true}
        )
      ).toEqual(42);
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', null),
          t => {
            expect(false).toEqual(true);
            return 42;
          },
          {tags: true}
        )
      ).toEqual(concreteTaggedValue('boolean', null));
      expect(
        mntValueApply(
          null,
          t => {
            expect(false).toEqual(true);
            return 42;
          },
          {tags: true}
        )
      ).toEqual(null);
    });

    it('in: List<List<Tagged<T>>>', () => {
      const lookup: {[key: string]: number} = {
        a: 42,
        b: 13,
        c: 3.14,
        d: 1,
        e: 2,
        f: 3,
      };
      expect(
        mntValueApply(
          [
            [
              concreteTaggedValue('tag-a', 'a'),
              concreteTaggedValue('tag-b', 'b'),
              concreteTaggedValue('tag-c', 'c'),
            ],
            [
              concreteTaggedValue('tag-d', 'd'),
              concreteTaggedValue('tag-e', 'e'),
              concreteTaggedValue('tag-f', 'f'),
            ],
          ],
          t => {
            expect(t._tag).toEqual('tag-' + t._value);
            t = t._value;
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {tags: true}
        )
      ).toEqual([
        [42, 13, 3.14],
        [1, 2, 3],
      ]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Maybe<List<Tagged<T>>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(
          [
            concreteTaggedValue('tag-a', 'a'),
            concreteTaggedValue('tag-b', 'b'),
            concreteTaggedValue('tag-c', 'c'),
          ],
          t => {
            expect(t._tag).toEqual('tag-' + t._value);
            t = t._value;
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {tags: true}
        )
      ).toEqual([42, 13, 3.14]);
      expect(Object.keys(lookup)).toEqual([]);
      expect(
        mntValueApply(
          null,
          t => {
            expect(false).toEqual(true);
            return 42;
          },
          {tags: true}
        )
      ).toEqual(null);
    });

    it('in: Tagged<List<Tagged<T>>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(
          concreteTaggedValue('outer', [
            concreteTaggedValue('tag-a', 'a'),
            concreteTaggedValue('tag-b', 'b'),
            concreteTaggedValue('tag-c', 'c'),
          ]),
          t => {
            expect(t._tag).toEqual(
              concreteTaggedValue('outer', 'tag-' + t._value)
            );
            t = t._value;
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {tags: true}
        )
      ).toEqual([42, 13, 3.14]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: List<Maybe<Tagged<T>>>', () => {
      const lookup: {[key: string]: number} = {a: 42, b: 13, c: 3.14};
      expect(
        mntValueApply(
          [
            concreteTaggedValue('tag-a', 'a'),
            null,
            concreteTaggedValue('tag-b', 'b'),
            null,
            concreteTaggedValue('tag-c', 'c'),
          ],
          t => {
            expect(t._tag).toEqual('tag-' + t._value);
            t = t._value;
            const res = lookup[t as string];
            delete lookup[t as string];
            return res;
          },
          {tags: true}
        )
      ).toEqual([42, null, 13, null, 3.14]);
      expect(Object.keys(lookup)).toEqual([]);
    });

    it('in: Tagged<Maybe<Tagged<T>>>', () => {
      expect(
        mntValueApply(
          concreteTaggedValue('outer', concreteTaggedValue('inner', 'string')),
          t => {
            expect(t._tag).toEqual(concreteTaggedValue('outer', 'inner'));
            t = t._value;
            expect(t).toEqual('string');
            return 42;
          },
          {tags: true}
        )
      ).toEqual(42);
      expect(
        mntValueApply(
          concreteTaggedValue('outer', null),
          t => {
            expect(false).toEqual(true);
            return 42;
          },
          {tags: true}
        )
      ).toEqual(concreteTaggedValue('outer', null));
    });
  });

  describe('(dims=1, tags=false, nones=false)', () => {
    /*
    Cases:
      T
      List<T>
      Maybe<T>
      Tagged<T>
      List<List<T>>
      Maybe<List<T>>
      Tagged<List<T>>
      List<Maybe<T>>
      Tagged<Maybe<T>>
      List<Tagged<T>>
      Maybe<Tagged<T>>
      List<List<List<T>>>
      Maybe<List<List<T>>>
      Tagged<List<List<T>>>
      List<Maybe<List<T>>>
      Tagged<Maybe<List<T>>>
      List<Tagged<List<T>>>
      Maybe<Tagged<List<T>>>
      List<List<Maybe<T>>>
      Maybe<List<Maybe<T>>>
      Tagged<List<Maybe<T>>>
      List<Tagged<Maybe<T>>>
      Maybe<Tagged<Maybe<T>>>
      List<List<Tagged<T>>>
      Maybe<List<Tagged<T>>>
      Tagged<List<Tagged<T>>>
      List<Maybe<Tagged<T>>>
      Tagged<Maybe<Tagged<T>>>
    */
    it('in: T', () => {
      expect(mntValueApply('string', t => {}, {dims: 1})).toEqual(
        undefined // invalid input
      );
    });

    it('in: List<T>', () => {
      expect(
        mntValueApply(
          ['a', 'b', 'c'],
          t => {
            expect(_.isEqual(t, ['a', 'b', 'c'])).toEqual(true);
            return t.join('');
          },
          {dims: 1}
        )
      ).toEqual('abc');
    });

    it('in: Maybe<T>', () => {
      expect(mntValueApply('string', t => {}, {dims: 1})).toEqual(
        undefined // invalid input
      );
      expect(
        mntValueApply(
          null,
          t => {
            expect(false).toEqual(true);
            return 42;
          },
          {tags: true}
        )
      ).toEqual(null);
    });

    it('in: Tagged<T>', () => {
      expect(
        mntValueApply(concreteTaggedValue('boolean', 'string'), t => {}, {
          dims: 1,
        })
      ).toEqual(
        undefined // invalid input
      );
    });

    it('in: List<List<T>>', () => {
      expect(
        mntValueApply(
          [
            ['a', 'b', 'c'],
            ['d', 'e', 'f'],
          ],
          t => {
            expect(
              _.isEqual(t, ['a', 'b', 'c']) || _.isEqual(t, ['d', 'e', 'f'])
            ).toEqual(true);
            return t.join('');
          },
          {dims: 1}
        )
      ).toEqual(['abc', 'def']);
    });

    it('in: Maybe<List<T>>', () => {
      expect(
        mntValueApply(
          ['a', 'b', 'c'],
          t => {
            expect(_.isEqual(t, ['a', 'b', 'c'])).toEqual(true);
            return t.join('');
          },
          {dims: 1}
        )
      ).toEqual('abc');
      expect(
        mntValueApply(
          null,
          t => {
            expect(false).toEqual(true);
            return 42;
          },
          {dims: 1}
        )
      ).toEqual(null);
    });

    it('in: Tagged<List<T>>', () => {
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', ['a', 'b', 'c']),
          t => {
            expect(_.isEqual(t, ['a', 'b', 'c'])).toEqual(true);
            return t.join('');
          },
          {dims: 1}
        )
      ).toEqual(concreteTaggedValue('boolean', 'abc'));
    });

    it('in: List<Maybe<T>>', () => {
      expect(
        mntValueApply(
          ['a', null, 'b', null, 'c'],
          t => {
            expect(_.isEqual(t, ['a', null, 'b', null, 'c'])).toEqual(true);
            return t.join('');
          },
          {dims: 1}
        )
      ).toEqual('abc');
    });

    it('in: Tagged<Maybe<T>>', () => {
      expect(
        mntValueApply(concreteTaggedValue('boolean', 'string'), t => {}, {
          dims: 1,
        })
      ).toEqual(
        undefined // invalid input
      );
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', null),
          t => {
            expect(false).toEqual(true);
            return 42;
          },
          {dims: 1}
        )
      ).toEqual(concreteTaggedValue('boolean', null));
    });

    it('in: List<Tagged<T>>', () => {
      expect(
        mntValueApply(
          [
            concreteTaggedValue('tag-a', 'a'),
            concreteTaggedValue('tag-b', 'b'),
            concreteTaggedValue('tag-c', 'c'),
          ],
          t => {
            expect(
              _.isEqual(t, [
                concreteTaggedValue('tag-a', 'a'),
                concreteTaggedValue('tag-b', 'b'),
                concreteTaggedValue('tag-c', 'c'),
              ])
            ).toEqual(true);
            return 'abc';
          },
          {dims: 1}
        )
      ).toEqual('abc');
    });

    it('in: Maybe<Tagged<T>>', () => {
      expect(
        mntValueApply(concreteTaggedValue('boolean', 'string'), t => {}, {
          dims: 1,
        })
      ).toEqual(
        undefined // invalid input
      );
      expect(
        mntValueApply(
          null,
          t => {
            expect(false).toEqual(true);
            return 42;
          },
          {dims: 1}
        )
      ).toEqual(null);
    });

    it('in: List<List<List<T>>>', () => {
      expect(
        mntValueApply(
          [
            [
              ['a', 'b', 'c'],
              ['d', 'e', 'f'],
            ],
            [
              ['g', 'h', 'i'],
              ['j', 'k', 'l'],
            ],
          ],
          t => {
            expect(
              _.isEqual(t, ['a', 'b', 'c']) ||
                _.isEqual(t, ['d', 'e', 'f']) ||
                _.isEqual(t, ['g', 'h', 'i']) ||
                _.isEqual(t, ['j', 'k', 'l'])
            ).toEqual(true);
            return t.join('');
          },
          {dims: 1}
        )
      ).toEqual([
        ['abc', 'def'],
        ['ghi', 'jkl'],
      ]);
    });

    it('in: Maybe<List<List<T>>>', () => {
      expect(
        mntValueApply(
          [
            ['a', 'b', 'c'],
            ['d', 'e', 'f'],
          ],
          t => {
            expect(
              _.isEqual(t, ['a', 'b', 'c']) || _.isEqual(t, ['d', 'e', 'f'])
            ).toEqual(true);
            return t.join('');
          },
          {dims: 1}
        )
      ).toEqual(['abc', 'def']);
      expect(
        mntValueApply(
          null,
          t => {
            expect(false).toEqual(true);
            return 42;
          },
          {dims: 1}
        )
      ).toEqual(null);
    });

    it('in: Tagged<List<List<T>>>', () => {
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', [
            ['a', 'b', 'c'],
            ['d', 'e', 'f'],
          ]),
          t => {
            expect(
              _.isEqual(t, ['a', 'b', 'c']) || _.isEqual(t, ['d', 'e', 'f'])
            ).toEqual(true);
            return t.join('');
          },
          {dims: 1}
        )
      ).toEqual(concreteTaggedValue('boolean', ['abc', 'def']));
    });

    it('in: List<Maybe<List<T>>>', () => {
      expect(
        mntValueApply(
          [['a', 'b', 'c'], null, ['d', 'e', 'f']],
          t => {
            expect(
              _.isEqual(t, ['a', 'b', 'c']) || _.isEqual(t, ['d', 'e', 'f'])
            ).toEqual(true);
            return t.join('');
          },
          {dims: 1}
        )
      ).toEqual(['abc', null, 'def']);
    });

    it('in: Tagged<Maybe<List<T>>>', () => {
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', ['a', 'b', 'c']),
          t => {
            expect(_.isEqual(t, ['a', 'b', 'c'])).toEqual(true);
            return t.join('');
          },
          {dims: 1}
        )
      ).toEqual(concreteTaggedValue('boolean', 'abc'));
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', null),
          t => {
            expect(false).toEqual(true);
            return 42;
          },
          {dims: 1}
        )
      ).toEqual(concreteTaggedValue('boolean', null));
    });

    it('in: List<Tagged<List<T>>>', () => {
      expect(
        mntValueApply(
          [
            concreteTaggedValue('tag-1', ['a', 'b', 'c']),
            concreteTaggedValue('tag-2', ['d', 'e', 'f']),
          ],
          t => {
            expect(
              _.isEqual(t, ['a', 'b', 'c']) || _.isEqual(t, ['d', 'e', 'f'])
            ).toEqual(true);
            return t.join('');
          },
          {dims: 1}
        )
      ).toEqual([
        concreteTaggedValue('tag-1', 'abc'),
        concreteTaggedValue('tag-2', 'def'),
      ]);
    });

    it('in: Maybe<Tagged<List<T>>>', () => {
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', ['a', 'b', 'c']),
          t => {
            expect(_.isEqual(t, ['a', 'b', 'c'])).toEqual(true);
            return t.join('');
          },
          {dims: 1}
        )
      ).toEqual(concreteTaggedValue('boolean', 'abc'));
      expect(
        mntValueApply(
          null,
          t => {
            expect(false).toEqual(true);
            return 42;
          },
          {dims: 1}
        )
      ).toEqual(null);
    });

    it('in: List<List<Maybe<T>>>', () => {
      expect(
        mntValueApply(
          [
            ['a', null, 'b', null, 'c'],
            ['d', null, 'e', null, 'f'],
          ],
          t => {
            expect(
              _.isEqual(t, ['a', null, 'b', null, 'c']) ||
                _.isEqual(t, ['d', null, 'e', null, 'f'])
            ).toEqual(true);
            return t.join('');
          },
          {dims: 1}
        )
      ).toEqual(['abc', 'def']);
    });

    it('in: Maybe<List<Maybe<T>>>', () => {
      expect(
        mntValueApply(
          ['a', null, 'b', null, 'c'],
          t => {
            expect(_.isEqual(t, ['a', null, 'b', null, 'c'])).toEqual(true);
            return t.join('');
          },
          {dims: 1}
        )
      ).toEqual('abc');
      expect(
        mntValueApply(
          null,
          t => {
            expect(false).toEqual(true);
            return 42;
          },
          {dims: 1}
        )
      ).toEqual(null);
    });

    it('in: Tagged<List<Maybe<T>>>', () => {
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', ['a', null, 'b', null, 'c']),
          t => {
            expect(_.isEqual(t, ['a', null, 'b', null, 'c'])).toEqual(true);
            return t.join('');
          },
          {dims: 1}
        )
      ).toEqual(concreteTaggedValue('boolean', 'abc'));
    });

    it('in: List<Tagged<Maybe<T>>>', () => {
      expect(
        mntValueApply(
          [
            concreteTaggedValue('tag-a', 'a'),
            concreteTaggedValue('tag-n1', null),
            concreteTaggedValue('tag-b', 'b'),
            concreteTaggedValue('tag-n2', null),
            concreteTaggedValue('tag-c', 'c'),
          ],
          t => {
            expect(
              _.isEqual(t, [
                concreteTaggedValue('tag-a', 'a'),
                concreteTaggedValue('tag-n1', null),
                concreteTaggedValue('tag-b', 'b'),
                concreteTaggedValue('tag-n2', null),
                concreteTaggedValue('tag-c', 'c'),
              ])
            ).toEqual(true);
            return 'abc';
          },
          {dims: 1}
        )
      ).toEqual('abc');
    });

    it('in: Maybe<Tagged<Maybe<T>>>', () => {
      expect(
        mntValueApply(concreteTaggedValue('boolean', 'string'), t => {}, {
          dims: 1,
        })
      ).toEqual(
        undefined // invalid input
      );
      expect(
        mntValueApply(
          concreteTaggedValue('boolean', null),
          t => {
            expect(false).toEqual(true);
            return 42;
          },
          {dims: 1}
        )
      ).toEqual(concreteTaggedValue('boolean', null));
      expect(
        mntValueApply(
          null,
          t => {
            expect(false).toEqual(true);
            return 42;
          },
          {dims: 1}
        )
      ).toEqual(null);
    });

    it('in: List<List<Tagged<T>>>', () => {
      expect(
        mntValueApply(
          [
            [
              concreteTaggedValue('tag-a', 'a'),
              concreteTaggedValue('tag-b', 'b'),
              concreteTaggedValue('tag-c', 'c'),
            ],
            [
              concreteTaggedValue('tag-d', 'd'),
              concreteTaggedValue('tag-e', 'e'),
              concreteTaggedValue('tag-f', 'f'),
            ],
          ],
          t => {
            expect(
              _.isEqual(t, [
                concreteTaggedValue('tag-a', 'a'),
                concreteTaggedValue('tag-b', 'b'),
                concreteTaggedValue('tag-c', 'c'),
              ]) ||
                _.isEqual(t, [
                  concreteTaggedValue('tag-d', 'd'),
                  concreteTaggedValue('tag-e', 'e'),
                  concreteTaggedValue('tag-f', 'f'),
                ])
            ).toEqual(true);
            return t.map((i: any) => i._value).join('');
          },
          {dims: 1}
        )
      ).toEqual(['abc', 'def']);
    });

    it('in: Maybe<List<Tagged<T>>>', () => {
      expect(
        mntValueApply(
          [
            concreteTaggedValue('tag-a', 'a'),
            concreteTaggedValue('tag-b', 'b'),
            concreteTaggedValue('tag-c', 'c'),
          ],
          t => {
            expect(
              _.isEqual(t, [
                concreteTaggedValue('tag-a', 'a'),
                concreteTaggedValue('tag-b', 'b'),
                concreteTaggedValue('tag-c', 'c'),
              ])
            ).toEqual(true);
            return 'abc';
          },
          {dims: 1}
        )
      ).toEqual('abc');
      expect(
        mntValueApply(
          null,
          t => {
            expect(false).toEqual(true);
            return 42;
          },
          {dims: 1}
        )
      ).toEqual(null);
    });

    it('in: Tagged<List<Tagged<T>>>', () => {
      expect(
        mntValueApply(
          concreteTaggedValue('outer', [
            concreteTaggedValue('tag-a', 'a'),
            concreteTaggedValue('tag-b', 'b'),
            concreteTaggedValue('tag-c', 'c'),
          ]),
          t => {
            expect(
              _.isEqual(t, [
                concreteTaggedValue('tag-a', 'a'),
                concreteTaggedValue('tag-b', 'b'),
                concreteTaggedValue('tag-c', 'c'),
              ])
            ).toEqual(true);
            return 'abc';
          },
          {dims: 1}
        )
      ).toEqual(concreteTaggedValue('outer', 'abc'));
    });

    it('in: List<Maybe<Tagged<T>>>', () => {
      expect(
        mntValueApply(
          [
            concreteTaggedValue('tag-a', 'a'),
            null,
            concreteTaggedValue('tag-b', 'b'),
            null,
            concreteTaggedValue('tag-c', 'c'),
          ],
          t => {
            expect(
              _.isEqual(t, [
                concreteTaggedValue('tag-a', 'a'),
                null,
                concreteTaggedValue('tag-b', 'b'),
                null,
                concreteTaggedValue('tag-c', 'c'),
              ])
            ).toEqual(true);
            return 'abc';
          },
          {dims: 1}
        )
      ).toEqual('abc');
    });

    it('in: Tagged<Maybe<Tagged<T>>>', () => {
      expect(
        mntValueApply(
          concreteTaggedValue('outer', concreteTaggedValue('inner', 'string')),
          t => {},
          {dims: 1}
        )
      ).toEqual(
        undefined // invalid input
      );
      expect(
        mntValueApply(
          concreteTaggedValue('outer', null),
          t => {
            expect(false).toEqual(true);
            return 42;
          },
          {dims: 1}
        )
      ).toEqual(concreteTaggedValue('outer', null));
    });
  });
});
