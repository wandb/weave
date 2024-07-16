import {GridSortModel} from '@mui/x-data-grid-pro';

import {getValidSortModel} from './sort';

describe('getValidSortModel', () => {
  it('parses a valid sort model', () => {
    const parsed = getValidSortModel(
      '[{"field": "name", "sort": "asc"}, {"field": "age", "sort": "desc"}]'
    );
    expect(parsed).toEqual([
      {
        field: 'name',
        sort: 'asc',
      },
      {
        field: 'age',
        sort: 'desc',
      },
    ]);
  });
  it('returns null on non-array with no explicit default', () => {
    const parsed = getValidSortModel('{}');
    expect(parsed).toEqual(null);
  });
  it('returns null on invalid sort value with no explicit default', () => {
    const parsed = getValidSortModel(
      '[{"field": "name", "sort": "ascending"}, {"field": "age", "sort": "desc"}]'
    );
    expect(parsed).toEqual(null);
  });
  it('returns default on non-array (invalid GridSortModel)', () => {
    const def: GridSortModel = [{field: 'name', sort: 'asc'}];
    const parsed = getValidSortModel('{}', def);
    expect(parsed).toEqual(def);
  });
});
