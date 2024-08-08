import {Box, Popover} from '@mui/material';
import {GridFilterModel, GridSortModel} from '@mui/x-data-grid-pro';
import {Radio} from '@wandb/weave/components';
import {Button} from '@wandb/weave/components/Button';
import {CodeEditor} from '@wandb/weave/components/CodeEditor';
import {
  DraggableGrow,
  DraggableHandle,
} from '@wandb/weave/components/DraggablePopups';
import {Icon, IconName} from '@wandb/weave/components/Icon';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {Dispatch, FC, SetStateAction, useRef, useState} from 'react';

import {useWFHooks} from '../wfReactInterface/context';
import {
  ContentType,
  fileExtensions,
} from '../wfReactInterface/traceServerClientTypes';
import {CallFilter} from '../wfReactInterface/wfDataModelHooksInterface';
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
  rightmostButton = false,
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
  rightmostButton?: boolean;
}) => {
  const [selectionState, setSelectionState] = useState<SelectionState>('all');

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
    lowLevelFilter.callIds =
      selectionState === 'selected' ? selectedCalls : undefined;
    // TODO(gst): allow specifying offset?
    const offset = 0;
    const limit = MAX_EXPORT;
    download(
      callQueryParams.entity,
      callQueryParams.project,
      contentType,
      lowLevelFilter,
      limit,
      offset,
      sortBy,
      filterBy,
      visibleColumns
    ).then(blob => {
      const fileExtension = fileExtensions[contentType];
      const date = new Date().toISOString().split('T')[0];
      const fileName = `weave_export_${callQueryParams.project}_${date}.${fileExtension}`;
      initiateDownloadFromBlob(blob, fileName);
      setAnchorEl(null);
    });
    setSelectionState('all');
  };

  const pythonText = useMakeCodeText(
    callQueryParams.entity,
    callQueryParams.project,
    selectedCalls,
    lowLevelFilter,
    sortBy
  );
  const curlText = useMakeCurlText(
    callQueryParams.entity,
    callQueryParams.project,
    selectedCalls,
    lowLevelFilter,
    sortBy
  );

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
          setSelectionState('all');
        }}
        TransitionComponent={DraggableGrow}>
        <Tailwind>
          <div className="min-w-[560px] max-w-[660px] p-12">
            <DraggableHandle>
              <div className="flex items-center pb-8">
                {selectedCalls.length === 0 ? (
                  <div className="flex-auto text-xl font-semibold">
                    Export ({numTotalCalls})
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
            <DownloadGrid
              pythonText={pythonText}
              curlText={curlText}
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
  onClick?: () => void;
}> = ({iconName, children, onClick}) => (
  <div
    className="flex w-full cursor-pointer items-center rounded-md border border-moon-200 p-16 hover:bg-moon-100"
    onClick={onClick}>
    <div className="mr-4 rounded-2xl bg-moon-200 p-4">
      <Icon size="xlarge" color="moon" name={iconName} />
    </div>
    <div className="ml-4">{children}</div>
  </div>
);

const DownloadGrid: FC<{
  pythonText: string;
  curlText: string;
  onClickDownload: (contentType: ContentType) => void;
}> = ({pythonText, curlText, onClickDownload}) => {
  const [codeMode, setCodeMode] = useState<'python' | 'curl' | null>(null);
  return (
    <>
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
      <div className="mt-8 flex items-center">
        <ClickableOutlinedCardWithIcon
          iconName="python-logo"
          onClick={() => setCodeMode('python')}>
          Use Python
        </ClickableOutlinedCardWithIcon>
        <div className="ml-8" />
        <ClickableOutlinedCardWithIcon
          iconName="code-alt"
          onClick={() => setCodeMode('curl')}>
          Use CURL
        </ClickableOutlinedCardWithIcon>
      </div>
      {codeMode && (
        <div className="mt-8 flex max-w-full items-center">
          <CodeEditor
            value={codeMode === 'python' ? pythonText : curlText}
            readOnly={true}
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

function useMakeCodeText(
  entity: string,
  project: string,
  callIds: string[],
  filter: CallFilter,
  sortBy: Array<{field: string; direction: 'asc' | 'desc'}>
) {
  console.log(filter);
  let codeStr = `import weave\nfrom weave.weave_client import _CallsFilter\nclient = weave.init("${entity}/${project}")`;

  const filteredCallIds = callIds ?? filter.callIds;
  if (filteredCallIds.length > 0) {
    // specifying call_ids ignores other filters
    codeStr += `\ncalls = client.calls(_CallsFilter(\n\tcall_ids=["${filteredCallIds.join(
      '", "'
    )}"],\n))`;
    return codeStr;
  }

  codeStr += `\ncalls = client.calls(_CallsFilter(\n`;
  if (filter.opVersionRefs) {
    codeStr += `\top_names=["${filter.opVersionRefs.join('", "')}"],\n`;
  }
  if (filter.runIds) {
    codeStr += `\trun_ids=["${filter.runIds.join('", "')}"],\n`;
  }
  if (filter.userIds) {
    codeStr += `\tuser_ids=["${filter.userIds.join('", "')}"],\n`;
  }
  if (filter.traceId) {
    codeStr += `\ttrace_id="${filter.traceId}",\n`;
  }
  if (filter.traceRootsOnly) {
    codeStr += `\ttrace_roots_only=True,\n`;
  }
  if (filter.parentIds) {
    codeStr += `\tparent_ids=["${filter.parentIds.join('", "')}"],\n`;
  }

  if (sortBy.length > 0) {
    codeStr += `\tsort_by=${JSON.stringify(sortBy, null, 0)},\n`;
  }

  codeStr += `))`;

  return codeStr;
}

function useMakeCurlText(
  entity: string,
  project: string,
  callIds: string[],
  filter: CallFilter,
  sortBy: Array<{field: string; direction: 'asc' | 'desc'}>
) {
  const baseUrl = 'https://trace.wandb.ai';
  const authHeader = '';

  const filterStr = JSON.stringify(
    {
      op_names: filter.opVersionRefs,
      input_refs: filter.inputObjectVersionRefs,
      output_refs: filter.outputObjectVersionRefs,
      parent_ids: filter.parentIds,
      trace_ids: filter.traceId ? [filter.traceId] : undefined,
      call_ids: filter.callIds,
      trace_roots_only: filter.traceRootsOnly,
      wb_run_ids: filter.runIds,
      wb_user_ids: filter.userIds,
    },
    null,
    0
  );
  const sortByStr = JSON.stringify(sortBy, null, 0);

  return `curl '${baseUrl}/calls/stream_query' \
  -H '${authHeader}' \
  -H 'content-type: application/json' \
  --data-raw '{
    "project_id":"${entity}/${project}",
    "filter":${filterStr},
    "limit":${MAX_EXPORT},
    "offset":0,
    "sort_by":${sortByStr}
 }'`;
}
