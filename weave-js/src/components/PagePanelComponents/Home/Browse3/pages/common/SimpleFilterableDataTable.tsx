import {FilterList, LastPage, OpenInNew} from '@mui/icons-material';
import {Badge, Box, List} from '@mui/material';
import IconButton from '@mui/material/IconButton';
import {DataGridPro, GridColDef, GridValidRowModel} from '@mui/x-data-grid-pro';
import React, {useEffect, useMemo, useState} from 'react';
import {useHistory} from 'react-router-dom';

type FilterableTablePropsType<
  DataRowType extends GridValidRowModel,
  CompositeFilterType extends {[key: string]: any} = {[key: string]: any}
> = {
  getInitialData: (filter: CompositeFilterType) => DataRowType[];
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
    filterPredicate: (
      obj: DataRowType,
      filter: Partial<CompositeFilterType>
    ) => boolean;
    filterControlListItem: React.FC<{
      filter: Partial<CompositeFilterType>;
      updateFilter: (update: Partial<CompositeFilterType>) => void;
    }>;
  };
};

export const FilterableTable = <
  DataRowType extends GridValidRowModel,
  CompositeFilterType extends {[key: string]: any} = {[key: string]: any}
>(
  props: FilterableTablePropsType<DataRowType, CompositeFilterType>
) => {
  // Initialize the filter
  const [filterState, setFilterState] = useState(props.initialFilter ?? {});
  // Update the filter when the initial filter changes
  useEffect(() => {
    if (props.initialFilter) {
      setFilterState(props.initialFilter);
    }
  }, [props.initialFilter]);

  // If the caller is controlling the filter, use the caller's filter state
  const filter = useMemo(
    () => (props.onFilterUpdate ? props.initialFilter ?? {} : filterState),
    [filterState, props.initialFilter, props.onFilterUpdate]
  );
  const setFilter = useMemo(
    () => (props.onFilterUpdate ? props.onFilterUpdate : setFilterState),
    [props.onFilterUpdate]
  );

  // Combine the frozen filter with the filter
  const effectiveFilter = useMemo(() => {
    return {...filter, ...props.frozenFilter} as CompositeFilterType;
  }, [filter, props.frozenFilter]);

  // Get the initial data from the caller (note that we pass the filter in in case
  // the caller wants to use it)
  const initialPreFilteredData = useMemo(
    () => props.getInitialData(effectiveFilter),
    [effectiveFilter, props]
  );

  // Apply the filter controls
  const filteredData = useMemo(() => {
    let data = initialPreFilteredData;
    Object.values(props.columns).forEach(column => {
      if (column.filterControls) {
        data = data.filter(obj =>
          column.filterControls!.filterPredicate(obj, effectiveFilter)
        );
      }
    });
    return data;
  }, [effectiveFilter, initialPreFilteredData, props.columns]);

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
            });
          }
          return <React.Fragment key={key}>{col}</React.Fragment>;
        })}
      </>
    );
  }, [effectiveFilter, filter, props.columns, setFilter]);

  return (
    <FilterLayoutTemplate
      filterPopoutTargetUrl={props.getFilterPopoutTargetUrl?.(effectiveFilter)}
      showFilterIndicator={Object.keys(effectiveFilter ?? {}).length > 0}
      showPopoutButton={Object.keys(props.frozenFilter ?? {}).length > 0}
      filterListItems={filterListItems}>
      <DataGridPro
        sx={{border: 0}}
        rows={dataGridRowData}
        rowHeight={38}
        columns={dataGridColumns}
        experimentalFeatures={{columnGrouping: true}}
        disableRowSelectionOnClick
      />
    </FilterLayoutTemplate>
  );
};

export const FilterLayoutTemplate: React.FC<{
  filterPopoutTargetUrl?: string;
  showFilterIndicator?: boolean;
  showPopoutButton?: boolean;
  filterListItems: React.ReactNode;
}> = props => {
  const [isOpen, setIsOpen] = useState(false);
  const history = useHistory();
  return (
    <Box
      sx={{
        flex: '1 1 auto',
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'row',
      }}>
      {props.children}
      <Box
        sx={{
          flex: '0 0 auto',
          height: '100%',
          width: isOpen ? '240px' : '55px',
          transition: 'width 0.1s ease-in-out',
          display: 'flex',
          flexDirection: 'column',
          overflowY: 'auto',
          overflowX: 'hidden',
          borderLeft: '1px solid #e0e0e0',
        }}>
        {isOpen ? (
          <>
            <Box
              sx={{
                pl: 1,
                pr: 1,
                height: 56,
                flex: '0 0 auto',
                borderBottom: '1px solid #e0e0e0',
                position: 'sticky',
                top: 0,
                zIndex: 1,
                backgroundColor: 'white',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}>
              <Box sx={{flex: '0 0 auto'}}>
                <IconButton
                  size="small"
                  onClick={() => {
                    setIsOpen(o => !o);
                  }}>
                  <LastPage />
                </IconButton>
                {props.filterPopoutTargetUrl && props.showPopoutButton && (
                  <IconButton
                    size="small"
                    onClick={() => {
                      if (props.filterPopoutTargetUrl) {
                        history.push(props.filterPopoutTargetUrl);
                      }
                    }}>
                    <OpenInNew />
                  </IconButton>
                )}
              </Box>
              <Box sx={{flex: '0 0 auto', pr: 1}}>Filters</Box>
            </Box>
            <List
              sx={{width: '100%', maxWidth: 360, bgcolor: 'background.paper'}}>
              {props.filterListItems}
            </List>
          </>
        ) : (
          <Box
            sx={{
              height: 56,
              flex: '0 0 auto',
              borderBottom: '1px solid #e0e0e0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
            {props.showFilterIndicator ? (
              <Badge color="primary" variant="dot">
                <IconButton
                  size="small"
                  onClick={() => {
                    setIsOpen(o => !o);
                  }}>
                  <FilterList />
                </IconButton>
              </Badge>
            ) : (
              <IconButton
                size="small"
                onClick={() => {
                  setIsOpen(o => !o);
                }}>
                <FilterList />
              </IconButton>
            )}
          </Box>
        )}
      </Box>
    </Box>
  );
};
