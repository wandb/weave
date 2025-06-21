import {Box, Tooltip, TooltipProps} from '@mui/material';
import {GridRenderCellParams} from '@mui/x-data-grid-pro';
import {Button} from '@wandb/weave/components/Button';
import {Icon} from '@wandb/weave/components/Icon';
import React, {useCallback, useLayoutEffect, useRef, useState} from 'react';

import {CellValue} from '../../Browse2/CellValue';
import {isRefPrefixedString} from '../filters/common';
import {useDatasetEditContext} from './DatasetEditorContext';
import {EditPopover} from './EditPopover';

export const CELL_COLORS = {
  DELETED: '#FFE6E6', // Red 200
  EDITED: '#E0EDFE', // Blue 200
  NEW: '#E4F7EE', // Green 200
  TRANSPARENT: 'transparent',
} as const;

export const DELETED_CELL_STYLES = {
  opacity: 0.5,
  textDecoration: 'line-through' as const,
} as const;

const cellViewingStyles = {
  height: '100%',
  width: '100%',
  display: 'flex',
  padding: '8px 12px',
  alignItems: 'center',
  justifyContent: 'center',
  transition: 'background-color 0.2s ease',
};

interface CellProps extends GridRenderCellParams {
  isEdited?: boolean;
  isDeleted?: boolean;
  isNew?: boolean;
  serverValue?: any;
  disableNewRowHighlight?: boolean;
  preserveFieldOrder?: (row: any) => any;
}

// Custom tooltip component to reduce repetition
const CellTooltip: React.FC<{
  title: string;
  children: React.ReactElement;
  placement?: TooltipProps['placement'];
}> = ({title, children, placement = 'top'}) => (
  <Tooltip
    title={title}
    enterDelay={1000}
    enterNextDelay={1000}
    leaveDelay={0}
    placement={placement}
    slotProps={{
      tooltip: {
        sx: {
          fontFamily: '"Source Sans Pro", sans-serif',
          fontSize: '14px',
        },
      },
    }}>
    {children}
  </Tooltip>
);

export const DatasetCellRenderer: React.FC<CellProps> = ({
  value,
  isEdited = false,
  isDeleted = false,
  isNew = false,
  id,
  field,
  row,
  serverValue,
  disableNewRowHighlight = false,
  preserveFieldOrder,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const [editedValue, setEditedValue] = useState(value);
  const {updateCellValue} = useDatasetEditContext();

  // Refs and state for edit popover
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [anchorEl, setAnchorEl] = useState<HTMLDivElement | null>(null);
  const initialWidth = useRef<number>();
  const initialHeight = useRef<number>();

  useLayoutEffect(() => {
    if (isEditing) {
      const element = document.activeElement?.closest('.MuiDataGrid-cell');
      if (element) {
        setAnchorEl(element as HTMLDivElement);
      }
    }
  }, [isEditing]);

  const isWeaveUrl = isRefPrefixedString(value);
  const isJsonList = Array.isArray(value);
  const isEditable =
    !isDeleted &&
    !isWeaveUrl &&
    (typeof value !== 'object' || isJsonList) &&
    typeof value !== 'boolean';

  // Use the context's updateCellValue function instead of local implementation
  const handleUpdateValue = useCallback(
    (newValue: any) => {
      updateCellValue(row, field, newValue, serverValue, preserveFieldOrder);
    },
    [row, field, serverValue, preserveFieldOrder, updateCellValue]
  );

  const handleEditClick = (event: React.MouseEvent) => {
    event.stopPropagation();
    if (isEditable) {
      setIsEditing(true);
    }
  };

  const handleCloseEdit = (valueOverride?: any) => {
    setIsEditing(false);
    // Use the provided valueOverride if available, otherwise use editedValue
    const finalValue =
      valueOverride !== undefined ? valueOverride : editedValue;
    // Only update if the value has changed
    if (finalValue !== value) {
      handleUpdateValue(finalValue);
    }
  };

  const handleValueChange = (newValue: string | any[]) => {
    setEditedValue(newValue);
  };

  const handleRevert = (event: React.MouseEvent) => {
    event.stopPropagation();
    setEditedValue(serverValue); // Reset editedValue to serverValue
    handleUpdateValue(serverValue);
  };

  const getBackgroundColor = () => {
    if (isDeleted) {
      return CELL_COLORS.DELETED;
    }
    if (isEdited) {
      return CELL_COLORS.EDITED;
    }
    if (isNew && !disableNewRowHighlight) {
      return CELL_COLORS.NEW;
    }
    return CELL_COLORS.TRANSPARENT;
  };

  // Special handler for boolean values - toggle directly
  if (typeof value === 'boolean') {
    const handleToggle = (e: React.MouseEvent) => {
      e.stopPropagation();
      e.preventDefault();
      handleUpdateValue(!value);
    };

    return (
      <CellTooltip title="Click to toggle">
        <Box
          onClick={handleToggle}
          onDoubleClick={handleToggle}
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            width: '100%',
            backgroundColor: getBackgroundColor(),
            opacity: isDeleted ? DELETED_CELL_STYLES.opacity : 1,
            textDecoration: isDeleted
              ? DELETED_CELL_STYLES.textDecoration
              : 'none',
            cursor: 'pointer',
            transition: 'background-color 0.2s ease',
            borderLeft: '1px solid transparent',
            borderRight: '1px solid transparent',
            '&:hover': {
              borderLeft: '1px solid #DFE0E2',
              borderRight: '1px solid #DFE0E2',
            },
          }}>
          <Icon
            name={value ? 'checkmark' : 'close'}
            height={20}
            width={20}
            style={{
              color: value ? '#00875A' : '#CC2944',
            }}
          />
        </Box>
      </CellTooltip>
    );
  }

  // Non-editable cell types (objects except arrays, weave URLs)
  if (!isEditable) {
    return (
      <CellTooltip title="Cell type cannot be edited">
        <Box
          onClick={e => {
            e.stopPropagation();
            e.preventDefault();
          }}
          onDoubleClick={e => {
            e.stopPropagation();
            e.preventDefault();
          }}
          onKeyDown={e => e.preventDefault()}
          tabIndex={-1}
          onMouseDown={e => {
            e.stopPropagation();
            e.preventDefault();
          }}
          sx={{
            height: '100%',
            backgroundColor: getBackgroundColor(),
            opacity: isDeleted ? DELETED_CELL_STYLES.opacity : 1,
            textDecoration: isDeleted
              ? DELETED_CELL_STYLES.textDecoration
              : 'none',
            alignContent: 'center',
            paddingLeft: '8px',
          }}>
          <CellValue value={value} noLink={true} field={field} />
        </Box>
      </CellTooltip>
    );
  }

  // Render cell in view mode
  if (!isEditing) {
    return (
      <CellTooltip title="Click to edit">
        <Box
          onClick={handleEditClick}
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
          sx={{
            ...cellViewingStyles,
            position: 'relative',
            cursor: 'pointer',
            backgroundColor: getBackgroundColor(),
            opacity: isDeleted ? DELETED_CELL_STYLES.opacity : 1,
            textDecoration: isDeleted
              ? DELETED_CELL_STYLES.textDecoration
              : 'none',
            borderLeft: '1px solid transparent',
            borderRight: '1px solid transparent',
            '&:hover': {
              borderLeft: '1px solid #DFE0E2',
              borderRight: '1px solid #DFE0E2',
            },
          }}>
          <span style={{flex: 1, position: 'relative', overflow: 'hidden'}}>
            {isJsonList ? JSON.stringify(value) : value}
          </span>
          {isHovered && (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                opacity: 0,
                transition: 'opacity 0.2s ease',
                cursor: 'pointer',
                animation: 'fadeIn 0.2s ease forwards',
                '@keyframes fadeIn': {
                  from: {opacity: 0},
                  to: {opacity: 0.5},
                },
                '&:hover': {
                  opacity: 0.8,
                },
              }}>
              {isEdited ? (
                <Button
                  icon="undo"
                  onClick={handleRevert}
                  variant="secondary"
                  size="small"
                  style={{padding: '2px 4px', minWidth: 0}}
                  tooltip="Revert to original value"
                />
              ) : (
                <Icon name="pencil-edit" height={14} width={14} />
              )}
            </Box>
          )}
        </Box>
      </CellTooltip>
    );
  }

  if (typeof value === 'number') {
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          height: '100%',
          width: '100%',
          border: '2px solid rgb(77, 208, 225)',
          backgroundColor: 'rgba(77, 208, 225, 0.2)',
        }}>
        <input
          type="number"
          value={typeof editedValue === 'number' ? editedValue.toString() : ''}
          onChange={e => setEditedValue(Number(e.target.value))}
          onKeyDown={e => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
              handleCloseEdit();
            } else if (e.key === 'Enter') {
              handleCloseEdit();
            } else if (e.key === 'Escape') {
              setIsEditing(false);
              setEditedValue(value); // Reset to original
            }
          }}
          onBlur={() => handleCloseEdit()}
          autoFocus
          style={{
            width: '100%',
            height: '100%',
            border: 'none',
            outline: 'none',
            background: 'none',
            textAlign: 'left',
            padding: '8px 12px',
            fontFamily: 'inherit',
            fontSize: 'inherit',
            color: 'inherit',
          }}
        />
      </Box>
    );
  }

  // For text/string values with EditPopover
  return (
    <>
      <Box
        sx={{
          ...cellViewingStyles,
          position: 'relative',
          cursor: 'pointer',
          backgroundColor: 'rgba(77, 208, 225, 0.2)',
          border: '2px solid rgb(77, 208, 225)',
        }}>
        <span style={{flex: 1, position: 'relative', overflow: 'hidden'}}>
          {value}
        </span>
      </Box>
      <EditPopover
        anchorEl={anchorEl}
        onClose={finalValue => handleCloseEdit(finalValue)}
        initialWidth={initialWidth.current}
        initialHeight={initialHeight.current}
        value={value}
        originalValue={serverValue ?? ''}
        onChange={handleValueChange}
        inputRef={inputRef}
        initialEditorMode={isJsonList ? 'code' : 'text'}
      />
    </>
  );
};

export interface ControlCellProps {
  params: GridRenderCellParams;
  deleteRow: (index: number) => void;
  deleteAddedRow: (id: string) => void;
  restoreRow: (index: number) => void;
  isDeleted: boolean;
  isNew: boolean;
  hideRemoveForAddedRows?: boolean;
  disableNewRowHighlight?: boolean;
}

export const ControlCell: React.FC<ControlCellProps> = ({
  params,
  deleteRow,
  deleteAddedRow,
  restoreRow,
  isDeleted,
  isNew,
  hideRemoveForAddedRows,
  disableNewRowHighlight = false,
}) => {
  const rowId = params.id as string;
  const rowIndex = params.row.___weave?.index;

  // Hide remove button for added rows if requested
  if (isNew && hideRemoveForAddedRows) {
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          width: '100%',
          backgroundColor: disableNewRowHighlight
            ? CELL_COLORS.TRANSPARENT
            : CELL_COLORS.NEW,
        }}
      />
    );
  }

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        width: '100%',
        backgroundColor: isDeleted
          ? CELL_COLORS.DELETED
          : isNew && !disableNewRowHighlight
          ? CELL_COLORS.NEW
          : CELL_COLORS.TRANSPARENT,
        opacity: isDeleted ? DELETED_CELL_STYLES.opacity : 1,
        textDecoration: isDeleted ? DELETED_CELL_STYLES.textDecoration : 'none',
      }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          opacity: 1,
          transition: 'opacity 200ms ease',
          '.MuiDataGrid-row:not(:hover) &': {
            opacity: 0,
          },
          zIndex: 1000,
          backgroundColor: 'transparent',
        }}>
        {isDeleted ? (
          <Button
            onClick={() => restoreRow(rowIndex)}
            tooltip="Restore"
            icon="undo"
            size="small"
            variant="secondary"
          />
        ) : (
          <Button
            onClick={() =>
              isNew ? deleteAddedRow(rowId) : deleteRow(rowIndex)
            }
            tooltip="Delete"
            icon="delete"
            size="small"
            variant="secondary"
          />
        )}
      </Box>
    </Box>
  );
};

export interface ControlsColumnHeaderProps {
  onAddRow: () => void;
}

export const ControlsColumnHeader: React.FC<ControlsColumnHeaderProps> = ({
  onAddRow,
}) => (
  <Box
    sx={{
      margin: '2px',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      height: '100%',
    }}>
    <Button
      icon="add-new"
      onClick={onAddRow}
      variant="ghost"
      size="small"
      tooltip="Add row"
    />
  </Box>
);
