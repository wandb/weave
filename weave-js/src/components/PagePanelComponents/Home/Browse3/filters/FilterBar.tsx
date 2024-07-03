/**
 * This bar above a grid displays currently set filters for quick editing.
 */

import {Popover} from '@mui/material';
import React, {useRef, useState} from 'react';
import {field} from 'vega';

import {Button} from '../../../../Button';
import {
  DraggableGrow,
  PoppedBody,
  StyledTooltip,
  TooltipHint,
} from '../../../../DraggablePopups';
import {IconFilterAlt} from '../../../../Icon';
import {Tailwind} from '../../../../Tailwind';
import {FilterRow} from './FilterRow';
import {ColumnInfo, Filters} from './types';

type FilterBarProps = {
  filters: Filters;
  columnInfo: ColumnInfo;
  onSetFilters: (filters: Filters) => void;
};

export const FilterBar = ({
  filters,
  columnInfo,
  onSetFilters,
}: FilterBarProps) => {
  console.log('FilterBar');
  console.log({filters});
  const ref = useRef<HTMLDivElement>(null);
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const onClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(anchorEl ? null : ref.current);
  };

  const open = Boolean(anchorEl);
  const id = open ? 'simple-popper' : undefined;

  const [isMouseOver, setIsMouseOver] = useState(false);

  const onMouseEnter = () => setIsMouseOver(true);
  const onMouseLeave = () => setIsMouseOver(false);

  // TODO: Make not calls specific by using colGroupingModel
  // TODO: Make not use filterable, set all columns filterable false
  const cols = columnInfo.cols.filter(c => c.filterable ?? true);
  const grouped: Record<string, any[]> = {
    Other: [],
  };
  for (const group of columnInfo.colGroupingModel) {
    grouped[group.groupId] = [];
  }

  const options = [
    {
      label: 'inputs',
      options: [],
    },
    {
      label: 'output',
      options: [],
    },
    {
      label: 'Other',
      options: [],
    },
  ];
  for (const col of cols) {
    if (col.field.startsWith('inputs.')) {
      options[0].options.push({
        value: col.field,
        label: col.headerName.substring('inputs.'.length),
      });
    } else if (col.field.startsWith('output.')) {
      options[1].options.push({
        value: col.field,
        label: col.headerName.substring('output.'.length),
      });
    } else {
      options[2].options.push({
        value: col.field,
        label: col.headerName,
      });
    }
  }

  const onRemoveAll = () => {
    onSetFilters([]);
    setAnchorEl(null);
  };

  // for (const col of cols) {
  //   const group = col.groupId ?? 'Other';
  //   grouped[group].push(col);
  // }
  // console.log({columnInfo, grouped});

  // children
  // :
  // (2) [{…}, {…}]
  // groupId
  // :
  // "output"
  // headerName
  // :
  // "output"

  return (
    <Tailwind>
      <div
        ref={ref}
        className="flex cursor-pointer items-center gap-4 rounded px-8 py-4 outline outline-1 outline-moon-250 hover:border-teal-400 hover:outline hover:outline-2 hover:outline-teal-500/40 focus:outline-2"
        onMouseEnter={onMouseEnter}
        onMouseLeave={onMouseLeave}
        onClick={onClick}>
        <IconFilterAlt />
        <div>Filter</div>
        <div className="">
          {filters.map(f => {
            console.log('filter todo key');
            console.log({f});
            return <div></div>;
          })}
        </div>
      </div>
      <Popover
        id={id}
        open={open}
        anchorEl={anchorEl}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'center',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'center',
        }}
        slotProps={{
          paper: {
            sx: {
              overflow: 'visible',
            },
          },
        }}
        onClose={() => setAnchorEl(null)}
        TransitionComponent={DraggableGrow}>
        <Tailwind>
          <div className="p-12">
            <div className="handle flex items-center pb-12">
              <div className="flex-auto font-semibold">Filters</div>
              <div>
                <Button
                  size="small"
                  variant="ghost"
                  icon="close"
                  tooltip="Close filters"
                  onClick={e => {
                    e.stopPropagation();
                    setAnchorEl(null);
                  }}
                />
              </div>
            </div>
            <div className="">
              {filters.map(f => {
                console.log('filter todo key');
                console.log({f});
                return (
                  <FilterRow options={options} onSetFilters={onSetFilters} />
                );
              })}
              {filters.length === 0 && (
                <FilterRow options={options} onSetFilters={onSetFilters} />
              )}
            </div>
            <div className="mt-8 flex items-center">
              <Button size="small" variant="quiet" icon="add-new">
                Add filter
              </Button>
              <div className="flex-auto" />
              <Button
                size="small"
                variant="quiet"
                icon="delete"
                onClick={onRemoveAll}>
                Remove all
              </Button>
            </div>
          </div>
        </Tailwind>
      </Popover>
    </Tailwind>
  );
};
