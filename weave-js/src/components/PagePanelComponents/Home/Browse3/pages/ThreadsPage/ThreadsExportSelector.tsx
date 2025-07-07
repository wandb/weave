import {Popover} from '@mui/material';
import {TrackedButton} from '@wandb/weave/components/Button/TrackedButton';
import {
  DraggableGrow,
  DraggableHandle,
} from '@wandb/weave/components/DraggablePopups';
import {Icon, IconName} from '@wandb/weave/components/Icon';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import classNames from 'classnames';
import React, {FC, useRef, useState} from 'react';

type ContentType = 'csv' | 'json' | 'jsonl';

export const ThreadsExportSelector = ({
  disabled,
  numTotalThreads,
}: {
  disabled: boolean;
  numTotalThreads: number;
}) => {
  // Popover management
  const ref = useRef<HTMLDivElement>(null);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const onClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(anchorEl ? null : ref.current);
  };
  const open = Boolean(anchorEl);
  const id = open ? 'threads-export-popover' : undefined;

  const onClickDownload = (contentType: ContentType) => {
    alert('The feature is yet to be implemented');
    setAnchorEl(null);
  };

  return (
    <>
      <span ref={ref}>
        <TrackedButton
          icon="export-share-upload"
          variant="ghost"
          onClick={onClick}
          disabled={disabled}
          trackedName="export-threads"
          tooltip={open ? undefined : 'Export threads data'}
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
        slotProps={{
          paper: {
            sx: {
              overflow: 'visible',
            },
          },
        }}
        onClose={() => {
          setAnchorEl(null);
        }}
        TransitionComponent={DraggableGrow}>
        <Tailwind>
          <div className="min-w-[400px] max-w-[500px] p-12">
            <DraggableHandle>
              <div className="flex items-center pb-8">
                <div className="flex-auto text-xl font-semibold">
                  Export Threads ({numTotalThreads.toLocaleString()})
                </div>
              </div>
            </DraggableHandle>
            <DownloadGrid onClickDownload={onClickDownload} />
          </div>
        </Tailwind>
      </Popover>
    </>
  );
};

const ClickableOutlinedCardWithIcon: FC<{
  iconName: IconName;
  disabled?: boolean;
  onClick: () => void;
}> = ({iconName, children, disabled, onClick}) => (
  <div
    className={classNames(
      'flex w-full cursor-pointer items-center rounded-md border border-moon-200 p-16 hover:bg-moon-100',
      disabled ? 'bg-moon-100 hover:cursor-default' : ''
    )}
    onClick={!disabled ? onClick : undefined}>
    <div className="mr-4 rounded-2xl bg-moon-200 p-4">
      <Icon size="xlarge" color="moon" name={iconName} />
    </div>
    <div className="ml-4 flex w-full items-center">{children}</div>
  </div>
);

const DownloadGrid: FC<{
  onClickDownload: (contentType: ContentType) => void;
}> = ({onClickDownload}) => {
  return (
    <>
      <div className="flex flex-col gap-8">
        <ClickableOutlinedCardWithIcon
          iconName="export-share-upload"
          onClick={() => onClickDownload('csv')}>
          Export to CSV
        </ClickableOutlinedCardWithIcon>

        <ClickableOutlinedCardWithIcon
          iconName="export-share-upload"
          onClick={() => onClickDownload('json')}>
          Export to JSON
        </ClickableOutlinedCardWithIcon>

        <ClickableOutlinedCardWithIcon
          iconName="export-share-upload"
          onClick={() => onClickDownload('jsonl')}>
          Export to JSONL
        </ClickableOutlinedCardWithIcon>
      </div>
    </>
  );
};
