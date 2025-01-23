/**
 * This bar above a grid displays currently set filters for quick editing.
 */

import {Popover} from '@mui/material';
import {GridFilterItem, GridFilterModel} from '@mui/x-data-grid-pro';
import {MOON_150} from '@wandb/weave/common/css/color.styles';
import React, {useCallback, useRef} from 'react';
import styled from 'styled-components';

import {Button} from '../../../../Button';
import {DraggableGrow, DraggableHandle} from '../../../../DraggablePopups';
import {IconDate, IconFilterAlt} from '../../../../Icon';
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
import {GroupedOption, SelectFieldOption} from './SelectField';
import {VariableChildrenDisplay} from './VariableChildrenDisplayer';

type DateRangeFilterBarProps = {
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

export const DateRangeFilterBar = ({
  filterModel,
  setFilterModel,
  columnInfo,
  selectedCalls,
  clearSelectedCalls,
  width,
}: DateRangeFilterBarProps) => {
  const refBar = useRef<HTMLDivElement>(null);
  const refLabel = useRef<HTMLDivElement>(null);
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const onClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(anchorEl ? null : refBar.current);
  };

  const open = Boolean(anchorEl);
  const id = open ? 'simple-popper' : undefined;

  const options: SelectFieldOption[] = [
    {
      label: '',
      options: [
        {
          value: 'started_at',
          label: 'Called',
        },
      ],
    },
  ];

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
        className="border-box flex h-32 cursor-pointer items-center gap-4 rounded border border-moon-200 px-8 hover:border-teal-500/40"
        onClick={onClick}>
        <div>
          <IconDate />
        </div>
        <div ref={refLabel} className="select-none">
          Date range
        </div>
        {/* <VariableChildrenDisplay width={availableWidth} gap={8}>
          {completeItems.map(f => (
            <FilterTagItem
              key={f.id}
              item={f}
              onRemoveFilter={onRemoveFilter}
            />
          ))}
        </VariableChildrenDisplay> */}
        <PreviewPanel>1 month</PreviewPanel>
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
              </div>
            </DraggableHandle>
            <div className="grid grid-cols-[auto_auto_auto_30px] gap-4">
              {filterModel.items.map(item => (
                <FilterRow
                  key={item.id}
                  item={item}
                  options={options}
                  isDisabled={true}
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
                variant="ghost"
                icon="add-new"
                disabled={filterModel.items.length === 0}
                onClick={() => onAddFilter('started_at')}>
                Add filter
              </Button>
              <div className="flex-auto" />
              <Button
                size="small"
                variant="ghost"
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

const PreviewPanel = styled.div<{clickable?: boolean}>`
  padding: 0 4px;
  background-color: ${MOON_150};
  border-radius: 4px;
  margin-left: 4px;
  font-weight: 600;
  font-family: monospace;
  font-size: 10px;
  line-height: 20px;
  cursor: ${props => (props.clickable ? 'pointer' : 'default')};
`;
PreviewPanel.displayName = 'S.IdPanel';
