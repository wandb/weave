import {
  constNone,
  constNumber,
  constString,
  constStringList,
} from '../../model';
import {testClient} from '../../testUtil';
import {
  opStringAdd,
  opStringAppend,
  opStringContains,
  opStringEndsWith,
  opStringEqual,
  opStringFindAll,
  opStringIn,
  opStringIsAlnum,
  opStringIsAlpha,
  opStringIsNumeric,
  opStringLeftStrip,
  opStringLen,
  opStringLevenshtein,
  opStringLower,
  opStringNotEqual,
  opStringPartition,
  opStringPrepend,
  opStringReplace,
  opStringRightStrip,
  opStringSlice,
  opStringSplit,
  opStringStartsWith,
  opStringStrip,
  opStringUpper,
} from './string';

describe('opStringEqual', () => {
  it('returns true for equal strings', async () => {
    await expect(
      (
        await testClient()
      ).query(
        opStringEqual({
          lhs: constString(''),
          rhs: constString(''),
        })
      )
    ).resolves.toEqual(true);
    await expect(
      (
        await testClient()
      ).query(
        opStringEqual({
          lhs: constString('foobar'),
          rhs: constString('foobar'),
        })
      )
    ).resolves.toEqual(true);
  });

  it('returns false for non-equal strings', async () => {
    await expect(
      (
        await testClient()
      ).query(
        opStringEqual({
          lhs: constString('foo'),
          rhs: constString('bar'),
        })
      )
    ).resolves.toEqual(false);
    await expect(
      (
        await testClient()
      ).query(
        opStringEqual({
          lhs: constString(''),
          rhs: constString('bar'),
        })
      )
    ).resolves.toEqual(false);
    await expect(
      (
        await testClient()
      ).query(
        opStringEqual({
          lhs: constString('foo'),
          rhs: constString(''),
        })
      )
    ).resolves.toEqual(false);
  });
});

describe('opStringNotEqual', () => {
  it('returns false for equal strings', async () => {
    await expect(
      (
        await testClient()
      ).query(
        opStringNotEqual({
          lhs: constString(''),
          rhs: constString(''),
        })
      )
    ).resolves.toEqual(false);
    await expect(
      (
        await testClient()
      ).query(
        opStringNotEqual({
          lhs: constString('foobar'),
          rhs: constString('foobar'),
        })
      )
    ).resolves.toEqual(false);
  });

  it('returns true for non-equal strings', async () => {
    await expect(
      (
        await testClient()
      ).query(
        opStringNotEqual({
          lhs: constString('foo'),
          rhs: constString('bar'),
        })
      )
    ).resolves.toEqual(true);
    await expect(
      (
        await testClient()
      ).query(
        opStringNotEqual({
          lhs: constString(''),
          rhs: constString('bar'),
        })
      )
    ).resolves.toEqual(true);
    await expect(
      (
        await testClient()
      ).query(
        opStringNotEqual({
          lhs: constString('foo'),
          rhs: constString(''),
        })
      )
    ).resolves.toEqual(true);
  });
});

describe('opStringIn', () => {
  it('correctly handles lhs is a string and rhs is string (substring search)', async () => {
    await expect(
      (
        await testClient()
      ).query(
        opStringIn({
          lhs: constString('bar'),
          rhs: constString('foobarbaz'),
        })
      )
    ).resolves.toEqual(true);
    await expect(
      (
        await testClient()
      ).query(
        opStringEqual({
          lhs: constString('quux'),
          rhs: constString('foobarbaz'),
        })
      )
    ).resolves.toEqual(false);
  });

  it('correctly handles lhs is a string and rhs is a list of strings (exact element search)', async () => {
    await expect(
      (
        await testClient()
      ).query(
        opStringIn({
          lhs: constString('bar'),
          rhs: constStringList(['foo', 'bar', 'baz']),
        })
      )
    ).resolves.toEqual(true);
    await expect(
      (
        await testClient()
      ).query(
        opStringEqual({
          lhs: constString('quux'),
          rhs: constStringList(['foo', 'bar', 'baz']),
        })
      )
    ).resolves.toEqual(false);

    // Expect false because when rhs is string list, we look for exact match only
    await expect(
      (
        await testClient()
      ).query(
        opStringEqual({
          lhs: constString('quux'),
          rhs: constStringList(['foo', 'bar', 'baz', '__quux__']),
        })
      )
    ).resolves.toEqual(false);
  });
});

describe('opStringLen', () => {
  it('returns correct string length', async () => {
    await expect(
      (
        await testClient()
      ).query(
        opStringLen({
          str: constString(''),
        })
      )
    ).resolves.toEqual(0);
    await expect(
      (
        await testClient()
      ).query(
        opStringLen({
          str: constString('foobar'),
        })
      )
    ).resolves.toEqual(6);
    await expect(
      (
        await testClient()
      ).query(
        opStringLen({
          str: constString('W&B is 🚀🦄🔥'),
        })
      )
    ).resolves.toEqual(10);
  });
});

describe('opStringAdd', () => {
  it('concatenates strings', async () => {
    await expect(
      (
        await testClient()
      ).query(
        opStringAdd({
          lhs: constString(''),
          rhs: constString(''),
        })
      )
    ).resolves.toEqual('');
    await expect(
      (
        await testClient()
      ).query(
        opStringAdd({
          lhs: constString('foo'),
          rhs: constString('bar'),
        })
      )
    ).resolves.toEqual('foobar');
    await expect(
      (
        await testClient()
      ).query(
        opStringAdd({
          lhs: constString('foo'),
          rhs: constNone(),
        })
      )
    ).resolves.toEqual('foo');

    // Adding a string to None is still None
    await expect(
      (
        await testClient()
      ).query(
        opStringAdd({
          lhs: constNone(),
          rhs: constString('bar'),
        })
      )
    ).resolves.toEqual(null);
  });
});

describe('opStringAppend', () => {
  it('concatenates suffix to end of str', async () => {
    await expect(
      (
        await testClient()
      ).query(
        opStringAppend({
          str: constString(''),
          suffix: constString(''),
        })
      )
    ).resolves.toEqual('');
    await expect(
      (
        await testClient()
      ).query(
        opStringAppend({
          str: constString('foo'),
          suffix: constString('bar'),
        })
      )
    ).resolves.toEqual('foobar');
  });
});

describe('opStringPrepend', () => {
  it('concatenates prefix to beginning of str', async () => {
    await expect(
      (
        await testClient()
      ).query(
        opStringPrepend({
          str: constString(''),
          prefix: constString(''),
        })
      )
    ).resolves.toEqual('');
    await expect(
      (
        await testClient()
      ).query(
        opStringPrepend({
          str: constString('foo'),
          prefix: constString('bar'),
        })
      )
    ).resolves.toEqual('barfoo');
  });
});

describe('opStringSplit', () => {
  it('splits str by sep, returning list of tokens', async () => {
    await expect(
      (
        await testClient()
      ).query(
        opStringSplit({
          str: constString('foo bar baz'),
          sep: constString(' '),
        })
      )
    ).resolves.toEqual(['foo', 'bar', 'baz']);
  });
});

describe('opStringPartition', () => {
  it('split str into pre, sep, post', async () => {
    await expect(
      (
        await testClient()
      ).query(
        opStringPartition({
          str: constString('foobarbazbar'),
          sep: constString('bar'),
        })
      )
    ).resolves.toEqual(['foo', 'bar', 'bazbar']);
  });
});

describe('opStringStartsWith', () => {
  it('handles (None) prefix correctly', async () => {
    // If prefix is null, always return true
    await expect(
      (
        await testClient()
      ).query(
        opStringStartsWith({
          str: constString(''),
          prefix: constNone(),
        })
      )
    ).resolves.toEqual(true);
    await expect(
      (
        await testClient()
      ).query(
        opStringStartsWith({
          str: constString('foobarbaz'),
          prefix: constNone(),
        })
      )
    ).resolves.toEqual(true);
  });

  it('returns true when prefix is at beginning of str', async () => {
    // If prefix is null, always return true
    await expect(
      (
        await testClient()
      ).query(
        opStringStartsWith({
          str: constString('foobarbaz'),
          prefix: constString('foo'),
        })
      )
    ).resolves.toEqual(true);
    await expect(
      (
        await testClient()
      ).query(
        opStringStartsWith({
          str: constString('🤡barbaz'),
          prefix: constString('🤡'),
        })
      )
    ).resolves.toEqual(true);
  });
  it('returns false when prefix is not at beginning of str', async () => {
    await expect(
      (
        await testClient()
      ).query(
        opStringStartsWith({
          str: constString('foobarbaz'),
          prefix: constString('bar'),
        })
      )
    ).resolves.toEqual(false);
    await expect(
      (
        await testClient()
      ).query(
        opStringStartsWith({
          str: constString('foo🤡baz'),
          prefix: constString('🤡'),
        })
      )
    ).resolves.toEqual(false);
  });
});

describe('opStringEndsWith', () => {
  it('handles (None) suffix correctly', async () => {
    // If suffix is null, always return true
    await expect(
      (
        await testClient()
      ).query(
        opStringEndsWith({
          str: constString(''),
          suffix: constNone(),
        })
      )
    ).resolves.toEqual(true);
    await expect(
      (
        await testClient()
      ).query(
        opStringEndsWith({
          str: constString('foobarbaz'),
          suffix: constNone(),
        })
      )
    ).resolves.toEqual(true);
  });

  it('returns true when suffix is at beginning of str', async () => {
    // If suffix is null, always return true
    await expect(
      (
        await testClient()
      ).query(
        opStringEndsWith({
          str: constString('barbaz'),
          suffix: constString('baz'),
        })
      )
    ).resolves.toEqual(true);
    await expect(
      (
        await testClient()
      ).query(
        opStringEndsWith({
          str: constString('barbaz🤡'),
          suffix: constString('🤡'),
        })
      )
    ).resolves.toEqual(true);
  });
  it('returns false when suffix is not at beginning of str', async () => {
    await expect(
      (
        await testClient()
      ).query(
        opStringEndsWith({
          str: constString('foobarbaz'),
          suffix: constString('bar'),
        })
      )
    ).resolves.toEqual(false);
    await expect(
      (
        await testClient()
      ).query(
        opStringEndsWith({
          str: constString('foo🤡baz'),
          suffix: constString('🤡'),
        })
      )
    ).resolves.toEqual(false);
  });
});

describe('opStringIsAlpha', () => {
  it('correctly detect alphabetic strings', async () => {
    // If suffix is null, always return true
    await expect(
      (
        await testClient()
      ).query(
        opStringIsAlpha({
          str: constString('abcABCxyzXYZ'),
        })
      )
    ).resolves.toEqual(true);
    // Empty string is not considered alpha string?
    await expect(
      (
        await testClient()
      ).query(
        opStringIsAlpha({
          str: constString(''),
        })
      )
    ).resolves.toEqual(false);
    await expect(
      (
        await testClient()
      ).query(
        opStringIsAlpha({
          str: constString('hunter42'),
        })
      )
    ).resolves.toEqual(false);
    await expect(
      (
        await testClient()
      ).query(
        opStringIsAlpha({
          str: constString('a b c'),
        })
      )
    ).resolves.toEqual(false);
  });
});

describe('opStringIsNumeric', () => {
  it('correctly detect numeric strings', async () => {
    // If suffix is null, always return true
    await expect(
      (
        await testClient()
      ).query(
        opStringIsNumeric({
          str: constString('42'),
        })
      )
    ).resolves.toEqual(true);
    await expect(
      (
        await testClient()
      ).query(
        opStringIsNumeric({
          str: constString('-3.14'),
        })
      )
    ).resolves.toEqual(true);
    // Empty string is not considered numeric string?
    await expect(
      (
        await testClient()
      ).query(
        opStringIsNumeric({
          str: constString(''),
        })
      )
    ).resolves.toEqual(false);
    await expect(
      (
        await testClient()
      ).query(
        opStringIsNumeric({
          str: constString('42e10'),
        })
      )
    ).resolves.toEqual(false);
    await expect(
      (
        await testClient()
      ).query(
        opStringIsNumeric({
          str: constString('one hundred'),
        })
      )
    ).resolves.toEqual(false);
    await expect(
      (
        await testClient()
      ).query(
        opStringIsNumeric({
          str: constString('1 1 2 3 5 8'),
        })
      )
    ).resolves.toEqual(false);
  });
});

describe('opStringIsAlnum', () => {
  it('correctly detect alphanumeric strings', async () => {
    // If suffix is null, always return true
    await expect(
      (
        await testClient()
      ).query(
        opStringIsAlnum({
          str: constString('hunter42'),
        })
      )
    ).resolves.toEqual(true);
    await expect(
      (
        await testClient()
      ).query(
        opStringIsAlnum({
          str: constString('42hunter'),
        })
      )
    ).resolves.toEqual(true);
    // Empty string is not considered alphanumeric string?
    await expect(
      (
        await testClient()
      ).query(
        opStringIsAlnum({
          str: constString(''),
        })
      )
    ).resolves.toEqual(false);
    await expect(
      (
        await testClient()
      ).query(
        opStringIsAlnum({
          str: constString('hunter-42'),
        })
      )
    ).resolves.toEqual(false);
    await expect(
      (
        await testClient()
      ).query(
        opStringIsAlnum({
          str: constString('hunter 42'),
        })
      )
    ).resolves.toEqual(false);
    await expect(
      (
        await testClient()
      ).query(
        opStringIsAlnum({
          str: constString('a b c 1 1 2 3 5 8'),
        })
      )
    ).resolves.toEqual(false);
  });
});

describe('opStringLower', () => {
  it('lowercases strings', async () => {
    await expect(
      (
        await testClient()
      ).query(
        opStringLower({
          str: constString('Weights & Biases 🚀'),
        })
      )
    ).resolves.toEqual('weights & biases 🚀');
  });
});

describe('opStringUpper', () => {
  it('uppercases strings', async () => {
    await expect(
      (
        await testClient()
      ).query(
        opStringUpper({
          str: constString('Weights & Biases 🚀'),
        })
      )
    ).resolves.toEqual('WEIGHTS & BIASES 🚀');
  });
});

describe('opStringSlice', () => {
  it('correctly slices strings', async () => {
    await expect(
      (
        await testClient()
      ).query(
        opStringSlice({
          str: constString('weights and biases'),
          begin: constNumber(0),
        })
      )
    ).resolves.toEqual('weights and biases');
    await expect(
      (
        await testClient()
      ).query(
        opStringSlice({
          str: constString('weights and biases'),
          begin: constNumber(0),
          end: constNumber(0),
        })
      )
    ).resolves.toEqual('');
    await expect(
      (
        await testClient()
      ).query(
        opStringSlice({
          str: constString('weights and biases'),
          begin: constNumber(4),
        })
      )
    ).resolves.toEqual('hts and biases');
    await expect(
      (
        await testClient()
      ).query(
        opStringSlice({
          str: constString('weights and biases'),
          begin: constNumber(4),
          end: constNumber(7),
        })
      )
    ).resolves.toEqual('hts');
    await expect(
      (
        await testClient()
      ).query(
        opStringSlice({
          str: constString('weights and biases'),
          begin: constNumber(4),
          end: constNumber(-3),
        })
      )
    ).resolves.toEqual('hts and bia');
    await expect(
      (
        await testClient()
      ).query(
        opStringSlice({
          str: constString('weights and biases'),
          begin: constNumber(4),
          end: constNumber(1000),
        })
      )
    ).resolves.toEqual('hts and biases');
  });
});

describe('opStringReplace', () => {
  it('correctly replace substrings', async () => {
    await expect(
      (
        await testClient()
      ).query(
        opStringReplace({
          str: constString('weights and biases'),
          sub: constString('and'),
          newSub: constString('or'),
        })
      )
    ).resolves.toEqual('weights or biases');
    await expect(
      (
        await testClient()
      ).query(
        opStringReplace({
          str: constString('wandb wandb wandb'),
          sub: constString('wandb'),
          newSub: constString('W&B'),
        })
      )
    ).resolves.toEqual('W&B W&B W&B');
  });
});

describe('opStringFindAll', () => {
  it('correctly find all instances of substring (plain text)', async () => {
    await expect(
      (
        await testClient()
      ).query(
        opStringFindAll({
          str: constString('Weights & Biases'),
          sub: constString('Bias'),
        })
      )
    ).resolves.toEqual(['Bias']);
  });
  it('correctly find all instances of substring (regex)', async () => {
    await expect(
      (
        await testClient()
      ).query(
        opStringFindAll({
          str: constString('weights and/or biases'),
          sub: constString('(or|and)'),
        })
      )
    ).resolves.toEqual(['and', 'or']);
  });
});

describe('opStringContains', () => {
  it('returns true if sub is in str', async () => {
    await expect(
      (
        await testClient()
      ).query(
        opStringContains({
          str: constString('Weights & Biases'),
          sub: constString('&'),
        })
      )
    ).resolves.toEqual(true);
    await expect(
      (
        await testClient()
      ).query(
        opStringContains({
          str: constString('Weights 🚀 Biases'),
          sub: constString('🚀'),
        })
      )
    ).resolves.toEqual(true);
  });

  it('returns true if sub is in str', async () => {
    await expect(
      (
        await testClient()
      ).query(
        opStringContains({
          str: constString('Weights & Biases'),
          sub: constString('or'),
        })
      )
    ).resolves.toEqual(false);
    await expect(
      (
        await testClient()
      ).query(
        opStringContains({
          str: constString('Weights 🚀 Biases'),
          sub: constString('🔥'),
        })
      )
    ).resolves.toEqual(false);
  });
});

describe('opStringStrip', () => {
  it('strips all trailing and leading whitespace', async () => {
    await expect(
      (
        await testClient()
      ).query(
        opStringStrip({
          str: constString('  \t\r\nWeights & Biases\r\n\t  '),
        })
      )
    ).resolves.toEqual('Weights & Biases');
  });
});

describe('opStringLeftStrip', () => {
  it('strips all trailing and leading whitespace', async () => {
    await expect(
      (
        await testClient()
      ).query(
        opStringLeftStrip({
          str: constString('  \t\r\nWeights & Biases\r\n\t  '),
        })
      )
    ).resolves.toEqual('Weights & Biases\r\n\t  ');
  });
});

describe('opStringRightStrip', () => {
  it('strips all trailing and leading whitespace', async () => {
    await expect(
      (
        await testClient()
      ).query(
        opStringRightStrip({
          str: constString('  \t\r\nWeights & Biases\r\n\t  '),
        })
      )
    ).resolves.toEqual('  \t\r\nWeights & Biases');
  });
});

describe('opStringLevenshtein', () => {
  it('returns correct levenshtein distance between words', async () => {
    const WORDS = ['smitten', 'mitten', 'kitty', 'fitting', 'written'];
    const EXPECTED_DISTANCES = [
      [0, 1, 4, 4, 2],
      [1, 0, 3, 3, 2],
      [4, 3, 0, 4, 4],
      [4, 3, 4, 0, 4],
      [2, 2, 4, 4, 0],
    ];
    const distances: any[][] = [[], [], [], [], []];
    // Take words list above and get the distance matrix
    for (let i = 0; i < WORDS.length; i++) {
      for (let j = 0; j < WORDS.length; j++) {
        distances[i][j] = await (
          await testClient()
        ).query(
          opStringLevenshtein({
            str1: constString(WORDS[i]),
            str2: constString(WORDS[j]),
          })
        );
      }
    }
    expect(distances).toEqual(EXPECTED_DISTANCES);
  });
});
