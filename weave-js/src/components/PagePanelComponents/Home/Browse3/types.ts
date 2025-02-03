import {GridColDef, GridColumnGroupingModel} from '@mui/x-data-grid-pro';

import {TraceCallSchema} from './pages/wfReactInterface/traceServerClientTypes';

export type ColumnInfo = {
  cols: Array<GridColDef<TraceCallSchema>>;
  colGroupingModel: GridColumnGroupingModel;
};
