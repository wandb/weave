import {GridPaginationModel} from '@mui/x-data-grid-pro';

const MAX_PAGE_SIZE = 100;
export const DEFAULT_PAGE_SIZE = 100;

export const getValidPaginationModel = (
  queryPage: string | undefined,
  queryPageSize: string | undefined
): GridPaginationModel => {
  let page = parseInt(queryPage ?? '', 10);
  if (isNaN(page) || page < 0) {
    page = 0;
  }
  let pageSize = parseInt(queryPageSize ?? '', 10);
  if (isNaN(pageSize) || pageSize <= 0 || pageSize > MAX_PAGE_SIZE) {
    pageSize = DEFAULT_PAGE_SIZE;
  }
  return {page, pageSize};
};
