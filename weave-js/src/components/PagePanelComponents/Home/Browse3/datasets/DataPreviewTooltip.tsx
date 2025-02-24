import {Box, Paper, Tooltip, TooltipProps} from '@mui/material';
import React from 'react';

import {WaveLoader} from '../../../../Loaders/WaveLoader';
import {CellValue} from '../../Browse2/CellValue';

interface DataPreviewTooltipProps {
  rows?: Array<Record<string, any>>;
  maxRows?: number;
  maxColumns?: number;
  children: React.ReactElement;
  tooltipProps?: Partial<TooltipProps>;
  isLoading?: boolean;
}

export const DataPreviewTooltip: React.FC<DataPreviewTooltipProps> = ({
  rows,
  maxRows = 5,
  maxColumns = 3,
  children,
  tooltipProps,
  isLoading = false,
}) => {
  if (isLoading) {
    return (
      <Tooltip
        title={
          <Box sx={{display: 'flex', justifyContent: 'center'}}>
            <WaveLoader size="small" />
          </Box>
        }
        placement="right"
        enterDelay={600}
        enterNextDelay={200}
        leaveDelay={0}
        slotProps={{
          tooltip: {
            sx: {
              bgcolor: 'white',
              color: 'inherit',
              boxShadow: '0px 2px 8px rgba(0, 0, 0, 0.15)',
              p: 0,
            },
          },
        }}
        {...tooltipProps}>
        {children}
      </Tooltip>
    );
  }

  if (!rows?.length) {
    return <>{children}</>;
  }

  const previewRows = rows.slice(0, maxRows);
  const allColumns = Array.from(
    new Set(previewRows.flatMap(row => Object.keys(row)))
  );
  const previewColumns = allColumns.slice(0, maxColumns);
  const hasMoreColumns = allColumns.length > maxColumns;
  const hasMoreRows = rows.length > maxRows;

  const tooltipContent = (
    <Paper
      elevation={0}
      sx={{
        maxWidth: '800px',
        maxHeight: '400px',
        fontFamily: 'Source Sans Pro',
        fontSize: '14px',
        borderRadius: 1,
        overflow: 'hidden',
      }}>
      <Box
        sx={{
          overflowX: 'auto',
          overflowY: 'auto',
          maxHeight: '400px',
        }}>
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: `repeat(${
              previewColumns.length + (hasMoreColumns ? 1 : 0)
            }, minmax(120px, 1fr))`,
            minWidth: 'fit-content',
            gap: 0,
            border: '1px solid rgba(224, 224, 224, 1)',
            borderRadius: 1,
          }}>
          {/* Header row */}
          {previewColumns.map((column, colIndex) => (
            <Box
              key={column}
              sx={{
                color: 'text.secondary',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                p: 1,
                borderBottom: '1px solid rgba(224, 224, 224, 1)',
                borderRight:
                  colIndex < previewColumns.length - 1 || hasMoreColumns
                    ? '1px solid rgba(224, 224, 224, 1)'
                    : 'none',
                bgcolor: '#fafafa',
                position: 'sticky',
                top: 0,
                zIndex: 1,
              }}>
              {column}
            </Box>
          ))}
          {hasMoreColumns && (
            <Box
              sx={{
                color: 'text.secondary',
                fontStyle: 'italic',
                p: 1,
                borderBottom: '1px solid rgba(224, 224, 224, 1)',
                bgcolor: '#fafafa',
                position: 'sticky',
                top: 0,
                zIndex: 1,
              }}>
              +{allColumns.length - maxColumns} more
            </Box>
          )}

          {/* Data rows */}
          {previewRows.map((row, rowIndex) => (
            <React.Fragment key={rowIndex}>
              {previewColumns.map((column, colIndex) => (
                <Box
                  key={column}
                  sx={{
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    p: 1,
                    borderBottom:
                      rowIndex < previewRows.length - 1
                        ? '1px solid rgba(224, 224, 224, 1)'
                        : 'none',
                    borderRight:
                      colIndex < previewColumns.length - 1 || hasMoreColumns
                        ? '1px solid rgba(224, 224, 224, 1)'
                        : 'none',
                    maxWidth: '300px',
                  }}>
                  <Box
                    onClick={e => e.stopPropagation()}
                    onMouseEnter={e => e.stopPropagation()}
                    onMouseLeave={e => e.stopPropagation()}>
                    <CellValue value={row[column]} noLink />
                  </Box>
                </Box>
              ))}
              {hasMoreColumns && (
                <Box
                  sx={{
                    color: 'text.secondary',
                    fontStyle: 'italic',
                    p: 1,
                    borderBottom:
                      rowIndex < previewRows.length - 1
                        ? '1px solid rgba(224, 224, 224, 1)'
                        : 'none',
                  }}>
                  ...
                </Box>
              )}
            </React.Fragment>
          ))}
        </Box>
      </Box>

      {hasMoreRows && (
        <Box
          sx={{
            mt: 1,
            color: 'text.secondary',
            fontStyle: 'italic',
            textAlign: 'center',
          }}>
          {rows.length - maxRows} more rows...
        </Box>
      )}
    </Paper>
  );

  return (
    <Tooltip
      title={tooltipContent}
      placement="right"
      enterDelay={600}
      enterNextDelay={200}
      leaveDelay={0}
      slotProps={{
        tooltip: {
          sx: {
            bgcolor: 'white',
            color: 'inherit',
            boxShadow: '0px 2px 8px rgba(0, 0, 0, 0.15)',
            p: 0,
          },
        },
      }}
      {...tooltipProps}>
      {children}
    </Tooltip>
  );
};
