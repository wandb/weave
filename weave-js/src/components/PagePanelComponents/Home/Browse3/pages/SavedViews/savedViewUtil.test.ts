import {
  Filters,
  filtersToQuery,
  queryToFilters,
  toSeconds,
} from './savedViewUtil';

describe('toSeconds', () => {
  it('handles null input', () => {
    expect(toSeconds(null)).toBeNull();
  });
  it('returns null for empty string', () => {
    expect(toSeconds('')).toBeNull();
  });
  it('returns number for number', () => {
    expect(toSeconds(1)).toEqual(1);
  });
  it('returns number for number string', () => {
    expect(toSeconds('1')).toEqual(1);
  });
  it('returns number for float', () => {
    expect(toSeconds(1.5)).toEqual(1.5);
  });
  it('returns number for float string', () => {
    expect(toSeconds('1.5')).toEqual(1.5);
  });
  it('returns number for date string', () => {
    expect(toSeconds('2025-03-02T00:00:00Z')).toEqual(1740873600.0);
  });
  it('returns number for date', () => {
    expect(toSeconds(new Date('2025-03-02T00:00:00Z'))).toBe(1740873600.0);
  });
});

describe('filtersToQuery', () => {
  it('handles null input', () => {
    expect(filtersToQuery(null)).toBeNull();
  });
  it('handles empty array input', () => {
    expect(filtersToQuery([])).toBeNull();
  });
});

describe('queryToFilters', () => {
  it('handles undefined input', () => {
    expect(queryToFilters()).toBeNull();
  });
  it('handles null input', () => {
    expect(queryToFilters(null)).toBeNull();
  });
  it('converts one filter - gt number', () => {
    const query = {
      $expr: {
        $gt: [{$getField: 'completion_token_cost'}, {$literal: 25}],
      },
    };
    expect(queryToFilters(query)).toEqual([
      {
        field: 'completion_token_cost',
        operator: '(number): >',
        value: 25,
      },
    ]);
  });
  it('converts one filter - equals str', () => {
    const query = {
      $expr: {
        $eq: [{$getField: 'inputs.model'}, {$literal: 'gpt-4o-mini'}],
      },
    };
    expect(queryToFilters(query)).toEqual([
      {
        field: 'inputs.model',
        operator: '(string): equals',
        value: 'gpt-4o-mini',
      },
    ]);
  });
  it('converts multiple filters', () => {
    const query = {
      $expr: {
        $and: [
          {
            $eq: [{$getField: 'inputs.model'}, {$literal: 'gpt-4o-mini'}],
          },
          {
            $eq: [{$getField: 'output.object'}, {$literal: 'chat.completion'}],
          },
        ],
      },
    };
    expect(queryToFilters(query)).toEqual([
      {
        field: 'inputs.model',
        operator: '(string): equals',
        value: 'gpt-4o-mini',
      },
      {
        field: 'output.object',
        operator: '(string): equals',
        value: 'chat.completion',
      },
    ]);
  });
});

describe('roundtrip conversion', () => {
  it('handles many cases', () => {
    const cases: Filters = [
      {field: 'test', operator: '(string): contains', value: 'foo'},
      {field: 'test', operator: '(string): equals', value: 'foo'},
      // {field: 'test', operator: '(string): in', value: ['A', 'B', 'C']},
      {field: 'test', operator: '(number): =', value: 42},
      {field: 'test', operator: '(number): !=', value: 42},
      {field: 'test', operator: '(number): <', value: 42},
      {field: 'test', operator: '(number): <=', value: 5.0},
      {field: 'test', operator: '(number): >', value: 42},
      {field: 'test', operator: '(number): >=', value: 5.0},
      // Can't round trip bool, they get converted to string
      // Can't round trip date, they get converted to number
      {field: 'test', operator: '(any): isEmpty', value: null},
      {field: 'test', operator: '(any): isNotEmpty', value: null},
      {field: 'test', operator: '(any): isNull', value: null},
    ];
    for (const c of cases) {
      const filters = [c];
      const query = filtersToQuery(filters);
      const filters2 = queryToFilters(query);
      expect(filters2).toEqual(filters);
    }
  });
});
