import {Box} from '@mui/material';
import {GridApiPro, GridFilterModel, GridSortModel} from '@mui/x-data-grid-pro';
import ModifiedDropdown from '@wandb/weave/common/components/elements/ModifiedDropdown';
import {toast} from '@wandb/weave/common/components/elements/Toast';
import {Button} from '@wandb/weave/components/Button';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {FC, useEffect, useState} from 'react';

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
      filterBy
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
              // onClick: () => setClickedOption(ContentType.json),
              disabled: true,
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
