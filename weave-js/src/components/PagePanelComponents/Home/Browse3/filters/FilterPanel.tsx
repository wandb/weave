/**
 * This gets size information and passes it down.
 */

import {GridFilterModel} from '@mui/x-data-grid-pro';
import {LocalizationProvider} from '@mui/x-date-pickers';
import {AdapterMoment} from '@mui/x-date-pickers/AdapterMoment';
import React from 'react';
import {AutoSizer} from 'react-virtualized';

import {ColumnInfo} from '../types';
import {FilterBar} from './FilterBar';

type FilterPanelProps = {
  filterModel: GridFilterModel;
  setFilterModel: (newModel: GridFilterModel) => void;
  columnInfo: ColumnInfo;
};

export const FilterPanel = (props: FilterPanelProps) => {
  return (
    <div
      style={{
        flex: '1 1 auto',
        alignSelf: 'stretch',
        overflow: 'hidden',
        minWidth: 90,
      }}>
      <LocalizationProvider dateAdapter={AdapterMoment}>
        <AutoSizer
          style={{
            width: '100%',
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            marginLeft: 2,
          }}>
          {({width, height}) => (
            <FilterBar {...props} width={width} height={height} />
          )}
        </AutoSizer>
      </LocalizationProvider>
    </div>
  );
};
