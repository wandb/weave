import {GridColDef, GridColumnGroupingModel} from '@mui/x-data-grid-pro';

import {TraceCallSchema} from './pages/wfReactInterface/traceServerClient';

// TODO: Move into shared place for calls table
export type ColumnInfo = {
  cols: Array<GridColDef<TraceCallSchema>>;
  colGroupingModel: GridColumnGroupingModel;
};
