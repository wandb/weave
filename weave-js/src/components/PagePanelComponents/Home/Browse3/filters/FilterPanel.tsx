/**
 * This gets size information and passes it down.
 */

import {GridFilterModel} from '@mui/x-data-grid-pro';
import {LocalizationProvider} from '@mui/x-date-pickers';
import {AdapterMoment} from '@mui/x-date-pickers/AdapterMoment';
import {useWindowSize} from '@wandb/weave/common/hooks/useWindowSize';
import React from 'react';

import {ColumnInfo} from '../types';
import {FilterBar} from './FilterBar';

type FilterPanelProps = {
  isEvaluateTable: boolean;
  filterModel: GridFilterModel;
  setFilterModel: (newModel: GridFilterModel) => void;
  columnInfo: ColumnInfo;
  selectedCalls: string[];
  clearSelectedCalls: () => void;
};

export const FilterPanel = (props: FilterPanelProps) => {
  const {width: windowWidth} = useWindowSize();
  // 400 = 60(sidebar) + 50 * 3(refresh, export, delete buttons) + 100 * 2 (compare + filter text)
  let maxFilterBarWidth = windowWidth - 400;
  if (!props.isEvaluateTable) {
    // For op filter on traces table
    maxFilterBarWidth -= 300;
  }
  return (
    <div className="min-w-90 flex-auto self-stretch">
      <LocalizationProvider dateAdapter={AdapterMoment}>
        <FilterBar {...props} width={maxFilterBarWidth} height={28} />
      </LocalizationProvider>
    </div>
  );
};
