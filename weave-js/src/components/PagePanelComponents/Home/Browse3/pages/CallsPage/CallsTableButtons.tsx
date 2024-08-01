import {Box, Popover} from '@mui/material';
import {
  GridApiPro,
  GridColumnVisibilityModel,
  GridFilterModel,
  GridSortModel,
} from '@mui/x-data-grid-pro';
import ModifiedDropdown from '@wandb/weave/common/components/elements/ModifiedDropdown';
import {toast} from '@wandb/weave/common/components/elements/Toast';
import {Switch} from '@wandb/weave/components';
import {Button} from '@wandb/weave/components/Button';
import * as DropdownMenu from '@wandb/weave/components/DropdownMenu';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {maybePluralize} from '@wandb/weave/core/util/string';
import React, {FC, useEffect, useRef, useState} from 'react';

import {useWFHooks} from '../wfReactInterface/context';
import {ContentType} from '../wfReactInterface/traceServerClientTypes';
import {WFHighLevelCallFilter} from './callsTableFilter';
import {useDownloadFilterSortby} from './callsTableQuery';

const MAX_EXPORT = 100_000;

export const ExportRunsTableButton = ({
  tableRef,
  selectedCalls,
  pageName,
  callQueryParams,
  rightmostButton = false,
}: {
  tableRef: React.MutableRefObject<GridApiPro>;
  selectedCalls: string[];
  callQueryParams: {
    entity: string;
    project: string;
    filter: WFHighLevelCallFilter;
    gridFilter: GridFilterModel;
    gridSort?: GridSortModel;
    columns?: string[];
  };
  pageName: string;
  rightmostButton?: boolean;
}) => {
  const {useCallsExport} = useWFHooks();
  const download = useCallsExport();
  const [clickedOption, setClickedOption] = useState<ContentType | null>(null);
  const fileName = `${pageName}-export`;

  const {sortBy, lowLevelFilter, filterBy} = useDownloadFilterSortby(
    callQueryParams.filter,
    callQueryParams.gridFilter,
    callQueryParams.gridSort
  );

  useEffect(() => {
    if (!clickedOption) {
      return;
    }
    download(
      callQueryParams.entity,
      callQueryParams.project,
      clickedOption,
      lowLevelFilter,
      MAX_EXPORT,
      0,
      sortBy,
      filterBy,
      callQueryParams.columns
    )
      .then(() => {
        ///
      })
      .catch(e => {
        toast(`Error downloading export: ${e}`, {type: 'error'});
      })
      .finally(() => {
        setClickedOption(null);
      });
  }, [
    callQueryParams.entity,
    callQueryParams.project,
    callQueryParams.columns,
    lowLevelFilter,
    sortBy,
    filterBy,
    clickedOption,
    download,
  ]);

  const selectedExport = () => {
    tableRef.current?.exportDataAsCsv({
      includeColumnGroupsHeaders: false,
      getRowsToExport: () => selectedCalls,
      fileName,
    });
  };

  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        alignItems: 'center',
      }}>
      <Tailwind>
        <ModifiedDropdown
          icon={
            <Button
              className={rightmostButton ? 'mr-16' : 'mr-4'}
              icon="export-share-upload"
              variant="ghost"
            />
          }
          direction="left"
          search={false}
          options={[
            {
              value: 'export-jsonl',
              text: 'Export to jsonl',
              onClick: () => setClickedOption(ContentType.jsonl),
            },
            {
              value: 'export-json',
              text: 'Export to json',
              onClick: () => setClickedOption(ContentType.json),
            },
            {
              value: 'export-tsv',
              text: 'Export to tsv',
              onClick: () => setClickedOption(ContentType.tsv),
            },
            {
              value: 'export-csv',
              text: 'Export to csv',
              onClick: () => setClickedOption(ContentType.csv),
            },
            {
              value: 'export selected',
              text: `Export selected calls (${selectedCalls.length})`,
              onClick:
                selectedCalls.length > 0 ? () => selectedExport() : undefined,
              disabled: selectedCalls.length === 0,
            },
          ]}
        />
      </Tailwind>
    </Box>
  );
};

export const ExportSelector = ({
  columnVisibilityModel,
  disabled,
  callQueryParams,
  rightmostButton = false,
}: {
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
  const [search, setSearch] = useState('');
  const [allVisibleColumns, setAllVisibleColumns] = useState(true);
  const [isExportTypeOpen, setIsExportTypeOpen] = useState(false);

  const ref = useRef<HTMLDivElement>(null);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const onClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(anchorEl ? null : ref.current);
    setSearch('');
  };

  const open = Boolean(anchorEl);
  const id = open ? 'simple-popper' : undefined;
  const cols = columnVisibilityModel ?? {};
  const numVisible = Object.values(cols).filter(v => v === true).length;

  const {useCallsExport} = useWFHooks();
  const download = useCallsExport();
  const [clickedOption, setClickedOption] = useState<ContentType | null>(null);

  const {sortBy, lowLevelFilter, filterBy} = useDownloadFilterSortby(
    callQueryParams.filter,
    callQueryParams.gridFilter,
    callQueryParams.gridSort
  );

  const options = [
    {
      value: 'export-jsonl',
      text: 'jsonl',
      onClick: () => setClickedOption(ContentType.jsonl),
    },
    {
      value: 'export-json',
      text: 'json',
      onClick: () => setClickedOption(ContentType.json),
    },
    {
      value: 'export-tsv',
      text: 'tsv',
      onClick: () => setClickedOption(ContentType.tsv),
    },
    {
      value: 'export-csv',
      text: 'csv',
      onClick: () => setClickedOption(ContentType.csv),
    },
    {
      value: 'export-python',
      text: 'python',
      onClick: () => {
        console.log('python');
        setClickedOption('python');
      },
      disabled: true,
    },
  ];

  const onClickDownload = () => {
    if (clickedOption === null) {
      return;
    }
    
    download(
      callQueryParams.entity,
      callQueryParams.project,
      clickedOption,
      lowLevelFilter,
      MAX_EXPORT,
      0,
      sortBy,
      filterBy,
      Object.keys(cols).filter(v => cols[v] === true)
    );
  };

  const STYLE_MENU_CONTENT = {zIndex: 2};

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
        onClose={() => setAnchorEl(null)}>
        <Tailwind>
          <div className="min-w-[360px] p-12">
            <div className="flex items-center pb-8">
              <div className="flex-auto text-xl font-semibold">Export</div>
              <div className="ml-16 text-moon-500">
                {maybePluralize(numVisible, 'visible column', 's')}
              </div>
            </div>
            <div className="flex justify-start">
              <div className="mr-8">Export all visible columns</div>
              <Switch.Root
                id="switch-visible"
                size="small"
                className="mt-4"
                checked={allVisibleColumns}
                onCheckedChange={isOn => {
                  setAllVisibleColumns(isOn);
                }}>
                <Switch.Thumb size="small" checked={allVisibleColumns} />
              </Switch.Root>
            </div>
            {!allVisibleColumns && (
              <div className="mb-8">
                <TextField
                  placeholder="Filter columns"
                  autoFocus
                  value={search}
                  onChange={setSearch}
                />
              </div>
            )}

            <div className="mt-8 flex items-center">
              <Button size="small" variant="primary" onClick={onClickDownload}>
                Export
              </Button>
              <span className="ml-4 font-semibold">as</span>
              <DropdownMenu.Root
                open={isExportTypeOpen}
                onOpenChange={setIsExportTypeOpen}>
                <DropdownMenu.Trigger>
                  <div className="ml-4 flex items-center">
                    <Button size="small" variant="secondary">
                      {clickedOption ?? 'jsonl'}
                    </Button>
                  </div>
                </DropdownMenu.Trigger>
                <DropdownMenu.Content
                  // align="end"
                  style={STYLE_MENU_CONTENT}
                  onCloseAutoFocus={e => e.preventDefault()}>
                  {options.map(item => (
                    <DropdownMenu.Item
                      className="max-w-[70px]"
                      key={item.value}
                      onClick={item.onClick}
                      disabled={item.disabled}>
                      {item.text}
                    </DropdownMenu.Item>
                  ))}
                </DropdownMenu.Content>
              </DropdownMenu.Root>
            </div>
          </div>
        </Tailwind>
      </Popover>
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
