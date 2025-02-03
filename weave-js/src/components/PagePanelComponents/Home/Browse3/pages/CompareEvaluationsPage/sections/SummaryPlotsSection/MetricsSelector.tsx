import {Popover} from '@mui/material';
import {Switch} from '@wandb/weave/components';
import {Button} from '@wandb/weave/components/Button';
import {
  DraggableGrow,
  DraggableHandle,
} from '@wandb/weave/components/DraggablePopups';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {maybePluralize} from '@wandb/weave/core/util/string';
import classNames from 'classnames';
import React, {useRef, useState} from 'react';

export const MetricsSelector: React.FC<{
  setSelectedMetrics: (newModel: Record<string, boolean>) => void;
  selectedMetrics: Record<string, boolean> | undefined;
  allMetrics: string[];
}> = ({setSelectedMetrics, selectedMetrics, allMetrics}) => {
  const [search, setSearch] = useState('');

  const ref = useRef<HTMLDivElement>(null);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const onClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(anchorEl ? null : ref.current);
    setSearch('');
  };
  const open = Boolean(anchorEl);
  const id = open ? 'simple-popper' : undefined;

  const filteredCols = search
    ? allMetrics.filter(col => col.toLowerCase().includes(search.toLowerCase()))
    : allMetrics;

  const shownMetrics = Object.values(selectedMetrics ?? {}).filter(Boolean);

  const numHidden = allMetrics.length - shownMetrics.length;
  const buttonSuffix = search ? `(${filteredCols.length})` : 'all';

  return (
    <>
      <span ref={ref}>
        <Button
          variant="ghost"
          icon="column"
          tooltip="Manage metrics"
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
                  Manage metrics
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
              {Array.from(allMetrics).map((metric: string) => {
                const value = metric;
                const idSwitch = `toggle-vis_${value}`;
                const checked = selectedMetrics?.[metric] ?? false;
                const label = metric;
                const disabled = false;
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
                          setSelectedMetrics(
                            isOn
                              ? {...selectedMetrics, [metric]: true}
                              : {...selectedMetrics, [metric]: false}
                          );
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
                variant="ghost"
                icon="hide-hidden"
                disabled={filteredCols.length === 0}
                onClick={() => {
                  const newModel = {...selectedMetrics};
                  for (const metric of filteredCols) {
                    newModel[metric] = false;
                  }
                  setSelectedMetrics(newModel);
                }}>
                {`Hide ${buttonSuffix}`}
              </Button>
              <div className="flex-auto" />
              <Button
                size="small"
                variant="ghost"
                icon="show-visible"
                disabled={filteredCols.length === 0}
                onClick={() => {
                  const newModel = {...selectedMetrics};
                  for (const metric of filteredCols) {
                    newModel[metric] = true;
                  }
                  setSelectedMetrics(newModel);
                }}>
                {`Show ${buttonSuffix}`}
              </Button>
            </div>
          </div>
        </Tailwind>
      </Popover>
    </>
  );
};
