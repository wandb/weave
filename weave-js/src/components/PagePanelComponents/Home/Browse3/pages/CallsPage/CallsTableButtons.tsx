import {Box, Popover} from '@mui/material';
import {
  GridFilterModel,
  gridPageCountSelector,
  gridPageSelector,
  gridPageSizeSelector,
  gridRowCountSelector,
  GridSortModel,
  useGridApiContext,
  useGridSelector,
} from '@mui/x-data-grid-pro';
import {MOON_500} from '@wandb/weave/common/css/color.styles';
import {useOrgName} from '@wandb/weave/common/hooks/useOrganization';
import {useViewerUserInfo2} from '@wandb/weave/common/hooks/useViewerUserInfo';
import {Radio, Switch} from '@wandb/weave/components';
import {Button} from '@wandb/weave/components/Button';
import {CodeEditor} from '@wandb/weave/components/CodeEditor';
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
import {Select} from '../../../../../Form/Select';
import {useWFHooks} from '../wfReactInterface/context';
import {Query} from '../wfReactInterface/traceServerClientInterface/query';
import {
  ContentType,
  fileExtensions,
} from '../wfReactInterface/traceServerClientTypes';
import {CallFilter} from '../wfReactInterface/wfDataModelHooksInterface';
import {WFHighLevelCallFilter} from './callsTableFilter';
import {useFilterSortby} from './callsTableQuery';

const MAX_EXPORT = 10_000;

type SelectionState = 'all' | 'selected' | 'limit';

const LabelWithSwitch: FC<{
  id: string;
  label: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
}> = ({id, label, checked, onCheckedChange, disabled}) => (
  <div
    className={classNames(
      'flex items-center py-2',
      disabled ? 'opacity-40' : ''
    )}>
    <Switch.Root
      id={id}
      size="small"
      checked={checked}
      onCheckedChange={onCheckedChange}
      disabled={disabled}>
      <Switch.Thumb size="small" checked={checked} />
    </Switch.Root>
    <label
      htmlFor={id}
      className={classNames('ml-6', disabled ? '' : 'cursor-pointer')}>
      {label}
    </label>
  </div>
);

export const ExportSelector = ({
  selectedCalls,
  numTotalCalls,
  visibleColumns,
  refColumnsToExpand,
  disabled,
  callQueryParams,
  defaultToSelected,
}: {
  selectedCalls: string[];
  numTotalCalls: number;
  visibleColumns: string[];
  refColumnsToExpand: string[];
  callQueryParams: {
    entity: string;
    project: string;
    filter: WFHighLevelCallFilter;
    gridFilter: GridFilterModel;
    gridSort?: GridSortModel;
  };
  disabled: boolean;
  defaultToSelected?: boolean;
}) => {
  const [selectionState, setSelectionState] = useState<SelectionState>(
    defaultToSelected && selectedCalls.length > 0 ? 'selected' : 'all'
  );
  const [downloadLoading, setDownloadLoading] = useState<ContentType | null>(
    null
  );
  const {loading: viewerLoading, userInfo} = useViewerUserInfo2();
  const userInfoLoaded = !viewerLoading ? userInfo : null;
  const {orgName} = useOrgName({
    entityName: userInfoLoaded?.username ?? '',
    skip: viewerLoading,
  });
  const [includeFeedback, setIncludeFeedback] = useState(false);
  const [includeCosts, setIncludeCosts] = useState(false);

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

    // Explicitly add feedback column for CSV/TSV exports
    if (
      [ContentType.csv, ContentType.tsv].includes(contentType) &&
      includeFeedback
    ) {
      visibleColumns.push('summary.weave.feedback');
    }

    const leafColumns = [ContentType.csv, ContentType.tsv].includes(contentType)
      ? makeLeafColumns(visibleColumns)
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
      leafColumns,
      refColumnsToExpand,
      includeFeedback,
      includeCosts
    ).then(blob => {
      const fileExtension = fileExtensions[contentType];
      const date = new Date().toISOString().split('T')[0];
      const fileName = `weave_export_${callQueryParams.project}_${date}.${fileExtension}`;
      initiateDownloadFromBlob(blob, fileName);
      setAnchorEl(null);
      setDownloadLoading(null);

      userEvents.exportClicked({
        dataSize: blob.size,
        numColumns: visibleColumns?.length ?? null,
        numRows: numTotalCalls,
        numExpandedColumns: refColumnsToExpand.length,
        // the most nested refColumn to expand
        maxDepth: refColumnsToExpand.reduce(
          (max, col) => Math.max(max, col.split('.').length),
          0
        ),
        type: contentType,
        latency: Date.now() - startTime,
        userId: userInfoLoaded?.id ?? '',
        organizationName: orgName,
        username: userInfoLoaded?.username ?? '',
      });
    });
    setSelectionState('all');
  };

  const pythonText = makeCodeText(
    callQueryParams.project,
    selectionState === 'selected' ? selectedCalls : undefined,
    lowLevelFilter,
    filterBy,
    sortBy,
    includeFeedback,
    includeCosts
  );
  const curlText = makeCurlText(
    callQueryParams.entity,
    callQueryParams.project,
    selectionState === 'selected' ? selectedCalls : undefined,
    lowLevelFilter,
    filterBy,
    refColumnsToExpand,
    sortBy,
    includeFeedback,
    includeCosts
  );

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
          <div className="min-w-[560px] max-w-[660px] p-12">
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
            </DraggableHandle>
            <div className="flex items-center gap-12">
              <LabelWithSwitch
                id="include-feedback"
                label="Include feedback"
                checked={includeFeedback}
                onCheckedChange={setIncludeFeedback}
                disabled={disabled}
              />
              <LabelWithSwitch
                id="include-costs"
                label="Include costs"
                checked={includeCosts}
                onCheckedChange={setIncludeCosts}
                disabled={disabled}
              />
            </div>
            <DownloadGrid
              pythonText={pythonText}
              curlText={curlText}
              downloadLoading={downloadLoading}
              onClickDownload={onClickDownload}
            />
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
  downloadLoading?: boolean;
  disabled?: boolean;
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
        <Icon
          // manage python logo night mode
          className={classNames({'night-aware': iconName.includes('logo')})}
          size="xlarge"
          color="moon"
          name={iconName}
        />
      </div>
    )}
    <div className="ml-4 flex w-full items-center">{children}</div>
  </div>
);

const DownloadGrid: FC<{
  pythonText: string;
  curlText: string;
  downloadLoading: ContentType | null;
  onClickDownload: (contentType: ContentType) => void;
}> = ({pythonText, curlText, downloadLoading, onClickDownload}) => {
  const [codeMode, setCodeMode] = useState<'python' | 'curl' | null>(null);
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
      <div className="mt-8 flex items-center">
        <ClickableOutlinedCardWithIcon
          iconName="python-logo"
          onClick={() => setCodeMode('python')}>
          <span className="w-full">Use Python</span>
        </ClickableOutlinedCardWithIcon>
        <div className="ml-8" />
        <ClickableOutlinedCardWithIcon
          iconName="code-alt"
          onClick={() => setCodeMode('curl')}>
          <span className="w-full">Use CURL</span>
        </ClickableOutlinedCardWithIcon>
      </div>
      {codeMode && (
        <div className="mt-8 flex max-w-full items-center">
          <CodeEditor
            value={codeMode === 'python' ? pythonText : curlText}
            language={codeMode === 'python' ? 'python' : 'shell'}
            handleMouseWheel={true}
            alwaysConsumeMouseWheel={false}
          />
        </div>
      )}
    </>
  );
};

export const CompareEvaluationsTableButton: FC<{
  onClick: () => void;
  disabled?: boolean;
  tooltipText?: string;
  selectedCount: number;
}> = ({onClick, disabled, tooltipText, selectedCount}) => {
  const defaultTooltip =
    selectedCount === 1 ? 'Select more than one eval to compare' : undefined;

  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        alignItems: 'center',
      }}>
      <Button
        size="medium"
        variant="ghost"
        disabled={disabled || selectedCount === 1}
        onClick={onClick}
        icon="chart-scatterplot"
        tooltip={tooltipText ?? defaultTooltip}>
        Compare
      </Button>
    </Box>
  );
};

export const CompareTracesTableButton: FC<{
  onClick: () => void;
  disabled?: boolean;
  tooltipText?: string;
  selectedCount: number;
}> = ({onClick, disabled, tooltipText, selectedCount}) => {
  const defaultTooltip =
    selectedCount === 1 ? 'Select more than one trace to compare' : undefined;

  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        alignItems: 'center',
      }}>
      <Button
        size="medium"
        variant="ghost"
        disabled={disabled || selectedCount === 1}
        onClick={onClick}
        icon="chart-scatterplot"
        tooltip={tooltipText ?? defaultTooltip}>
        Compare
      </Button>
    </Box>
  );
};

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
        icon="delete"></Button>
    </Box>
  );
};

export const BulkAddToDatasetButton: FC<{
  onClick: () => void;
  disabled?: boolean;
}> = ({onClick, disabled}) => {
  const buttonRef = useRef<HTMLButtonElement>(null);

  const handleClick = () => {
    // Force tooltip to close by blurring the button
    buttonRef.current?.blur();
    onClick();
  };

  return (
    <Button
      ref={buttonRef}
      variant="ghost"
      size="medium"
      onClick={handleClick}
      disabled={disabled}
      tooltip="Add selected rows to a dataset"
      icon="table">
      Add to dataset
    </Button>
  );
};

export const RefreshButton: FC<{
  onClick: () => void;
  disabled?: boolean;
}> = ({onClick, disabled}) => {
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
        onClick={onClick}
        disabled={disabled}
        tooltip="Refresh"
        icon="reload-refresh"
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

function makeLeafColumns(visibleColumns: string[]) {
  // Filter columns down to only the most nested, for example
  // ['output', 'output.x', 'output.x.y'] -> ['output.x.y']
  // sort columns by length, longest to shortest
  visibleColumns.sort((a, b) => b.length - a.length);
  const leafColumns: string[] = [];
  for (const col of visibleColumns) {
    if (leafColumns.some(leafCol => leafCol.startsWith(col))) {
      continue;
    }
    leafColumns.push(col);
  }
  return leafColumns;
}

function makeCodeText(
  project: string,
  callIds: string[] | undefined,
  filter: CallFilter,
  query: Query | undefined,
  sortBy: Array<{field: string; direction: 'asc' | 'desc'}>,
  includeFeedback: boolean,
  includeCosts: boolean
) {
  let codeStr = `import weave\n\nclient = weave.init("${project}")`;
  codeStr += `\ncalls = client.get_calls(\n`;
  const filteredCallIds = callIds ?? filter.callIds;
  if (filteredCallIds && filteredCallIds.length > 0) {
    codeStr += `   filter={"call_ids": ["${filteredCallIds.join('", "')}"]},\n`;
    if (includeFeedback) {
      codeStr += `   include_feedback=True,\n`;
    }
    if (includeCosts) {
      codeStr += `   include_costs=True,\n`;
    }
    // specifying call_ids ignores other filters, return early
    codeStr += `)`;
    return codeStr;
  }
  if (Object.values(filter).some(value => value !== undefined)) {
    codeStr += `    filter={`;
    if (filter.opVersionRefs) {
      codeStr += `"op_names": ["${filter.opVersionRefs.join('", "')}"],`;
    }
    if (filter.runIds) {
      codeStr += `"run_ids": ["${filter.runIds.join('", "')}"],`;
    }
    if (filter.userIds) {
      codeStr += `"user_ids": ["${filter.userIds.join('", "')}"],`;
    }
    if (filter.traceId) {
      codeStr += `"trace_ids": ["${filter.traceId}"],`;
    }
    if (filter.traceRootsOnly) {
      codeStr += `"trace_roots_only": True,`;
    }
    if (filter.parentIds) {
      codeStr += `"parent_ids": ["${filter.parentIds.join('", "')}"],`;
    }
    codeStr = codeStr.slice(0, -1);
    codeStr += `},\n`;
  }
  if (query) {
    codeStr += `    query=${JSON.stringify(query, null, 0)},\n`;
  }

  if (sortBy.length > 0) {
    codeStr += `    sort_by=${JSON.stringify(sortBy, null, 0)},\n`;
  }
  if (includeFeedback) {
    codeStr += `    include_feedback=True,\n`;
  }
  if (includeCosts) {
    codeStr += `    include_costs=True,\n`;
  }

  codeStr += `)`;

  return codeStr;
}

function makeCurlText(
  entity: string,
  project: string,
  callIds: string[] | undefined,
  filter: CallFilter,
  query: Query | undefined,
  expandColumns: string[],
  sortBy: Array<{field: string; direction: 'asc' | 'desc'}>,
  includeFeedback: boolean,
  includeCosts: boolean
) {
  const baseUrl = (window as any).CONFIG.TRACE_BACKEND_BASE_URL;
  const filterStr = JSON.stringify(
    {
      op_names: filter.opVersionRefs,
      input_refs: filter.inputObjectVersionRefs,
      output_refs: filter.outputObjectVersionRefs,
      parent_ids: filter.parentIds,
      trace_ids: filter.traceId ? [filter.traceId] : undefined,
      call_ids: callIds,
      trace_roots_only: filter.traceRootsOnly,
      wb_run_ids: filter.runIds,
      wb_user_ids: filter.userIds,
    },
    null,
    0
  );

  let baseCurl = `# Ensure you have a WANDB_API_KEY set in your environment
curl '${baseUrl}/calls/stream_query' \\
  -u api:$WANDB_API_KEY \\
  -H 'content-type: application/json' \\
  --data-raw '{
    "project_id":"${entity}/${project}",
    "filter":${filterStr},
`;
  if (query) {
    baseCurl += `    "query":${JSON.stringify(query, null, 0)},\n`;
  }
  if (expandColumns.length > 0) {
    baseCurl += `    "expand_columns":${JSON.stringify(
      expandColumns,
      null,
      0
    )},\n`;
  }
  baseCurl += `    "limit":${MAX_EXPORT},
    "offset":0,
    "sort_by":${JSON.stringify(sortBy, null, 0)},
    "include_feedback": ${includeFeedback},
    "include_costs": ${includeCosts}
  }'`;

  return baseCurl;
}

type PageSizeOption = {
  readonly value: number;
  readonly label: string;
};

type PaginationButtonsProps = {
  hideControls?: boolean;
};

export const PaginationButtons = ({hideControls}: PaginationButtonsProps) => {
  const apiRef = useGridApiContext();
  const page = useGridSelector(apiRef, gridPageSelector);
  const pageCount = useGridSelector(apiRef, gridPageCountSelector);
  const pageSize = useGridSelector(apiRef, gridPageSizeSelector);
  const rowCount = useGridSelector(apiRef, gridRowCountSelector);

  const handlePrevPage = () => {
    apiRef.current.setPage(page - 1);
  };

  const handleNextPage = () => {
    apiRef.current.setPage(page + 1);
  };

  // Calculate the item range being displayed
  const start = rowCount > 0 ? page * pageSize + 1 : 0;
  const end = Math.min(rowCount, (page + 1) * pageSize);

  const pageSizes = [10, 25, 50, 100];
  if (!pageSizes.includes(pageSize)) {
    pageSizes.push(pageSize);
    pageSizes.sort((a, b) => a - b);
  }
  const pageSizeOptions = pageSizes.map(sz => ({
    value: sz,
    label: sz.toString(),
  }));
  const pageSizeValue = pageSizeOptions.find(o => o.value === pageSize);
  const onPageSizeChange = (option: PageSizeOption | null) => {
    if (option) {
      apiRef.current.setPageSize(option.value);
    }
  };

  return (
    <Box
      display="flex"
      alignItems="center"
      justifyContent="space-between"
      width="100%"
      padding={1}>
      <Box display="flex" alignItems="center">
        <Button
          variant="ghost"
          size="medium"
          onClick={handlePrevPage}
          disabled={page === 0}
          icon="chevron-back"
        />
        <Box
          mx={1}
          sx={{
            fontSize: '14px',
            fontWeight: '400',
            color: MOON_500,
            // This is so that when we go from 1-100 -> 101-200, the buttons don't jump
            minWidth: '90px',
            display: 'flex',
            justifyContent: 'center',
          }}>
          {start}-{end} of {rowCount}
        </Box>
        <Button
          variant="ghost"
          size="medium"
          onClick={handleNextPage}
          disabled={page >= pageCount - 1}
          icon="chevron-next"
        />
      </Box>
      {hideControls ? null : (
        <Box
          sx={{
            fontSize: '14px',
            fontWeight: '400',
            color: MOON_500,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            // Regrettable hack to appear over Material scrollbar's z-index of 6.
            zIndex: 7,
          }}>
          Per page:
          <Select<PageSizeOption>
            size="small"
            menuPlacement="top"
            options={pageSizeOptions}
            value={pageSizeValue}
            isSearchable={false}
            onChange={onPageSizeChange}
          />
        </Box>
      )}
    </Box>
  );
};
