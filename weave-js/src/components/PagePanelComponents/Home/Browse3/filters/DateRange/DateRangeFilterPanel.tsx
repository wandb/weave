import {GridFilterModel} from '@mui/x-data-grid-pro';
import {LocalizationProvider} from '@mui/x-date-pickers';
import {AdapterMoment} from '@mui/x-date-pickers/AdapterMoment';
import React from 'react';
import {AutoSizer} from 'react-virtualized';

import {DateRangeFilterBar} from './DateRangeFilterBar';

type FilterPanelProps = {
  filterModel: GridFilterModel;
  setFilterModel: (newModel: GridFilterModel) => void;
};

export const DateRangeFilterPanel = (props: FilterPanelProps) => {
  return (
    <div className="min-w-90 flex-auto self-stretch">
      <LocalizationProvider dateAdapter={AdapterMoment}>
        <AutoSizer
          className="ml-2 flex items-center"
          style={{
            width: '100%',
            height: '100%',
          }}>
          {({width, height}) => (
            <DateRangeFilterBar {...props} width={width} height={height} />
          )}
        </AutoSizer>
      </LocalizationProvider>
    </div>
  );
};
