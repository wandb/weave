import {Popover} from '@mui/material';
import {GridFilterModel} from '@mui/x-data-grid-pro';
import React, {useEffect, useMemo, useRef, useState} from 'react';

import {DraggableGrow} from '../../../../../DraggablePopups';
import {IconDate} from '../../../../../Icon';
import {Tailwind} from '../../../../../Tailwind';
import {
  DateRangeFilterRow,
  DateRangeGridFilterItem,
  TIME_RANGE_OPTIONS,
  TIMESTAMP_FIELD,
} from './DateRangeFilterRow';

type DateRangeFilterBarProps = {
  filterModel: GridFilterModel;
  setFilterModel: (newModel: GridFilterModel) => void;

  width: number;
  height: number;
};

export const DateRangeFilterBar = ({
  filterModel,
  setFilterModel,
  width,
}: DateRangeFilterBarProps) => {
  const refBar = useRef<HTMLDivElement>(null);
  const refLabel = useRef<HTMLDivElement>(null);
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const [searchText, setSearchText] = useState('');
  const [isEditing, setIsEditing] = useState(false);

  // local filter model is used to avoid triggering a re-render of the trace
  // table on every keystroke. debounced DEBOUNCE_MS ms
  const [localFilterModel, setLocalFilterModel] = useState(filterModel);
  useEffect(() => {
    setLocalFilterModel(filterModel);
  }, [filterModel]);

  const onClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(anchorEl ? null : refBar.current);
    if (!anchorEl) {
      setIsEditing(true);
    }
  };
  const open = Boolean(anchorEl);
  const id = open ? 'simple-popper' : undefined;

  // Get the current date range from filter model
  const dateRangeInfo = useMemo(() => {
    // Find timestamp filter in the model
    const timestampFilter = filterModel.items.find(
      item => item.field === TIMESTAMP_FIELD
    ) as DateRangeGridFilterItem | undefined;

    if (!timestampFilter) {
      const defaultOption = TIME_RANGE_OPTIONS.find(opt => opt.id === '1w');
      return {
        id: '1w',
        display: '1w',
        value: defaultOption?.value || 'Past 1 Week',
      };
    }

    // If the filter has a rangeId property, use that
    if (timestampFilter.rangeId) {
      const option = TIME_RANGE_OPTIONS.find(
        opt => opt.id === timestampFilter.rangeId
      );
      return {
        id: timestampFilter.rangeId,
        display: option?.display || timestampFilter.rangeId,
        value: option?.value || '',
      };
    }

    // Otherwise try to determine from the timestamp value
    const value = timestampFilter.value?.toString() || '';

    // Try to match with one of our time range options
    for (const option of TIME_RANGE_OPTIONS) {
      if (value.includes(option.id)) {
        return {
          id: option.id,
          display: option.display,
          value: option.value,
        };
      }
    }
    const defaultOption = TIME_RANGE_OPTIONS.find(opt => opt.id === '1w');
    return {
      id: '1w',
      display: '1w',
      value: defaultOption?.value || 'Past 1 Week',
    };
  }, [filterModel]);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchText(e.target.value);
  };

  const handleClose = () => {
    setAnchorEl(null);
    setIsEditing(false);
    setSearchText('');
  };

  return (
    <>
      <div
        ref={refBar}
        className="border-box flex h-32 cursor-pointer items-center gap-4 rounded border border-moon-200 px-8 hover:border-teal-500/40"
        onClick={onClick}>
        {isEditing ? (
          <HeaderInput
            searchText={searchText}
            handleSearchChange={handleSearchChange}
            dateRangeInfo={dateRangeInfo}
          />
        ) : (
          <HeaderText
            smallValue={dateRangeInfo.value}
            fullText={dateRangeInfo.display}
            expanded={isEditing}
          />
        )}
      </div>
      <Popover
        id={id}
        open={open}
        anchorEl={anchorEl}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'left',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'left',
        }}
        slotProps={{
          paper: {
            sx: {
              marginTop: '8px',
              overflow: 'visible',
            },
          },
        }}
        onClose={handleClose}
        TransitionComponent={DraggableGrow}>
        <Tailwind>
          <div className="p-12">
            <div className="flex items-center pb-12">
              <div className="flex-auto font-semibold">Date range</div>
            </div>
            <DateRangeFilterRow
              filterModel={localFilterModel}
              setFilterModel={setFilterModel}
              onClose={handleClose}
              searchText={searchText}
            />
          </div>
        </Tailwind>
      </Popover>
    </>
  );
};

const HeaderText = ({
  smallValue,
  fullText,
  expanded,
}: {
  smallValue: string;
  fullText: string;
  expanded: boolean;
}) => {
  return (
    <div className="flex items-center gap-4">
      <IconDate />
      <div className="rounded bg-moon-200 px-4 text-sm">{fullText}</div>
      {expanded && <div className="px-4 text-sm">{smallValue}</div>}
    </div>
  );
};

const HeaderInput = ({
  searchText,
  handleSearchChange,
  dateRangeInfo,
}: {
  searchText: string;
  handleSearchChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  dateRangeInfo: DateRangeInfo;
}) => {
  return (
    <div className="flex items-center gap-4">
      <IconDate />
      <input
        type="text"
        value={searchText}
        onChange={handleSearchChange}
        className="w-full bg-transparent outline-none"
        placeholder={`${dateRangeInfo.display}`}
        autoFocus
      />
    </div>
  );
};
