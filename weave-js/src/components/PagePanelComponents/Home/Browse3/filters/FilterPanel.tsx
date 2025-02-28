/**
 * This gets size information and passes it down.
 */

import {GridFilterModel} from '@mui/x-data-grid-pro';
import {LocalizationProvider} from '@mui/x-date-pickers';
import {AdapterMoment} from '@mui/x-date-pickers/AdapterMoment';
import React from 'react';
import {AutoSizer} from 'react-virtualized';

import {WFHighLevelCallFilter} from '../pages/CallsPage/callsTableFilter';
import {OpVersionSchema} from '../pages/wfReactInterface/wfDataModelHooksInterface';
import {ColumnInfo} from '../types';
import {FilterBar} from './FilterBar';

type FilterPanelProps = {
  filterModel: GridFilterModel;
  setFilterModel: (newModel: GridFilterModel) => void;
  columnInfo: ColumnInfo;
  selectedCalls: string[];
  clearSelectedCalls: () => void;

  // op stuff
  frozenFilter: WFHighLevelCallFilter | undefined;
  filter: WFHighLevelCallFilter;
  setFilter: (state: WFHighLevelCallFilter) => void;
  selectedOpVersionOption: string;
  opVersionOptions: Record<
    string,
    {
      title: string;
      ref: string;
      group: string;
      objectVersion?: OpVersionSchema;
    }
  >;
};

export const FilterPanel = (props: FilterPanelProps) => {
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
            <FilterBar {...props} width={width} height={height} />
          )}
        </AutoSizer>
      </LocalizationProvider>
    </div>
  );
};
