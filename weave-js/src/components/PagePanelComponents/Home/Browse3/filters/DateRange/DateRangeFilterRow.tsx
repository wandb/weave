import {GridFilterItem, GridFilterModel} from '@mui/x-data-grid-pro';
import React, {useEffect, useMemo, useState} from 'react';

// Field name for timestamp in the filter model
export const TIMESTAMP_FIELD = 'started_at';

// Time range options
export const TIME_RANGE_OPTIONS = [
  {id: '1h', display: '1h', value: 'Past 1 hour'},
  {id: '1d', display: '1d', value: 'Past 1 day'},
  {id: '2d', display: '2d', value: 'Past 2 days'},
  {id: '1w', display: '1w', value: 'Past 1 week'},
  {id: '2w', display: '2w', value: 'Past 2 weeks'},
  {id: '1mo', display: '1mo', value: 'Past 1 month'},
];

// Add this type extension
export interface DateRangeGridFilterItem extends GridFilterItem {
  rangeId?: string;
}

type DateRangeFilterRowProps = {
  filterModel: GridFilterModel;
  setFilterModel: (newModel: GridFilterModel) => void;
  onClose: () => void;
  searchText?: string;
};

export const DateRangeFilterRow = ({
  filterModel,
  setFilterModel,
  onClose,
  searchText = '',
}: DateRangeFilterRowProps) => {
  // Find the current time range from the filter model
  const currentTimeRange = useMemo(() => {
    const timestampFilter = filterModel.items.find(
      item => item.field === TIMESTAMP_FIELD
    ) as DateRangeGridFilterItem | undefined;

    if (!timestampFilter) return '1w';

    // Extract the time range from the filter value
    if (timestampFilter.rangeId) {
      return timestampFilter.rangeId;
    }

    return '1w'; // Default to 1 week if not found
  }, [filterModel]);

  const [selectedRange, setSelectedRange] = useState(currentTimeRange);

  // Update selected range when filter model changes
  useEffect(() => {
    setSelectedRange(currentTimeRange);
  }, [currentTimeRange]);

  // Filter options based on search text
  const filteredOptions = useMemo(() => {
    if (!searchText) return TIME_RANGE_OPTIONS;

    const lowerSearch = searchText.toLowerCase();
    return TIME_RANGE_OPTIONS.filter(
      option =>
        option.display.toLowerCase().includes(lowerSearch) ||
        option.value.toLowerCase().includes(lowerSearch)
    );
  }, [searchText]);

  const handleRangeSelect = (rangeId: string) => {
    if (rangeId === 'calendar') {
      handleCalendarSelect();
      return;
    }

    setSelectedRange(rangeId);

    // Calculate the date range based on the selected option
    const now = new Date();
    let startDate: Date;

    switch (rangeId) {
      case 'live':
        startDate = new Date(now.getTime() - 15 * 60 * 1000);
        break;
      case '15m':
        startDate = new Date(now.getTime() - 15 * 60 * 1000);
        break;
      case '30m':
        startDate = new Date(now.getTime() - 30 * 60 * 1000);
        break;
      case '1h':
        startDate = new Date(now.getTime() - 60 * 60 * 1000);
        break;
      case '4h':
        startDate = new Date(now.getTime() - 4 * 60 * 60 * 1000);
        break;
      case '1d':
        startDate = new Date(now.getTime() - 24 * 60 * 60 * 1000);
        break;
      case '2d':
        startDate = new Date(now.getTime() - 2 * 24 * 60 * 60 * 1000);
        break;
      case '1w':
        startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        break;
      case '2w':
        startDate = new Date(now.getTime() - 14 * 24 * 60 * 60 * 1000);
        break;
      default:
        startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000); // Default to 1 week
    }

    // Format dates for the filter
    const startTimestamp = startDate.toISOString();
    const endTimestamp = now.toISOString();

    // Create or update the timestamp filter
    const existingFilterIndex = filterModel.items.findIndex(
      item => item.field === TIMESTAMP_FIELD
    );

    const newFilterItem: DateRangeGridFilterItem = {
      id:
        existingFilterIndex >= 0
          ? filterModel.items[existingFilterIndex].id
          : filterModel.items.length,
      field: TIMESTAMP_FIELD,
      operator: '(date): after',
      value: startTimestamp,
      // Store the range ID for display purposes
      rangeId: rangeId,
    };

    let updatedItems;
    if (existingFilterIndex >= 0) {
      // Replace existing timestamp filter
      updatedItems = [
        ...filterModel.items.slice(0, existingFilterIndex),
        newFilterItem,
        ...filterModel.items.slice(existingFilterIndex + 1),
      ];
    } else {
      // Add new timestamp filter
      updatedItems = [...filterModel.items, newFilterItem];
    }

    const updatedModel = {
      ...filterModel,
      items: updatedItems,
    };

    setFilterModel(updatedModel);
    onClose(); // Close the popover after selection
  };

  const handleCalendarSelect = () => {
    // Implement calendar selection logic
    console.log('Open calendar selection');
  };

  return (
    <div className="w-full">
      <div className="grid grid-cols-1 gap-2">
        {filteredOptions.map(option => (
          <div
            key={option.id}
            className={`cursor-pointer rounded p-2 hover:bg-moon-100 ${
              selectedRange === option.id ? 'bg-moon-200' : ''
            }`}
            onClick={() => handleRangeSelect(option.id)}>
            <div className="font-medium">{option.display}</div>
            <div className="text-gray-600 text-sm">{option.value}</div>
          </div>
        ))}
        <div
          className="mt-2 cursor-pointer rounded border-t border-moon-200 p-2 pt-4 hover:bg-moon-100"
          onClick={() => handleRangeSelect('calendar')}>
          <div className="font-medium">Custom Range</div>
          <div className="text-gray-600 text-sm">Select from calendar...</div>
        </div>
      </div>
    </div>
  );
};
