/**
 * This bar above a grid displays currently set filters for quick editing.
 */

import {Popover} from '@mui/material';
import {GridFilterItem, GridFilterModel} from '@mui/x-data-grid-pro';
import React, {useCallback, useRef} from 'react';

import {Button} from '../../../../Button';
import {DraggableGrow, DraggableHandle} from '../../../../DraggablePopups';
import {IconFilterAlt} from '../../../../Icon';
import {Tailwind} from '../../../../Tailwind';
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
import {GroupedOption, SelectFieldOption} from './SelectField';
import {VariableChildrenDisplay} from './VariableChildrenDisplayer';

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
        ...filterModel,
        items: [
          ...filterModel.items,
          {
            id: filterModel.items.length,
            field,
            operator: defaultOperator,
          },
        ],
      };
      setFilterModel(newModel);
    },
    [filterModel, setFilterModel]
  );

  const onUpdateFilter = useCallback(
    (item: GridFilterItem) => {
      const oldItems = filterModel.items;
      const index = oldItems.findIndex(f => f.id === item.id);

      if (index === -1) {
        const newModel2 = {...filterModel, items: [item]};
        setFilterModel(newModel2);
        return;
      }

      const newItems = [
        ...oldItems.slice(0, index),
        item,
        ...oldItems.slice(index + 1),
      ];
      const newModel = {...filterModel, items: newItems};
      setFilterModel(newModel);
    },
    [filterModel, setFilterModel]
  );

  const onRemoveFilter = useCallback(
    (filterId: FilterId) => {
      const items = filterModel.items.filter(f => f.id !== filterId);
      const newModel = {...filterModel, items};
      setFilterModel(newModel);
    },
    [filterModel, setFilterModel]
  );

  const onSetSelected = useCallback(() => {
    const newFilter =
      selectedCalls.length === 1
        ? {
            id: filterModel.items.length,
            field: 'id',
            operator: '(string): equals',
            value: selectedCalls[0],
          }
        : {
            id: filterModel.items.length,
            field: 'id',
            operator: '(string): in',
            value: selectedCalls,
          };
    const newModel = upsertFilter(
      filterModel,
      newFilter,
      f => f.field === 'id'
    );
    setFilterModel(newModel);
    clearSelectedCalls();
    setAnchorEl(null);
  }, [filterModel, setFilterModel, selectedCalls, clearSelectedCalls]);

  const outlineW = 2 * 2;
  const paddingW = 8 * 2;
  const iconW = 20;
  const gapW = 4 * 2; // Between icon and label and label and tags.
  const labelW = refLabel.current?.offsetWidth ?? 0;
  const availableWidth = width - outlineW - paddingW - iconW - labelW - gapW;

  const completeItems = filterModel.items.filter(f => !isFilterIncomplete(f));

  return (
    <>
      <div
        ref={refBar}
        className="flex cursor-pointer items-center gap-4 rounded px-8 py-4 outline outline-moon-250 hover:outline-2 hover:outline-teal-500/40"
        onClick={onClick}>
        <div>
          <IconFilterAlt />
        </div>
        <div ref={refLabel} className="select-none">
          Filter
        </div>
        <VariableChildrenDisplay width={availableWidth} gap={8}>
          {completeItems.map(f => (
            <FilterTagItem
              key={f.id}
              item={f}
              onRemoveFilter={onRemoveFilter}
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
        onClose={() => setAnchorEl(null)}
        TransitionComponent={DraggableGrow}>
        <Tailwind>
          <div className="p-12">
            <DraggableHandle>
              <div className="handle flex items-center pb-12">
                <div className="flex-auto font-semibold">Filters</div>
                {selectedCalls.length > 0 && (
                  <Button size="small" variant="quiet" onClick={onSetSelected}>
                    {`Selected rows (${selectedCalls.length})`}
                  </Button>
                )}
              </div>
            </DraggableHandle>
            <div className="grid grid-cols-[auto_auto_auto_30px] gap-4">
              {filterModel.items.map(item => (
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
            {filterModel.items.length === 0 && (
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
                variant="quiet"
                icon="add-new"
                disabled={filterModel.items.length === 0}
                onClick={() => onAddFilter('')}>
                Add filter
              </Button>
              <div className="flex-auto" />
              <Button
                size="small"
                variant="quiet"
                icon="delete"
                disabled={filterModel.items.length === 0}
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
