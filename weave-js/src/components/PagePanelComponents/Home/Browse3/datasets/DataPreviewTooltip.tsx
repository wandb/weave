import {Box, Paper, Tooltip, TooltipProps, Typography} from '@mui/material';
import React from 'react';

import {TEAL_600} from '../../../../../common/css/globals.styles';
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

  // Helper to render cell content with special handling for missing values
  const renderCellContent = (row: Record<string, any>, column: string) => {
    const value = row[column];
    if (value === undefined || value === null) {
      return (
        <Typography
          component="code"
          sx={{
            fontFamily: 'monospace',
            fontSize: '12px',
            backgroundColor: 'rgba(0, 0, 0, 0.04)',
            padding: '2px 4px',
            borderRadius: '2px',
            color: TEAL_600,
            fontWeight: 'bold',
          }}>
          undefined
        </Typography>
      );
    }
    return (
      <Box
        onClick={e => e.stopPropagation()}
        onMouseEnter={e => e.stopPropagation()}
        onMouseLeave={e => e.stopPropagation()}>
        <CellValue value={value} noLink />
      </Box>
    );
  };

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
        border: '1px solid rgba(224, 224, 224, 1)',
      }}>
      <Box
        sx={{
          overflowX: 'auto',
          overflowY: 'auto',
          maxHeight: '400px',
        }}>
        {/* Table Structure */}
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: `repeat(${
              previewColumns.length + (hasMoreColumns ? 1 : 0)
            }, minmax(120px, 1fr))`,
            minWidth: 'fit-content',
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
                    minHeight: '32px', // Ensure all cells have at least a minimum height
                    display: 'flex',
                    alignItems: 'center',
                    backgroundColor: 'transparent',
                  }}>
                  {renderCellContent(row, column)}
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

        {/* More rows indicator */}
        {hasMoreRows && (
          <Box
            sx={{
              p: 1,
              color: 'text.secondary',
              fontStyle: 'italic',
              textAlign: 'center',
              borderTop: '1px solid rgba(224, 224, 224, 1)',
              backgroundColor: '#fafafa',
            }}>
            {rows.length - maxRows} more rows...
          </Box>
        )}
      </Box>
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
