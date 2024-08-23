import {Box, Popover} from '@mui/material';
import {GridFilterModel, GridSortModel} from '@mui/x-data-grid-pro';
import {useOrgName} from '@wandb/weave/common/hooks/useOrganization';
import {useViewerUserInfo2} from '@wandb/weave/common/hooks/useViewerUserInfo';
import {Radio} from '@wandb/weave/components';
import {Button} from '@wandb/weave/components/Button';
import {
  DraggableGrow,
  DraggableHandle,
} from '@wandb/weave/components/DraggablePopups';
import {Icon, IconName} from '@wandb/weave/components/Icon';
import {Loading} from '@wandb/weave/components/Loading';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import classNames from 'classnames';
import React, {Dispatch, FC, SetStateAction, useRef, useState} from 'react';

import * as userEvents from '../../../../../../integrations/analytics/userEvents';
import {useWFHooks} from '../wfReactInterface/context';
import {
  ContentType,
  fileExtensions,
} from '../wfReactInterface/traceServerClientTypes';
import {WFHighLevelCallFilter} from './callsTableFilter';
import {useFilterSortby} from './callsTableQuery';

const MAX_EXPORT = 10_000;

type SelectionState = 'all' | 'selected' | 'limit';

export const ExportSelector = ({
  selectedCalls,
  numTotalCalls,
  visibleColumns,
  disabled,
  callQueryParams,
}: {
  selectedCalls: string[];
  numTotalCalls: number;
  visibleColumns: string[];
  callQueryParams: {
    entity: string;
    project: string;
    filter: WFHighLevelCallFilter;
    gridFilter: GridFilterModel;
    gridSort?: GridSortModel;
  };
  disabled: boolean;
}) => {
  const [selectionState, setSelectionState] = useState<SelectionState>('all');
  const [downloadLoading, setDownloadLoading] = useState<ContentType | null>(
    null
  );
  const {loading: viewerLoading, userInfo} = useViewerUserInfo2();
  const userInfoLoaded = !viewerLoading ? userInfo : null;
  const {loading: orgNameLoading, orgName} = useOrgName({
    entityName: userInfoLoaded?.username ?? '',
    skip: viewerLoading,
  });

  // Popover management
  const ref = useRef<HTMLDivElement>(null);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const onClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(anchorEl ? null : ref.current);
  };
  const open = Boolean(anchorEl);
  const id = open ? 'simple-popper' : undefined;

  // Call download query
  const {useCallsExport} = useWFHooks();
  const download = useCallsExport();
  const {sortBy, lowLevelFilter, filterBy} = useFilterSortby(
    callQueryParams.filter,
    callQueryParams.gridFilter,
    callQueryParams.gridSort
  );

  const onClickDownload = (contentType: ContentType) => {
    if (downloadLoading) {
      return;
    }
    setDownloadLoading(contentType);
    lowLevelFilter.callIds =
      selectionState === 'selected' ? selectedCalls : undefined;
    // TODO(gst): allow specifying offset
    const offset = 0;
    const limit = MAX_EXPORT;
    // TODO(gst): add support for JSONL and JSON column selection
    const columns = [ContentType.csv, ContentType.tsv].includes(contentType)
      ? visibleColumns
      : undefined;
    const startTime = Date.now();
    download(
      callQueryParams.entity,
      callQueryParams.project,
      contentType,
      lowLevelFilter,
      limit,
      offset,
      sortBy,
      filterBy,
      columns
    ).then(blob => {
      const fileExtension = fileExtensions[contentType];
      const date = new Date().toISOString().split('T')[0];
      const fileName = `weave_export_${callQueryParams.project}_${date}.${fileExtension}`;
      initiateDownloadFromBlob(blob, fileName);
      setAnchorEl(null);
      setDownloadLoading(null);

      userEvents.exportClicked({
        dataSize: blob.size,
        numColumns: columns?.length ?? null,
        numRows: numTotalCalls,
        numExpandedColumns: 0,
        maxDepth: 0,
        type: contentType,
        latency: Date.now() - startTime,
        userId: userInfoLoaded?.id ?? '',
        organizationName: orgName,
        username: userInfoLoaded?.username ?? '',
      });
    });
    setSelectionState('all');
  };

  return (
    <>
      <span ref={ref}>
        <Button
          icon="export-share-upload"
          variant="ghost"
          onClick={onClick}
          disabled={disabled}
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
          setSelectionState('all');
        }}
        TransitionComponent={DraggableGrow}>
        <Tailwind>
          <div className="min-w-[460px] p-12">
            <DraggableHandle>
              <div className="flex items-center pb-8">
                {selectedCalls.length === 0 ? (
                  <div className="flex-auto text-xl font-semibold">
                    Export (
                    {Math.min(numTotalCalls, MAX_EXPORT).toLocaleString()})
                  </div>
                ) : (
                  <div className="flex-auto text-xl font-semibold">Export</div>
                )}
              </div>
              {selectedCalls.length > 0 && (
                <SelectionCheckboxes
                  numSelectedCalls={selectedCalls.length}
                  numTotalCalls={numTotalCalls}
                  selectionState={selectionState}
                  setSelectionState={setSelectionState}
                />
              )}
              {!viewerLoading && !orgNameLoading && (
                <DownloadGrid
                  onClickDownload={onClickDownload}
                  downloadLoading={downloadLoading}
                />
              )}
            </DraggableHandle>
          </div>
        </Tailwind>
      </Popover>
    </>
  );
};

const SelectionCheckboxes: FC<{
  numSelectedCalls: number;
  numTotalCalls: number;
  selectionState: SelectionState;
  setSelectionState: Dispatch<SetStateAction<SelectionState>>;
}> = ({numSelectedCalls, numTotalCalls, selectionState, setSelectionState}) => {
  return (
    <>
      <div className="ml-2" />
      <Radio.Root
        className="flex items-center"
        aria-label="All checked"
        name="all checked"
        onValueChange={(value: SelectionState) => setSelectionState(value)}
        value={selectionState}>
        <Radio.Item id="all-rows" value="all">
          <Radio.Indicator />
        </Radio.Item>
        <label className="flex items-center">
          <span onClick={() => setSelectionState('all')} className="ml-6 mr-12">
            All rows ({numTotalCalls})
          </span>
        </label>
        <label className="flex items-center">
          <Radio.Item id="selected-rows" value="selected">
            <Radio.Indicator />
          </Radio.Item>
          <span
            className="ml-6 mr-12"
            onClick={() => setSelectionState('selected')}>
            Selected rows ({numSelectedCalls})
          </span>
        </label>
      </Radio.Root>
    </>
  );
};

const ClickableOutlinedCardWithIcon: FC<{
  iconName: IconName;
  downloadLoading: boolean;
  disabled: boolean;
  onClick: () => void;
}> = ({iconName, children, downloadLoading, disabled, onClick}) => (
  <div
    className={classNames(
      'flex w-full cursor-pointer items-center rounded-md border border-moon-200 p-16 hover:bg-moon-100',
      disabled ? 'bg-moon-100 hover:cursor-default' : ''
    )}
    onClick={!disabled ? onClick : undefined}>
    {downloadLoading ? (
      <Loading size={28} className="mr-4" />
    ) : (
      <div className="mr-4 rounded-2xl bg-moon-200 p-4">
        <Icon size="xlarge" color="moon" name={iconName} />
      </div>
    )}
    <div className="ml-4">{children}</div>
  </div>
);

const DownloadGrid: FC<{
  downloadLoading: ContentType | null;
  onClickDownload: (contentType: ContentType) => void;
}> = ({downloadLoading, onClickDownload}) => {
  return (
    <>
      <div className="mt-12 flex items-center">
        <ClickableOutlinedCardWithIcon
          iconName="export-share-upload"
          downloadLoading={downloadLoading === ContentType.csv}
          disabled={downloadLoading !== null}
          onClick={() => onClickDownload(ContentType.csv)}>
          Export to CSV
        </ClickableOutlinedCardWithIcon>
        <div className="ml-8" />
        <ClickableOutlinedCardWithIcon
          iconName="export-share-upload"
          downloadLoading={downloadLoading === ContentType.tsv}
          disabled={downloadLoading !== null}
          onClick={() => onClickDownload(ContentType.tsv)}>
          Export to TSV
        </ClickableOutlinedCardWithIcon>
      </div>
      <div className="mt-8 flex items-center">
        <ClickableOutlinedCardWithIcon
          iconName="export-share-upload"
          downloadLoading={downloadLoading === ContentType.jsonl}
          disabled={downloadLoading !== null}
          onClick={() => onClickDownload(ContentType.jsonl)}>
          Export to JSONL
        </ClickableOutlinedCardWithIcon>
        <div className="ml-8" />
        <ClickableOutlinedCardWithIcon
          iconName="export-share-upload"
          downloadLoading={downloadLoading === ContentType.json}
          disabled={downloadLoading !== null}
          onClick={() => onClickDownload(ContentType.json)}>
          Export to JSON
        </ClickableOutlinedCardWithIcon>
      </div>
    </>
  );
};

export const CompareEvaluationsTableButton: FC<{
  onClick: () => void;
  disabled?: boolean;
  tooltipText?: string;
}> = ({onClick, disabled, tooltipText}) => (
  <Box
    sx={{
      height: '100%',
      display: 'flex',
      alignItems: 'center',
    }}>
    <Button
      className="mx-4"
      size="medium"
      variant="primary"
      disabled={disabled}
      onClick={onClick}
      icon="chart-scatterplot"
      tooltip={tooltipText}>
      Compare
    </Button>
  </Box>
);

export const BulkDeleteButton: FC<{
  disabled?: boolean;
  onClick: () => void;
}> = ({disabled, onClick}) => {
  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        alignItems: 'center',
      }}>
      <Button
        variant="ghost"
        size="medium"
        disabled={disabled}
        onClick={onClick}
        tooltip="Select rows with the checkbox to delete"
        icon="delete"
      />
    </Box>
  );
};

function initiateDownloadFromBlob(blob: Blob, fileName: string) {
  const downloadUrl = URL.createObjectURL(blob);
  // Create a download link and click it
  const anchor = document.createElement('a');
  anchor.href = downloadUrl;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(downloadUrl);
}
