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
  isValuelessOperator,
  UNFILTERABLE_FIELDS,
  upsertFilter,
} from './common';
import {FilterRow} from './FilterRow';
import {FilterTagItem} from './FilterTagItem';
import {combineRangeFilters, getNextFilterId} from './filterUtils';
import {GroupedOption, SelectFieldOption} from './SelectField';
import {VariableChildrenDisplay} from './VariableChildrenDisplayer';

const DEBOUNCE_MS = 1_000;

type FilterBarProps = {
  entity: string;
  project: string;
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
    // Empty string is never valid
    filter.value === '' ||
    (filter.value === undefined && !isValuelessOperator(filter.operator))
  );
};

export const FilterBar = ({
  entity,
  project,
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

  // Keep track of incomplete filters that should be preserved during state sync
  const [incompleteFilters, setIncompleteFilters] = useState<GridFilterItem[]>(
    []
  );

  // Merge the parent filter model with our incomplete filters
  useEffect(() => {
    const newItems = [...filterModel.items];

    // Add incomplete filters that aren't in the parent model
    incompleteFilters.forEach(incompleteFilter => {
      if (!newItems.some(item => item.id === incompleteFilter.id)) {
        newItems.push(incompleteFilter);
      }
    });

    setLocalFilterModel({...filterModel, items: newItems});
  }, [filterModel, incompleteFilters]);

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
    const emptyModel = {items: []};
    setLocalFilterModel(emptyModel);
    setFilterModel(emptyModel);
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

  // Only send complete filters to the parent component
  const applyCompletedFilters = useCallback(
    (model: GridFilterModel) => {
      const completeFilters = model.items.filter(
        item => !isFilterIncomplete(item)
      );
      setFilterModel({...model, items: completeFilters});
      setIncompleteFilters(model.items.filter(isFilterIncomplete));
    },
    [setFilterModel]
  );

  const debouncedSetFilterModel = useMemo(
    () => _.debounce(applyCompletedFilters, DEBOUNCE_MS),
    [applyCompletedFilters]
  );

  const onUpdateFilter = useCallback(
    (item: GridFilterItem) => {
      debouncedSetFilterModel.cancel();
      const oldItems = localFilterModel.items;
      const index = oldItems.findIndex(f => f.id === item.id);

      // Set this filter as active edit, highlighting filter bar children in teal
      setActiveEditId(item.id);

      if (index === -1) {
        const newModel = {...localFilterModel, items: [item]};
        setLocalFilterModel(newModel);
        debouncedSetFilterModel(newModel);
        return;
      }

      const newItems = [
        ...oldItems.slice(0, index),
        item,
        ...oldItems.slice(index + 1),
      ];
      const newItemsModel = {...localFilterModel, items: newItems};
      setLocalFilterModel(newItemsModel);
      debouncedSetFilterModel(newItemsModel);
    },
    [localFilterModel, debouncedSetFilterModel]
  );

  const onRemoveFilter = useCallback(
    (filterId: FilterId) => {
      const items = localFilterModel.items.filter(f => f.id !== filterId);
      const newModel = {...localFilterModel, items};
      setLocalFilterModel(newModel);
      applyCompletedFilters(newModel);

      // Clear active edit if removed
      if (activeEditId === filterId) {
        setActiveEditId(null);
      }
    },
    [localFilterModel, applyCompletedFilters, activeEditId]
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

    // Apply filter immediately (won't be incomplete)
    setLocalFilterModel(newModel);
    applyCompletedFilters(newModel);

    clearSelectedCalls();
    setAnchorEl(null);

    // Clear active edit when popover is closed
    setActiveEditId(null);
  }, [
    localFilterModel,
    applyCompletedFilters,
    selectedCalls,
    clearSelectedCalls,
  ]);

  const onFilterTagClick = useCallback((filterId: FilterId) => {
    setActiveEditId(filterId);
    setAnchorEl(refBar.current);
  }, []);

  const outlineW = 2 * 2;
  const paddingW = 8 * 2;
  const iconW = 20;
  const gapW = 4 * 2; // Between icon and label and label and tags.
  const labelW = refLabel.current?.offsetWidth ?? 0;
  const availableWidth = width - outlineW - paddingW - iconW - labelW - gapW;

  const completeItems = localFilterModel.items.filter(
    f => !isFilterIncomplete(f)
  );

  // Determine if we should show a border based on whether there are active filters
  const hasBorder = completeItems.length > 0;

  const {combinedItems, activeEditIds} = useMemo(() => {
    const {items, activeIds} = combineRangeFilters(completeItems, activeEditId);
    return {combinedItems: items, activeEditIds: activeIds};
  }, [completeItems, activeEditId]);

  return (
    <>
      <div
        ref={refBar}
        className={`border-box flex h-32 cursor-pointer items-center gap-4 rounded px-8 ${
          hasBorder
            ? 'border border-moon-200 hover:border-teal-400 hover:ring-1 hover:ring-teal-400 dark:border-moon-200 dark:hover:border-2 dark:hover:border-teal-400'
            : ''
        } ${
          !hasBorder ? 'hover:bg-teal-300/[0.48] dark:hover:bg-moon-200' : ''
        }`}
        onClick={onClick}>
        <div>
          <IconFilterAlt />
        </div>
        <div ref={refLabel} className="select-none font-semibold">
          Filter
        </div>
        <VariableChildrenDisplay width={availableWidth} gap={8}>
          {combinedItems.map(f => (
            <FilterTagItem
              key={f.id}
              item={f}
              onRemoveFilter={onRemoveFilter}
              isEditing={activeEditIds.has(f.id) || f.id === activeEditId}
              onClick={() => onFilterTagClick(f.id)}
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
                  entity={entity}
                  project={project}
                  item={item}
                  options={options}
                  onAddFilter={onAddFilter}
                  onUpdateFilter={onUpdateFilter}
                  onRemoveFilter={onRemoveFilter}
                  activeEditId={activeEditId}
                />
              ))}
            </div>
            {localFilterModel.items.length === 0 && (
              <FilterRow
                entity={entity}
                project={project}
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
                activeEditId={activeEditId}
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
