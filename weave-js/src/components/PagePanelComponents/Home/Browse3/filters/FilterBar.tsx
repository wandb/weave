/**
 * This bar above a grid displays currently set filters for quick editing.
 */

import {Autocomplete, FormControl, Popover} from '@mui/material';
import {GridFilterItem, GridFilterModel} from '@mui/x-data-grid-pro';
import {MOON_200, TEAL_300} from '@wandb/weave/common/css/color.styles';
import _ from 'lodash';
import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';

import {Button} from '../../../../Button';
import {DraggableGrow, DraggableHandle} from '../../../../DraggablePopups';
import {Icon, IconFilterAlt} from '../../../../Icon';
import {Tailwind} from '../../../../Tailwind';
import {
  convertFeedbackFieldToBackendFilter,
  parseFeedbackType,
} from '../feedback/HumanFeedback/tsHumanFeedback';
import {ALL_TRACES_OR_CALLS_REF_KEY} from '../pages/CallsPage/callsTableFilter';
import {WFHighLevelCallFilter} from '../pages/CallsPage/callsTableFilter';
import {OpVersionSchema} from '../pages/wfReactInterface/wfDataModelHooksInterface';
import {StyledPaper} from '../StyledAutocomplete';
import {StyledTextField} from '../StyledTextField';
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
import {GroupedOption, SelectField, SelectFieldOption} from './SelectField';
import {VariableChildrenDisplay} from './VariableChildrenDisplayer';

const DEBOUNCE_MS = 700;

type FilterBarProps = {
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
  frozenFilter,
  filter,
  setFilter,
  selectedOpVersionOption,
  opVersionOptions,
}: FilterBarProps) => {
  const refBar = useRef<HTMLDivElement>(null);
  const refLabel = useRef<HTMLDivElement>(null);
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);

  // local filter model is used to avoid triggering a re-render of the trace
  // table on every keystroke. debounced DEBOUNCE_MS ms
  const [localFilterModel, setLocalFilterModel] = useState(filterModel);

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
            id: localFilterModel.items.length,
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

      if (index === -1) {
        const newModel = {...localFilterModel, items: [item]};
        updateLocalAndDebouncedFilterModel(newModel);
        return;
      }

      const newItems = [
        ...oldItems.slice(0, index),
        item,
        ...oldItems.slice(index + 1),
      ];
      const newItemsModel = {...localFilterModel, items: newItems};
      updateLocalAndDebouncedFilterModel(newItemsModel);
    },
    [localFilterModel, updateLocalAndDebouncedFilterModel]
  );

  const onRemoveFilter = useCallback(
    (filterId: FilterId) => {
      if (filterId === 'default-operation') {
        // set the op to None
        setFilter({
          ...filter,
          opVersionRefs: [],
        });
        return;
      }
      const items = localFilterModel.items.filter(f => f.id !== filterId);
      const newModel = {...localFilterModel, items};
      setLocalFilterModel(newModel);
      setFilterModel(newModel);
    },
    [localFilterModel, setFilterModel, setFilter, filter]
  );

  const onSetSelected = useCallback(() => {
    const newFilter =
      selectedCalls.length === 1
        ? {
            id: localFilterModel.items.length,
            field: 'id',
            operator: '(string): equals',
            value: selectedCalls[0],
          }
        : {
            id: localFilterModel.items.length,
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
  }, [localFilterModel, setFilterModel, selectedCalls, clearSelectedCalls]);

  // Handle operation change
  const handleOperationChange = useCallback(
    (event: any, newValue: string | null) => {
      if (!newValue) {
        return;
      }

      // Update the high-level filter directly
      if (newValue === ALL_TRACES_OR_CALLS_REF_KEY) {
        setFilter({
          ...filter,
          opVersionRefs: [],
        });
      } else {
        setFilter({
          ...filter,
          opVersionRefs: [newValue],
        });
      }
    },
    [setFilter, filter]
  );

  const outlineW = 2 * 2;
  const paddingW = 8 * 2;
  const iconW = 20;
  const gapW = 4 * 2; // Between icon and label and label and tags.
  const labelW = refLabel.current?.offsetWidth ?? 0;
  const availableWidth = width - outlineW - paddingW - iconW - labelW - gapW;

  const completeItems = localFilterModel.items.filter(
    f => !isFilterIncomplete(f)
  );

  // Custom renderer for operation filter
  const renderOperationFilter = () => {
    const frozenOpFilter = Object.keys(frozenFilter ?? {}).includes(
      'opVersions'
    );

    return (
      <>
        {/* First column - Field */}
        <div className="min-w-[190px]">
          <SelectField
            options={[
              {
                label: 'operation',
                options: [{value: 'operation', label: 'operation'}],
              },
            ]}
            value="operation"
            onSelectField={() => {}}
            isDisabled={true}
          />
        </div>

        {/* Second column - Operator */}
        <div className="w-[140px]">
          <SelectField
            options={[
              {
                label: 'equals',
                options: [{value: 'equals', label: 'equals'}],
              },
            ]}
            value="equals"
            onSelectField={() => {}}
            isDisabled={true}
          />
        </div>

        {/* Third column - Value */}
        <div className="w-full flex-grow">
          <FormControl
            fullWidth
            sx={{borderColor: MOON_200, width: '100%', minWidth: 220}}>
            <Autocomplete
              PaperComponent={paperProps => <StyledPaper {...paperProps} />}
              sx={{
                width: '100%',
                '& .MuiOutlinedInput-root': {
                  height: '32px',
                  width: '100%',
                  '& fieldset': {
                    borderColor: MOON_200,
                  },
                  '&:hover fieldset': {
                    borderColor: `rgba(${TEAL_300}, 0.48)`,
                  },
                },
                '& .MuiOutlinedInput-input': {
                  height: '32px',
                  padding: '0 14px',
                  boxSizing: 'border-box',
                },
              }}
              size="small"
              limitTags={1}
              disabled={frozenOpFilter}
              value={selectedOpVersionOption}
              onChange={handleOperationChange}
              renderInput={renderParams => (
                <StyledTextField {...renderParams} fullWidth />
              )}
              getOptionLabel={option => opVersionOptions[option]?.title ?? ''}
              disableClearable={
                selectedOpVersionOption === ALL_TRACES_OR_CALLS_REF_KEY
              }
              groupBy={option => opVersionOptions[option]?.group}
              options={Object.keys(opVersionOptions)}
              popupIcon={<Icon name="chevron-down" />}
              clearIcon={<Icon name="close" />}
            />
          </FormControl>
        </div>
      </>
    );
  };

  const operationItem = filter.opVersionRefs?.map(ref => ({
    id: 'default-operation',
    field: 'op',
    operator: 'operation',
    value: ref,
  })) ?? [
    {
      id: 'default-operation',
      field: 'op',
      operator: 'operation',
      value: ALL_TRACES_OR_CALLS_REF_KEY,
    },
  ];

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
          {[...operationItem, ...completeItems].map(f => (
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
                  <Button size="small" variant="ghost" onClick={onSetSelected}>
                    {`Selected rows (${selectedCalls.length})`}
                  </Button>
                )}
              </div>
            </DraggableHandle>

            {/* Default filters section */}
            <div className="mb-8">
              <div className="mb-2 text-sm text-moon-500">Default filters</div>
              <div className="grid grid-cols-[190px_140px_1fr_30px] gap-4">
                {renderOperationFilter()}
              </div>
            </div>

            {/* Divider between default and custom filters */}
            <div className="my-6 border-t border-moon-200"></div>

            {/* AND text for custom filters */}
            <div className="mb-2 text-sm text-moon-500">AND</div>

            {/* Custom filters section */}
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
            </div>
            <div className="mt-8 flex items-center">
              <Button
                size="small"
                variant="ghost"
                icon="add-new"
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
