/**
 * Button/popup for grid column visibility state.
 */

import {Popover} from '@mui/material';
import {GridColDef, GridColumnVisibilityModel} from '@mui/x-data-grid-pro';
import {Switch} from '@wandb/weave/components';
import classNames from 'classnames';
import React, {useCallback, useRef, useState} from 'react';

import {maybePluralize} from '../../../../../../core/util/string';
import {Button} from '../../../../../Button';
import {DraggableGrow, DraggableHandle} from '../../../../../DraggablePopups';
import {TextField} from '../../../../../Form/TextField';
import {Tailwind} from '../../../../../Tailwind';
import {ColumnInfo} from '../../types';
import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';

type ManageColumnsButtonProps = {
  columnInfo: ColumnInfo;
  columnVisibilityModel: GridColumnVisibilityModel;
  setColumnVisibilityModel: (model: GridColumnVisibilityModel) => void;
};

export const ManageColumnsButton = ({
  columnInfo,
  columnVisibilityModel,
  setColumnVisibilityModel,
}: ManageColumnsButtonProps) => {
  const [search, setSearch] = useState('');
  const lowerSearch = search.toLowerCase();
  const filteredCols = search
    ? columnInfo.cols.filter((col: GridColDef<TraceCallSchema>) => {
        const value = col.field;
        const label = col.headerName ?? value;
        return label.toLowerCase().includes(lowerSearch);
      })
    : columnInfo.cols;
  const numToggleable = filteredCols.filter(col => col.hideable ?? true).length;
  const buttonSuffix = search ? `(${numToggleable})` : 'all';

  const ref = useRef<HTMLDivElement>(null);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const onClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(anchorEl ? null : ref.current);
    setSearch('');
  };

  const open = Boolean(anchorEl);
  const id = open ? 'simple-popper' : undefined;
  const numHidden = Object.values(columnVisibilityModel).filter(
    v => v === false
  ).length;

  const toggleColumnShow = useCallback(
    (key: string) => {
      const on = columnVisibilityModel[key] ?? true;
      const newModel = {
        ...columnVisibilityModel,
        [key]: !on,
      };
      setColumnVisibilityModel(newModel);
    },
    [columnVisibilityModel, setColumnVisibilityModel]
  );
  const onHideAll = () => {
    const newModel = {...columnVisibilityModel};
    for (const col of filteredCols) {
      if (col.hideable ?? true) {
        newModel[col.field] = false;
      }
    }
    setColumnVisibilityModel(newModel);
  };
  const onShowAll = () => {
    const newModel = {...columnVisibilityModel};
    for (const col of filteredCols) {
      // If a column is not hideable, we also don't need to explicitly show it.
      if (col.hideable ?? true) {
        newModel[col.field] = true;
      }
    }
    setColumnVisibilityModel(newModel);
  };

  return (
    <>
      <span ref={ref}>
        <Button
          variant="ghost"
          icon="column"
          tooltip="Manage columns"
          onClick={onClick}
        />
      </span>
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
          <div className="min-w-[360px] p-12">
            <DraggableHandle>
              <div className="flex items-center pb-8">
                <div className="flex-auto text-xl font-semibold">
                  Manage columns
                </div>
                <div className="ml-16 text-moon-500">
                  {maybePluralize(numHidden, 'hidden column', 's')}
                </div>
              </div>
            </DraggableHandle>
            <div className="mb-8">
              <TextField
                placeholder="Filter columns"
                autoFocus
                value={search}
                onChange={setSearch}
              />
            </div>
            <div className="max-h-[300px] overflow-auto">
              {columnInfo.cols.map((col: GridColDef<TraceCallSchema>) => {
                const value = col.field;
                const idSwitch = `toggle-vis_${value}`;
                const checked = columnVisibilityModel[col.field] ?? true;
                const label = col.headerName ?? value;
                const disabled = !(col.hideable ?? true);
                if (
                  search &&
                  !label.toLowerCase().includes(search.toLowerCase())
                ) {
                  return null;
                }
                return (
                  <div key={value}>
                    <div
                      className={classNames(
                        'flex items-center py-2',
                        disabled ? 'opacity-40' : ''
                      )}>
                      <Switch.Root
                        id={idSwitch}
                        size="small"
                        checked={checked}
                        onCheckedChange={isOn => {
                          toggleColumnShow(col.field);
                        }}
                        disabled={disabled}>
                        <Switch.Thumb size="small" checked={checked} />
                      </Switch.Root>
                      <label
                        htmlFor={idSwitch}
                        className={classNames(
                          'ml-6',
                          disabled ? '' : 'cursor-pointer'
                        )}>
                        {label}
                      </label>
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="mt-8 flex items-center">
              <Button
                size="small"
                variant="quiet"
                icon="hide-hidden"
                disabled={numToggleable === 0}
                onClick={onHideAll}>
                {`Hide ${buttonSuffix}`}
              </Button>
              <div className="flex-auto" />
              <Button
                size="small"
                variant="quiet"
                icon="show-visible"
                disabled={numToggleable === 0}
                onClick={onShowAll}>
                {`Show ${buttonSuffix}`}
              </Button>
            </div>
          </div>
        </Tailwind>
      </Popover>
    </>
  );
};
