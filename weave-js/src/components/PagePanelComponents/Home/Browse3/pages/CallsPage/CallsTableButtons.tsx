import React, { useState, useEffect, FC } from 'react';
import { saveAs } from 'file-saver';
import { toast } from '@wandb/weave/common/components/elements/Toast';
import { Button } from '@wandb/weave/components/Button';
import { Tailwind } from '@wandb/weave/components/Tailwind';
import { WFHighLevelCallFilter } from './callsTableFilter';
import { useCallsExportStream } from './callsTableQuery';
import { ContentType, ContentTypeJson, ContentTypeText } from '../wfReactInterface/traceServerClientTypes';
import { GridApiPro, GridFilterModel, GridSortModel } from '@mui/x-data-grid-pro';
import { Box } from '@mui/material';
import ModifiedDropdown from '@wandb/weave/common/components/elements/ModifiedDropdown';

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
    const [clickedOption, setClickedOption] = useState<ContentType | null>(null);
    const fileName = `${pageName}-export`;

    const {loading, result} = useCallsExportStream(
      callQueryParams.entity,
      callQueryParams.project,
      clickedOption ?? ContentTypeJson.jsonl,
      callQueryParams.filter,
      callQueryParams.gridFilter,
      callQueryParams.gridSort ?? null,
      MAX_EXPORT,
      clickedOption == null
    );
  
    useEffect(() => {
      if (!clickedOption) {
        return;
      } else if (loading && !result) {
        // TODO(gst): warn if large download?
        return;
      }
  
      if (!result) {
        toast('Error, no calls to export', {type: 'error'});
      } else {
        try {
          let extension = ''
          if (clickedOption === ContentTypeJson.jsonl) {
            extension = 'jsonl';
          } else if (clickedOption === ContentTypeJson.json) {
            extension = 'json';
          } else if (clickedOption === ContentTypeText.csv) {
            extension = 'csv';
          }
          saveAs(result, `${fileName}.${extension}`);
        } catch {
          toast('Error exporting calls', {type: 'error'});
        } finally {
          setClickedOption(null);
        }
      }
    }, [clickedOption, loading, result, fileName]);
  
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
                variant='ghost'
                disabled={loading}
              />
            }
            disabled={loading}
            direction='left'
            search={false}
            options={[
              {
                value: 'export-jsonl',
                text: 'Export to jsonl',
                onClick: () => setClickedOption(ContentTypeJson.jsonl),
              },
              {
                value: 'export-json',
                text: 'Export to json',
                onClick: () => setClickedOption(ContentTypeJson.json),
              },
              {
                value: 'export-csv',
                text: 'Export to csv',
                onClick: () => setClickedOption(ContentTypeText.csv),
              },
              {
                value: 'export selected',
                text: `Export selected calls (${selectedCalls.length})`,
                onClick: selectedCalls.length > 0 ? () => selectedExport() : undefined,
                disabled: selectedCalls.length === 0,
              }
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
