import {Box, Popover} from '@mui/material';
import {
  GridApiPro,
  GridColumnVisibilityModel,
  GridFilterModel,
  GridSortModel,
} from '@mui/x-data-grid-pro';
import ModifiedDropdown from '@wandb/weave/common/components/elements/ModifiedDropdown';
import {toast} from '@wandb/weave/common/components/elements/Toast';
import {Button} from '@wandb/weave/components/Button';
import {Checkbox} from '@wandb/weave/components/Checkbox/Checkbox';
import * as DropdownMenu from '@wandb/weave/components/DropdownMenu';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {IconOnlyPill} from '@wandb/weave/components/Tag';
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

type SelectionState = {
  allChecked?: boolean;
  selectedChecked?: boolean;
  limitChecked?: boolean;
  limit?: string | null;
  exportOption: ContentTypeOption;
};

type ContentTypeOption = {
  value: ContentType | 'python' | 'curl';
  text: string;
  disabled?: boolean;
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
  const defaultOption = {value: ContentType.jsonl, text: 'jsonl'};
  const [selectionState, setSelectionState] = useState<SelectionState>({
    exportOption: defaultOption,
  });
  const [isExportTypeOpen, setIsExportTypeOpen] = useState(false);

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

  const options: ContentTypeOption[] = [
    {value: ContentType.jsonl, text: 'jsonl'},
    {value: ContentType.json, text: 'json'},
    {value: ContentType.tsv, text: 'tsv'},
    {value: ContentType.csv, text: 'csv'},
    // TODO: implement python and curl
    {value: 'python', text: 'python', disabled: true},
    {value: 'curl', text: 'curl', disabled: true},
  ];

  const onClickDownload = () => {
    if (selectionState.exportOption.value == null) {
      return;
    }
    if (['python', 'curl'].includes(selectionState.exportOption.value)) {
      console.error(
        'Export type not supported:',
        selectionState.exportOption.value
      );
      return;
    }
    if (selectionState.selectedChecked) {
      tableRef.current?.exportDataAsCsv({
        getRowsToExport: () => selectedCalls,
        fileName: `${callQueryParams.project}-export`,
      });
      setSelectionState(s => ({
        exportOption: defaultOption,
        limit: null,
        limitChecked: false,
        selectedChecked: false,
        allChecked: false,
      }));
      return;
    }
    const exportType = selectionState.exportOption.value as ContentType;
    const limit = selectionState.limitChecked
      ? Math.min(MAX_EXPORT, parseInt(selectionState.limit ?? '100'))
      : MAX_EXPORT;
    download(
      callQueryParams.entity,
      callQueryParams.project,
      exportType,
      lowLevelFilter,
      limit,
      0,
      sortBy,
      filterBy,
      Object.keys(cols).filter(v => cols[v] === true)
    ).then(() => {
      setSelectionState(s => ({
        ...s,
        exportOption: s.exportOption,
        limit: null,
        limitChecked: false,
        selectedChecked: false,
        allChecked: false,
      }));
    });
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
        onClose={() => setAnchorEl(null)}>
        <Tailwind>
          <div className="min-w-[460px] p-12">
            <div className="flex items-center pb-8">
              <div className="flex-auto text-xl font-semibold">Export</div>
              <div className="ml-16 text-moon-500">
                {maybePluralize(numVisible, 'column', 's')}
              </div>
            </div>
            <div className="flex items-center">
              <Checkbox
                checked={selectionState.allChecked ?? false}
                onCheckedChange={() =>
                  setSelectionState(s => ({
                    exportOption: s.exportOption,
                    allChecked: !s.allChecked,
                  }))
                }
              />
              <div className="ml-4 mr-24">
                all {maybePluralize(numTotalCalls, 'row', 's')}
              </div>
              <Checkbox
                checked={selectionState.selectedChecked ?? false}
                onCheckedChange={() =>
                  setSelectionState(s => ({
                    exportOption: s.exportOption,
                    selectedChecked: !s.selectedChecked,
                  }))
                }
              />
              <div className="ml-8 mr-6">first</div>
              <div className="w-[42px]">
                <TextField
                  type="number"
                  placeholder="100"
                  value={selectionState.limit ?? ''}
                  onChange={value =>
                    setSelectionState(s => ({
                      exportOption: s.exportOption,
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
                          exportOption: s.exportOption,
                          limitChecked: !s.limitChecked,
                        }))
                      }
                    />
                    <div className="ml-4">
                      selected (
                      {maybePluralize(selectedCalls.length, 'row', 's')})
                    </div>
                  </>
                )}
            </div>
            <div className="mt-12 flex items-center">
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
                      {selectionState?.exportOption.text}
                    </Button>
                  </div>
                </DropdownMenu.Trigger>
                <DropdownMenu.Content
                  onCloseAutoFocus={e => e.preventDefault()}>
                  {options.map(item => (
                    <DropdownMenu.Item
                      className="max-w-[70px]"
                      key={item.value}
                      onClick={() =>
                        setSelectionState(s => ({...s, exportOption: item}))
                      }
                      disabled={item.disabled}>
                      {item.text}
                    </DropdownMenu.Item>
                  ))}
                </DropdownMenu.Content>
              </DropdownMenu.Root>
            </div>
            <div className="mt-12 flex items-center text-moon-500">
              <IconOnlyPill color="moon" icon="warning" />
              <div className="ml-6">
                Exporting is currently in beta, and is subject to change.
              </div>
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
