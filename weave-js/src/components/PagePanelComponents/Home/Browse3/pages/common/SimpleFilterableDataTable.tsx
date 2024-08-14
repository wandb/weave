import {Box, SxProps} from '@mui/material';
import {
  GridColDef,
  GridRowSelectionModel,
  GridValidRowModel,
} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {useEffect, useMemo, useState} from 'react';

import {StyledDataGrid} from '../../StyledDataGrid';
import {useControllableState, useURLSearchParamsDict} from '../util';

type FilterableTablePropsType<
  DataRowType extends GridValidRowModel,
  CompositeFilterType extends {[key: string]: any} = {[key: string]: any}
> = {
  getInitialData: () => DataRowType[];
  columns: WFHighLevelDataColumnDictType<DataRowType, CompositeFilterType>;
  getFilterPopoutTargetUrl?: (filter: CompositeFilterType) => string;
  frozenFilter?: Partial<CompositeFilterType>;
  initialFilter?: Partial<CompositeFilterType>;
  // Setting this will make the component a controlled component. The parent
  // is responsible for updating the filter.
  onFilterUpdate?: (filter: CompositeFilterType) => void;
};

export type WFHighLevelDataColumnDictType<
  DataRowType extends GridValidRowModel,
  CompositeFilterType extends {[key: string]: any} = {[key: string]: any}
> = {
  [columnIdKey: string]: WFHighLevelDataColumn<
    DataRowType,
    any,
    any,
    string,
    CompositeFilterType
  >;
};

export type WFHighLevelDataColumn<
  DataRowType extends GridValidRowModel,
  FilterType,
  ValueType extends string | number | boolean | null,
  ColumnIdType extends string,
  CompositeFilterType = {[key: string]: any} & {
    [key in ColumnIdType]: FilterType;
  }
> = {
  columnId: ColumnIdType;
  // If present, this column is displayed in the grid
  gridDisplay?: {
    columnLabel: string;
    // Value used by datagrid for sorting, filtering, etc...
    columnValue: (obj: DataRowType) => ValueType;
    gridColDefOptions?: Partial<GridColDef<DataRowType, ValueType>>;
  };
  // If present, filtering for this column is enabled
  filterControls?: {
    filterKeys: string[];
    filterPredicate: (
      obj: DataRowType,
      filter: Partial<CompositeFilterType>
    ) => boolean;
    filterControlListItem: React.FC<{
      filter: Partial<CompositeFilterType>;
      updateFilter: (update: Partial<CompositeFilterType>) => void;
      frozenData: DataRowType[];
    }>;
  };
};

export const FilterableTable = <
  DataRowType extends GridValidRowModel,
  CompositeFilterType extends {[key: string]: any} = {[key: string]: any}
>(
  props: FilterableTablePropsType<DataRowType, CompositeFilterType>
) => {
  const [filter, setFilter] = useControllableState(
    (props.initialFilter ?? {}) as CompositeFilterType,
    props.onFilterUpdate
  );

  // Combine the frozen filter with the filter
  const effectiveFilter = useMemo(() => {
    return {...filter, ...props.frozenFilter} as CompositeFilterType;
  }, [filter, props.frozenFilter]);

  // Get the initial data from the caller
  const initialPreFilteredData = useMemo(() => props.getInitialData(), [props]);
  const {filteredData: frozenData} = useMemo(() => {
    let data = initialPreFilteredData;
    const ff = props.frozenFilter;
    if (ff != null) {
      Object.values(props.columns).forEach(column => {
        if (column.filterControls) {
          data = data.filter(obj =>
            column.filterControls!.filterPredicate(obj, ff)
          );
        }
      });
    }
    return {filteredData: data};
  }, [initialPreFilteredData, props.columns, props.frozenFilter]);

  // Apply the filter controls
  const {filteredData, filteredColData} = useMemo(() => {
    let data = frozenData;
    const colData = _.mapValues(props.columns, () => frozenData);
    Object.entries(props.columns).forEach(([key, column]) => {
      if (column.filterControls) {
        data = data.filter(obj =>
          column.filterControls!.filterPredicate(obj, filter)
        );
        // UG, nasty n^2 loop
        Object.entries(props.columns).forEach(([innerKey, innerColumn]) => {
          if (innerKey === key || !innerColumn.filterControls) {
            return;
          }
          colData[key] = colData[key].filter(obj =>
            innerColumn.filterControls!.filterPredicate(
              obj,
              _.omit(
                filter,
                column.filterControls!.filterKeys
              ) as Partial<CompositeFilterType>
            )
          );
        });
      }
    });
    return {filteredData: data, filteredColData: colData};
  }, [filter, frozenData, props.columns]);

  // Apply the data transformations
  const dataGridRowData = useMemo(() => {
    return filteredData.map(obj => {
      const rowData: {[columnId: string]: any} = {...obj};
      Object.values(props.columns).forEach(column => {
        if (column.gridDisplay) {
          rowData[column.columnId] = column.gridDisplay.columnValue(obj);
        }
      });
      return rowData as DataRowType;
    });
  }, [filteredData, props.columns]);

  // Create the columns
  const dataGridColumns = useMemo(() => {
    return Object.values(props.columns)
      .filter(column => column.gridDisplay)
      .map(column => {
        return {
          field: column.columnId,
          headerName: column.gridDisplay!.columnLabel,
          flex: column.gridDisplay!.gridColDefOptions?.width ? 0 : 1,
          ...column.gridDisplay!.gridColDefOptions,
        };
      });
  }, [props.columns]);

  // Create the filter UI elements
  const filterListItems = useMemo(() => {
    const filterCurr: {[key: string]: any} = {};
    return (
      <>
        {Object.entries(props.columns).map(([key, column]) => {
          filterCurr[key] = effectiveFilter[key];
          let col = null;
          if (column.filterControls) {
            col = column.filterControls.filterControlListItem({
              filter: filterCurr as Partial<CompositeFilterType>,
              updateFilter: update => {
                setFilter({...filter, ...update} as CompositeFilterType);
              },
              frozenData: filteredColData[key],
            });
          }
          return <React.Fragment key={key}>{col}</React.Fragment>;
        })}
      </>
    );
  }, [effectiveFilter, filter, filteredColData, props.columns, setFilter]);

  // Highlight table row if it matches peek drawer.
  const query = useURLSearchParamsDict();
  const {peekPath} = query;
  const peekId = peekPath ? peekPath.split('/').pop() : null;
  const rowIds = useMemo(() => {
    return dataGridRowData.map(row => row.id);
  }, [dataGridRowData]);
  const [rowSelectionModel, setRowSelectionModel] =
    useState<GridRowSelectionModel>([]);
  useEffect(() => {
    if (rowIds.length === 0) {
      // Data may have not loaded
      return;
    }
    if (peekId == null) {
      // No peek drawer, clear any selection
      setRowSelectionModel([]);
    } else {
      // If peek drawer matches a row, select it.
      // If not, don't modify selection.
      if (rowIds.includes(peekId)) {
        setRowSelectionModel([peekId]);
      }
    }
  }, [rowIds, peekId]);

  return (
    <FilterLayoutTemplate
      filterPopoutTargetUrl={props.getFilterPopoutTargetUrl?.(effectiveFilter)}
      showFilterIndicator={Object.keys(effectiveFilter ?? {}).length > 0}
      showPopoutButton={Object.keys(props.frozenFilter ?? {}).length > 0}
      filterListItems={filterListItems}>
      <StyledDataGrid
        columnHeaderHeight={40}
        rows={dataGridRowData}
        rowHeight={38}
        // Cast to "any" is due to https://github.com/mui/mui-x/issues/6014
        columns={dataGridColumns as any}
        experimentalFeatures={{columnGrouping: true}}
        disableRowSelectionOnClick
        rowSelectionModel={rowSelectionModel}
        initialState={{
          sorting: {sortModel: [{field: 'createdAt', sort: 'desc'}]},
        }}
      />
    </FilterLayoutTemplate>
  );
};

export const FilterLayoutTemplate: React.FC<{
  filterPopoutTargetUrl?: string;
  showFilterIndicator?: boolean;
  showPopoutButton?: boolean;
  filterListItems?: React.ReactNode;
  filterListSx?: SxProps;
}> = props => {
  // const [isOpen, setIsOpen] = useState(false);
  // const history = useHistory();
  return (
    <Box
      sx={{
        flex: '1 1 auto',
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
      }}>
      {props.filterListItems && (
        <Box
          sx={{
            flex: '0 0 auto',
            width: '100%',
            maxWidth: '100%',
            minHeight: 50,
            transition: 'width 0.1s ease-in-out',
            display: 'flex',
            flexDirection: 'row',
            overflowX: 'auto',
            overflowY: 'hidden',
            alignItems: 'center',
            gap: '8px',
            p: 1,
            '& li': {
              padding: 0,
              minWidth: '200px',
            },
            '& input, & label, & .MuiTypography-root': {
              fontSize: '0.875rem',
            },
            ...(props.filterListSx ?? {}),
          }}>
          {props.filterListItems}
        </Box>
      )}
      {props.children}
    </Box>
  );
};
