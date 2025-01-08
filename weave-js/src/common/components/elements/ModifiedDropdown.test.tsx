import {getAsValidRegex, simpleSearch} from './ModifiedDropdown';

describe('testing regex validity', () => {
  it('should handle basic character classes', () => {
    expect(getAsValidRegex('[a-z]')).toBeInstanceOf(RegExp);
  });

  it('should handle alternation', () => {
    expect(getAsValidRegex('cat|dog')).toBeInstanceOf(RegExp);
  });

  it('should handle quantifiers', () => {
    expect(getAsValidRegex('a{1,3}')).toBeInstanceOf(RegExp);
  });

  it('should handle escaped special characters', () => {
    expect(getAsValidRegex('\\[test\\]')).toBeInstanceOf(RegExp);
  });

  it('should handle complex patterns', () => {
    expect(
      getAsValidRegex('^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+$')
    ).toBeInstanceOf(RegExp);
  });

  it('should reject unmatched parentheses', () => {
    expect(getAsValidRegex('(abc')).toBeNull();
  });

  it('should reject unmatched brackets', () => {
    expect(getAsValidRegex('[abc')).toBeNull();
  });

  it('should reject invalid quantifiers', () => {
    expect(getAsValidRegex('a{2,1}')).toBeNull();
  });

  it('should reject unescaped special characters', () => {
    expect(getAsValidRegex('[')).toBeNull();
  });

  it('should reject invalid character ranges', () => {
    expect(getAsValidRegex('[z-a]')).toBeNull();
  });
});

describe('testing simple search', () => {
  const options = [
    {
      icon: 'wbic-ic-up-arrow',
      text: 'Step',
      value: '_step',
      key: '_step',
    },
    {
      icon: 'wbic-ic-up-arrow',
      text: 'Stepperoni',
      value: '_stepperoni',
      key: '_stepperoni',
    },
    {
      icon: 'wbic-ic-up-arrow',
      text: '99',
      value: 99,
      key: '_99',
    },
    {
      icon: 'calendar',
      text: 'Relative Time (Wall)',
      value: '_absolute_runtime',
      key: '_absolute_runtime',
    },
    {
      icon: 'calendar',
      text: 'Relative Time (Process)',
      value: '_runtime',
      key: '_runtime',
    },
    {
      icon: 'calendar',
      text: 'Wall Time',
      value: '_timestamp',
      key: '_timestamp',
    },
    {
      icon: 'wbic-ic-up-arrow',
      text: 'custom_x',
      value: 'custom_x',
      key: 'custom_x',
    },
    {
      icon: 'wbic-ic-up-arrow',
      text: 'loss',
      value: 'loss',
      key: 'loss',
    },
    {
      icon: 'chart bar',
      text: 'eval/run/1/loss_1024',
      value: 'eval/run/1/loss_1024',
      key: 'eval/run/1/loss_1024',
    },
    {
      icon: 'chart bar',
      text: 'eval/run/1/loss_256',
      value: 'eval/run/1/loss_256',
      key: 'eval/run/1/loss_256',
    },
    {
      icon: 'chart bar',
      text: 'eval/run/1/loss_512',
      value: 'eval/run/1/loss_512',
      key: 'eval/run/1/loss_512',
    },
    {
      icon: 'chart bar',
      text: 'eval/run/2/loss_2048',
      value: 'eval/run/2/loss_2048',
      key: 'eval/run/2/loss_2048',
    },
    {
      icon: 'chart bar',
      text: 'eval/run/2/loss_4096',
      value: 'eval/run/2/loss_4096',
      key: 'eval/run/2/loss_4096',
    },
    {
      icon: 'chart bar',
      text: 'eval/run/2/loss_768',
      value: 'eval/run/2/loss_768',
      key: 'eval/run/2/loss_768',
    },
  ];

  it('simpleSearch matches exact non-regex strings', () => {
    const results = simpleSearch(options, 'loss');
    expect(results.every(r => (r.value as string).includes('loss'))).toBe(true);
  });

  it('simpleSearch matches partial non-regex strings', () => {
    const results = simpleSearch(options, 'loss_');
    expect(results.every(r => (r.value as string).includes('loss_'))).toBe(
      true
    );
  });

  it('simpleSearch matches case-insensitive non-regex strings', () => {
    const results = simpleSearch(options, 'LOSS');
    expect(results.every(r => (r.value as string).includes('loss'))).toBe(true);
  });

  it('simpleSearch matches case-insensitive regex strings', () => {
    const results = simpleSearch(options, 'LOSS', {
      allowRegexSearch: true,
    });
    expect(results.every(r => (r.value as string).includes('loss'))).toBe(true);
  });

  it('simpleSearch matches case-insensitive regex strings', () => {
    const results = simpleSearch(options, 'tep$', {
      allowRegexSearch: true,
    });
    expect(results.length).toBe(1);
    expect(results.every(r => (r.value as string).includes('_step'))).toBe(
      true
    );
  });

  it('simpleSearch matches options with number values', () => {
    const results = simpleSearch(options, '99$', {
      allowRegexSearch: true,
    });
    expect(results.length).toBe(1);
    results.forEach(r => {
      expect(r.value).toEqual(99);
    });
  });

  it('simpleSearch matches all results on * regex string', () => {
    const results = simpleSearch(options, '*', {
      allowRegexSearch: true,
    });
    expect(results.length).toBe(options.length);
  });

  it('simpleSearch can disallow matching regex patterns', () => {
    const results = simpleSearch(options, '.*s.*s.*');
    expect(results.length).toBe(0);
  });

  it('simpleSearch can support matching regex patterns', () => {
    const results = simpleSearch(options, '.*s.*s.*', {
      allowRegexSearch: true,
    });
    expect(results.length).toBeGreaterThan(0);
  });
});
