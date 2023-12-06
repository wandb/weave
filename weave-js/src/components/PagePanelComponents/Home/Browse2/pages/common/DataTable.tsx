import {GridColDef} from '@mui/x-data-grid-pro';

export const basicField = (
  field: string,
  headerName: string,
  extra?: Partial<GridColDef>
): GridColDef => {
  if (extra?.width) {
    extra.minWidth = extra.width;
    extra.maxWidth = extra.width;
  }
  return {
    field,
    headerName,
    flex: extra?.flex ?? 1,
    minWidth: extra?.minWidth ?? 100,
    ...extra,
  };
};
