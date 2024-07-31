import {DEFAULT_PAGE_SIZE, getValidPaginationModel} from './pagination';

describe('getValidPaginationModel', () => {
  it('parses valid query values', () => {
    const parsed = getValidPaginationModel('0', '100');
    expect(parsed).toEqual({
      page: 0,
      pageSize: 100,
    });
  });
  it('handles missing page', () => {
    const parsed = getValidPaginationModel(undefined, '50');
    expect(parsed).toEqual({
      page: 0,
      pageSize: 50,
    });
  });
  it('handles missing pageSize', () => {
    const parsed = getValidPaginationModel('42', undefined);
    expect(parsed).toEqual({
      page: 42,
      pageSize: DEFAULT_PAGE_SIZE,
    });
  });
  it('handles invalid page', () => {
    const parsed = getValidPaginationModel('abc', undefined);
    expect(parsed).toEqual({
      page: 0,
      pageSize: DEFAULT_PAGE_SIZE,
    });
  });
  it('handles invalid pageSize', () => {
    const parsed = getValidPaginationModel('1', '-100');
    expect(parsed).toEqual({
      page: 1,
      pageSize: DEFAULT_PAGE_SIZE,
    });
  });
});
