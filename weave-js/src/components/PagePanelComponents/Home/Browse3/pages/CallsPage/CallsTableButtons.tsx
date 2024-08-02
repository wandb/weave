import {Box, Popover} from '@mui/material';
import {
  GridApiPro,
  GridColumnVisibilityModel,
  GridFilterModel,
  GridSortModel,
} from '@mui/x-data-grid-pro';
import {Button} from '@wandb/weave/components/Button';
import {Checkbox} from '@wandb/weave/components/Checkbox/Checkbox';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {Icon, IconName} from '@wandb/weave/components/Icon';
import {IconOnlyPill} from '@wandb/weave/components/Tag';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {maybePluralize} from '@wandb/weave/core/util/string';
import React, {FC, useRef, useState} from 'react';

import {useWFHooks} from '../wfReactInterface/context';
import {ContentType} from '../wfReactInterface/traceServerClientTypes';
import {WFHighLevelCallFilter} from './callsTableFilter';
import {useDownloadFilterSortby} from './callsTableQuery';

const MAX_EXPORT = 100_000;

type SelectionState = {
  allChecked?: boolean;
  selectedChecked?: boolean;
  limitChecked?: boolean;
  limit?: string | null;
};

export const ExportSelector = ({
  selectedCalls,
  tableRef,
  numTotalCalls,
  columnVisibilityModel,
  disabled,
  callQueryParams,
  rightmostButton = false,
}: {
  selectedCalls: string[];
  tableRef: React.MutableRefObject<GridApiPro>;
  numTotalCalls: number;
  columnVisibilityModel: GridColumnVisibilityModel | undefined;
  callQueryParams: {
    entity: string;
    project: string;
    filter: WFHighLevelCallFilter;
    gridFilter: GridFilterModel;
    gridSort?: GridSortModel;
  };
  disabled: boolean;
  rightmostButton?: boolean;
}) => {
  const [selectionState, setSelectionState] = useState<SelectionState>({
    allChecked: true,
  });

  const ref = useRef<HTMLDivElement>(null);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const onClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(anchorEl ? null : ref.current);
  };

  const open = Boolean(anchorEl);
  const id = open ? 'simple-popper' : undefined;
  const cols = columnVisibilityModel ?? {};
  const numVisible = Object.values(cols).filter(v => v === true).length;

  const {useCallsExport} = useWFHooks();
  const download = useCallsExport();

  const {sortBy, lowLevelFilter, filterBy} = useDownloadFilterSortby(
    callQueryParams.filter,
    callQueryParams.gridFilter,
    callQueryParams.gridSort
  );

  const onClickDownload = (contentType: ContentType) => {
    if (selectionState.selectedChecked) {
      // download from datagrid table
      tableRef.current?.exportDataAsCsv({
        getRowsToExport: () => selectedCalls,
        fileName: `${callQueryParams.project}-export`,
      });
      setAnchorEl(null);
    } else {
      // download from server
      const limit = selectionState.limitChecked
        ? Math.min(MAX_EXPORT, parseInt(selectionState.limit ?? '100', 10))
        : MAX_EXPORT;
      download(
        callQueryParams.entity,
        callQueryParams.project,
        contentType,
        lowLevelFilter,
        limit,
        0,
        sortBy,
        filterBy,
        Object.keys(cols).filter(v => cols[v] === true)
      ).then(() => {
        setAnchorEl(null);
      });
    }
    setSelectionState({allChecked: true});
  };

  return (
    <>
      <span ref={ref}>
        <Button
          className={rightmostButton ? 'mr-16' : 'mr-4'}
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
          setSelectionState({allChecked: true});
        }}>
        <Tailwind>
          <div className="min-w-[460px] p-12">
            <div className="flex items-center pb-8">
              <div className="flex-auto text-xl font-semibold">Export</div>
              <div className="ml-16 text-moon-500">
                {maybePluralize(numVisible, 'column', 's')}
              </div>
            </div>
            <div className="flex items-center">
              <div className="ml-2" />
              <Checkbox
                checked={selectionState.allChecked ?? false}
                onCheckedChange={() =>
                  setSelectionState(s => ({allChecked: !s.allChecked}))
                }
              />
              <div className="ml-6 mr-24">all rows ({numTotalCalls})</div>
              <Checkbox
                checked={selectionState.selectedChecked ?? false}
                onCheckedChange={() =>
                  setSelectionState(s => ({
                    selectedChecked: !s.selectedChecked,
                  }))
                }
              />
              <div className="ml-8 mr-6">first</div>
              <div className="w-auto min-w-[50px]">
                <TextField
                  type="number"
                  placeholder="1000"
                  value={selectionState.limit ?? ''}
                  onChange={value =>
                    setSelectionState(s => ({
                      selectedChecked: s.selectedChecked,
                      limit: value,
                    }))
                  }
                />
              </div>
              <div className="ml-4 mr-16">rows</div>
              {selectedCalls.length > 0 &&
                selectedCalls.length !== numTotalCalls && (
                  <>
                    <Checkbox
                      checked={selectionState.limitChecked ?? false}
                      onCheckedChange={() =>
                        setSelectionState(s => ({
                          limitChecked: !s.limitChecked,
                        }))
                      }
                    />
                    <div className="ml-4">
                      selected rows ({selectedCalls.length})
                    </div>
                  </>
                )}
            </div>
            <div className="mt-12 flex items-center">
              <ClickableOutlinedCardWithIcon
                iconName="export-share-upload"
                onClick={() => onClickDownload(ContentType.csv)}>
                Export to CSV
              </ClickableOutlinedCardWithIcon>
              <div className="ml-8" />
              <ClickableOutlinedCardWithIcon
                iconName="export-share-upload"
                onClick={() => onClickDownload(ContentType.tsv)}>
                Export to TSV
              </ClickableOutlinedCardWithIcon>
            </div>
            <div className="mt-8 flex items-center">
              <ClickableOutlinedCardWithIcon
                iconName="export-share-upload"
                onClick={() => onClickDownload(ContentType.jsonl)}>
                Export to JSONL
              </ClickableOutlinedCardWithIcon>
              <div className="ml-8" />
              <ClickableOutlinedCardWithIcon
                iconName="export-share-upload"
                onClick={() => onClickDownload(ContentType.json)}>
                Export to JSON
              </ClickableOutlinedCardWithIcon>
            </div>
            <div className="mt-12 flex items-center text-moon-500">
              <IconOnlyPill color="moon" icon="warning" />
              <div className="ml-6">
                This export experience is in beta and subject to change.
              </div>
            </div>
          </div>
        </Tailwind>
      </Popover>
    </>
  );
};

const ClickableOutlinedCardWithIcon: FC<{
  iconName: IconName;
  onClick: () => void;
}> = ({iconName, children, onClick}) => (
  <div
    className="flex w-full cursor-pointer items-center rounded-md border border-moon-200 p-16"
    onClick={onClick}>
    <div className="mr-4 rounded-2xl bg-moon-200 p-4">
      <Icon size="xlarge" color="moon" name={iconName} />
    </div>
    <div className="ml-4">{children}</div>
  </div>
);

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
        className="ml-4 mr-16"
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
