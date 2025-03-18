/**
 * This bar above a grid displays currently set filters for quick editing.
 */

import {Popover} from '@mui/material';
import {GridFilterItem, GridFilterModel} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';

import {Button} from '../../../../Button';
import {DraggableGrow, DraggableHandle} from '../../../../DraggablePopups';
import {IconFilterAlt} from '../../../../Icon';
import {Tailwind} from '../../../../Tailwind';
import {
  convertFeedbackFieldToBackendFilter,
  parseFeedbackType,
} from '../feedback/HumanFeedback/tsHumanFeedback';
import {ColumnInfo} from '../types';
import {
  FIELD_DESCRIPTIONS,
  FilterId,
  getOperatorOptions,
  isDateOperator,
  isValuelessOperator,
  UNFILTERABLE_FIELDS,
  upsertFilter,
} from './common';
import {FilterRow} from './FilterRow';
import {FilterTagItem} from './FilterTagItem';
import {GroupedOption, SelectFieldOption} from './SelectField';
import {VariableChildrenDisplay} from './VariableChildrenDisplayer';

const DEBOUNCE_MS = 700;

type FilterBarProps = {
  filterModel: GridFilterModel;
  setFilterModel: (newModel: GridFilterModel) => void;
  columnInfo: ColumnInfo;
  selectedCalls: string[];
  clearSelectedCalls: () => void;

  width: number;
  height: number;
};

const isFilterIncomplete = (filter: GridFilterItem): boolean => {
  return (
    filter.field === undefined ||
    (filter.value === undefined && !isValuelessOperator(filter.operator))
  );
};

export const FilterBar = ({
  filterModel,
  setFilterModel,
  columnInfo,
  selectedCalls,
  clearSelectedCalls,
  width,
}: FilterBarProps) => {
  const refBar = useRef<HTMLDivElement>(null);
  const refLabel = useRef<HTMLDivElement>(null);
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);

  // local filter model is used to avoid triggering a re-render of the trace
  // table on every keystroke. debounced DEBOUNCE_MS ms
  const [localFilterModel, setLocalFilterModel] = useState(filterModel);
  const [activeEditId, setActiveEditId] = useState<FilterId | null>(null);
  useEffect(() => {
    setLocalFilterModel(filterModel);
  }, [filterModel]);

  const onClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(anchorEl ? null : refBar.current);
  };

  const open = Boolean(anchorEl);
  const id = open ? 'simple-popper' : undefined;

  // TODO: Make not calls specific by using colGroupingModel
  const {cols} = columnInfo;
  const options: SelectFieldOption[] = [
    {
      label: 'Metadata',
      options: [],
    },
    {
      label: 'inputs',
      options: [],
    },
    {
      label: 'output',
      options: [],
    },
    {
      label: 'attributes',
      options: [],
    },
  ];
  for (const col of cols) {
    if (UNFILTERABLE_FIELDS.includes(col.field)) {
      continue;
    }
    if (col.field.startsWith('inputs.')) {
      (options[1] as GroupedOption).options.push({
        value: col.field,
        label: (col.headerName ?? col.field).substring('inputs.'.length),
      });
    } else if (col.field === 'output') {
      (options[2] as GroupedOption).options.push({
        value: col.field,
        label: col.headerName ?? col.field,
      });
    } else if (col.field.startsWith('output.')) {
      (options[2] as GroupedOption).options.push({
        value: col.field,
        label: (col.headerName ?? col.field).substring('output.'.length),
      });
    } else if (col.field.startsWith('attributes.')) {
      (options[3] as GroupedOption).options.push({
        value: col.field,
        label: (col.headerName ?? col.field).substring('attributes.'.length),
        description: FIELD_DESCRIPTIONS[col.field],
      });
    } else if (
      col.field.startsWith('summary.weave.feedback.wandb.annotation')
    ) {
      const parsed = parseFeedbackType(col.field);
      if (!parsed) {
        continue;
      }
      const backendFilter = convertFeedbackFieldToBackendFilter(parsed.field);
      (options[0] as GroupedOption).options.push({
        value: backendFilter,
        label: parsed ? parsed.displayName : col.field,
      });
    } else {
      (options[0] as GroupedOption).options.push({
        value: col.field,
        label: col.headerName ?? col.field,
        description: FIELD_DESCRIPTIONS[col.field],
      });
    }
  }
  (options[0] as GroupedOption).options.unshift({
    value: 'id',
    label: 'Call ID',
  });

  const onRemoveAll = () => {
    setFilterModel({items: []});
    setAnchorEl(null);
  };

  const onAddFilter = useCallback(
    (field: string) => {
      const defaultOperator = getOperatorOptions(field)[0].value;
      const newModel = {
        ...localFilterModel,
        items: [
          ...localFilterModel.items,
          {
            id: getNextFilterId(localFilterModel.items),
            field,
            operator: defaultOperator,
          },
        ],
      };
      setLocalFilterModel(newModel);
    },
    [localFilterModel]
  );

  const debouncedSetFilterModel = useMemo(
    () =>
      _.debounce(
        (newModel: GridFilterModel) => setFilterModel(newModel),
        DEBOUNCE_MS
      ),
    [setFilterModel]
  );
  const updateLocalAndDebouncedFilterModel = useCallback(
    (newModel: GridFilterModel) => {
      setLocalFilterModel(newModel);
      debouncedSetFilterModel(newModel);
    },
    [debouncedSetFilterModel]
  );

  const onUpdateFilter = useCallback(
    (item: GridFilterItem) => {
      const oldItems = localFilterModel.items;
      const index = oldItems.findIndex(f => f.id === item.id);

      // Set this filter as the active edit
      setActiveEditId(item.id);

      // Whether it's a new filter or updating an existing one,
      // always preserve other filters
      const newItems =
        index === -1
          ? [...oldItems, item] // Append new filter
          : [...oldItems.slice(0, index), item, ...oldItems.slice(index + 1)]; // Update existing filter

      const newItemsModel = {...localFilterModel, items: newItems};
      updateLocalAndDebouncedFilterModel(newItemsModel);
    },
    [localFilterModel, updateLocalAndDebouncedFilterModel]
  );

  const onRemoveFilter = useCallback(
    (filterId: FilterId) => {
      const items = localFilterModel.items.filter(f => f.id !== filterId);
      const newModel = {...localFilterModel, items};
      setLocalFilterModel(newModel);
      setFilterModel(newModel);

      // Clear active edit if removed
      if (activeEditId === filterId) {
        setActiveEditId(null);
      }
    },
    [localFilterModel, setFilterModel, activeEditId]
  );

  const onSetSelected = useCallback(() => {
    const newFilter =
      selectedCalls.length === 1
        ? {
            id: getNextFilterId(localFilterModel.items),
            field: 'id',
            operator: '(string): equals',
            value: selectedCalls[0],
          }
        : {
            id: getNextFilterId(localFilterModel.items),
            field: 'id',
            operator: '(string): in',
            value: selectedCalls,
          };
    const newModel = upsertFilter(
      localFilterModel,
      newFilter,
      f => f.field === 'id'
    );
    setFilterModel(newModel);
    clearSelectedCalls();
    setAnchorEl(null);

    // Clear active edit when popover is closed
    setActiveEditId(null);
  }, [localFilterModel, setFilterModel, selectedCalls, clearSelectedCalls]);

  const outlineW = 2 * 2;
  const paddingW = 8 * 2;
  const iconW = 20;
  const gapW = 4 * 2; // Between icon and label and label and tags.
  const labelW = refLabel.current?.offsetWidth ?? 0;
  const availableWidth = width - outlineW - paddingW - iconW - labelW - gapW;

  const completeItems = localFilterModel.items.filter(
    f => !isFilterIncomplete(f)
  );

  const {combinedItems, activeIds} = useMemo(() => {
    const {items: combinedItems, activeIds} = combineRangeFilters(
      completeItems,
      activeEditId
    );
    return {combinedItems, activeIds};
  }, [completeItems, activeEditId]);

  return (
    <>
      <div
        ref={refBar}
        className="border-box flex h-32 cursor-pointer items-center gap-4 rounded border border-moon-200 px-8 hover:border-teal-500/40"
        onClick={onClick}>
        <div>
          <IconFilterAlt />
        </div>
        <div ref={refLabel} className="select-none">
          Filter
        </div>
        <VariableChildrenDisplay width={availableWidth} gap={8}>
          {combinedItems.map(f => (
            <FilterTagItem
              key={f.id}
              item={f}
              onRemoveFilter={onRemoveFilter}
              isEditing={activeIds.has(f.id) || f.id === activeEditId}
            />
          ))}
        </VariableChildrenDisplay>
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
        onClose={() => {
          setAnchorEl(null);
          setActiveEditId(null); // Clear active edit when popover is closed
        }}
        TransitionComponent={DraggableGrow}>
        <Tailwind>
          <div className="p-12">
            <DraggableHandle>
              <div className="handle flex items-center pb-12">
                <div className="flex-auto font-semibold">Filters</div>
                {selectedCalls.length > 0 && (
                  <Button size="small" variant="ghost" onClick={onSetSelected}>
                    {`Selected rows (${selectedCalls.length})`}
                  </Button>
                )}
              </div>
            </DraggableHandle>
            <div className="grid grid-cols-[auto_auto_auto_30px] gap-4">
              {localFilterModel.items.map(item => (
                <FilterRow
                  key={item.id}
                  item={item}
                  options={options}
                  onAddFilter={onAddFilter}
                  onUpdateFilter={onUpdateFilter}
                  onRemoveFilter={onRemoveFilter}
                />
              ))}
            </div>
            {localFilterModel.items.length === 0 && (
              <FilterRow
                item={{
                  id: undefined,
                  field: '',
                  operator: '',
                  value: undefined,
                }}
                options={options}
                onAddFilter={onAddFilter}
                onUpdateFilter={onUpdateFilter}
                onRemoveFilter={onRemoveFilter}
              />
            )}
            <div className="mt-8 flex items-center">
              <Button
                size="small"
                variant="ghost"
                icon="add-new"
                disabled={localFilterModel.items.length === 0}
                onClick={() => onAddFilter('')}>
                Add filter
              </Button>
              <div className="flex-auto" />
              <Button
                size="small"
                variant="ghost"
                icon="delete"
                disabled={localFilterModel.items.length === 0}
                onClick={onRemoveAll}>
                Remove all
              </Button>
            </div>
          </div>
        </Tailwind>
      </Popover>
    </>
  );
};

const getNextFilterId = (items: GridFilterItem[]): number => {
  if (items.length === 0) {
    return 0;
  }
  const ids = items.map(item => {
    const id = item.id;
    if (id == null) {
      return 0;
    }
    return typeof id === 'number' ? id : parseInt(String(id), 10) || 0;
  });
  return Math.max(...ids) + 1;
};

// Helper to combine before/after filters for the same field
const combineRangeFilters = (
  items: GridFilterItem[],
  activeEditId: FilterId | null
): {items: GridFilterItem[]; activeIds: Set<FilterId>} => {
  const result: GridFilterItem[] = [];
  const dateRanges = new Map<
    string,
    {before?: GridFilterItem; after?: GridFilterItem}
  >();
  const activeIds = new Set<FilterId>();

  items.forEach(item => {
    if (
      isDateOperator(item.operator) &&
      (item.operator === '(date): before' || item.operator === '(date): after')
    ) {
      const range = dateRanges.get(item.field) || {};
      if (item.operator === '(date): before') {
        range.before = item;
      } else {
        range.after = item;
      }
      dateRanges.set(item.field, range);
    } else {
      result.push(item);
    }
  });

  // Add combined range filters
  dateRanges.forEach((range, field) => {
    if (range.before && range.after) {
      // Create a special combined filter
      const combinedFilter = {
        ...range.before,
        operator: '(date): range',
        value: {
          before: range.before.value,
          after: range.after.value,
        },
      };
      result.push(combinedFilter);

      // If either the before or after filter is being edited, add both IDs to activeIds
      if (activeEditId === range.before.id || activeEditId === range.after.id) {
        activeIds.add(range.before.id);
        activeIds.add(range.after.id);
      }
    } else {
      // Add individual filters back if we don't have both before and after
      if (range.before) {
        result.push(range.before);
      }
      if (range.after) {
        result.push(range.after);
      }
    }
  });

  return {items: result, activeIds};
};
