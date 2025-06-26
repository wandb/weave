import {Box} from '@mui/material';
import {GridRenderCellParams} from '@mui/x-data-grid-pro';
import {Icon} from '@wandb/weave/components/Icon';
import React, {useCallback, useEffect, useRef, useState} from 'react';

import {CellValue} from '../../Browse2/CellValue';
import {isRefPrefixedString} from '../filters/common';
import {useDatasetEditContext} from './DatasetEditorContext';
import {
  CELL_COLORS,
  DELETED_CELL_STYLES,
  CellTooltip,
} from './CellRenderers';

interface InlineCellProps extends GridRenderCellParams {
  isEdited?: boolean;
  isDeleted?: boolean;
  isNew?: boolean;
  serverValue?: any;
  disableNewRowHighlight?: boolean;
  preserveFieldOrder?: (row: any) => any;
  onCellEditStart?: (params: {id: string; field: string}) => void;
  onCellEditStop?: () => void;
}

/**
 * InlineCellRenderer provides spreadsheet-like inline editing functionality.
 * - Click or press Enter to start editing
 * - Arrow keys navigate between cells
 * - Tab/Shift+Tab navigate horizontally
 * - Escape cancels editing
 */
export const InlineCellRenderer: React.FC<InlineCellProps> = ({
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
  api,
  onCellEditStart,
  onCellEditStop,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editedValue, setEditedValue] = useState(value);
  const {updateCellValue} = useDatasetEditContext();
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement>(null);

  const isWeaveUrl = isRefPrefixedString(value);
  const isJsonList = Array.isArray(value);
  const isEditable =
    !isDeleted &&
    !isWeaveUrl &&
    (typeof value !== 'object' || isJsonList) &&
    typeof value !== 'boolean';

  const handleUpdateValue = useCallback(
    (newValue: any) => {
      updateCellValue(row, field, newValue, serverValue, preserveFieldOrder);
    },
    [row, field, serverValue, preserveFieldOrder, updateCellValue]
  );

  const startEditing = useCallback(() => {
    if (isEditable && !isEditing) {
      setIsEditing(true);
      setEditedValue(value);
      onCellEditStart?.({id: id as string, field});
    }
  }, [isEditable, isEditing, value, onCellEditStart, id, field]);

  const stopEditing = useCallback(
    (save: boolean = true) => {
      if (isEditing) {
        setIsEditing(false);
        onCellEditStop?.();
        
        if (save && editedValue !== value) {
          // Handle JSON array parsing
          if (isJsonList && typeof editedValue === 'string') {
            try {
              const parsed = JSON.parse(editedValue);
              if (Array.isArray(parsed)) {
                handleUpdateValue(parsed);
              }
            } catch {
              // If parsing fails, keep the original value
            }
          } else {
            handleUpdateValue(editedValue);
          }
        } else if (!save) {
          setEditedValue(value);
        }
      }
    },
    [isEditing, editedValue, value, isJsonList, handleUpdateValue, onCellEditStop]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!isEditing && (e.key === 'Enter' || e.key === 'F2')) {
        e.preventDefault();
        e.stopPropagation();
        startEditing();
        return;
      }

      if (isEditing) {
        switch (e.key) {
          case 'Enter':
            if (!e.shiftKey) {
              e.preventDefault();
              e.stopPropagation();
              stopEditing(true);
              // Move to next row
              const rowIds = api?.getAllRowIds() || [];
              const currentRowIndex = rowIds.indexOf(id as string);
              if (currentRowIndex !== -1 && currentRowIndex < rowIds.length - 1) {
                api?.setCellFocus(rowIds[currentRowIndex + 1], field);
              }
            }
            break;
          case 'Tab':
            e.preventDefault();
            e.stopPropagation();
            stopEditing(true);
            // Let DataGrid handle Tab navigation
            break;
          case 'Escape':
            e.preventDefault();
            e.stopPropagation();
            stopEditing(false);
            break;
          case 'ArrowUp':
          case 'ArrowDown':
          case 'ArrowLeft':
          case 'ArrowRight':
            if (!e.shiftKey && !e.ctrlKey && !e.metaKey) {
              e.preventDefault();
              e.stopPropagation();
              stopEditing(true);
              
              // Navigate to the appropriate cell
              const rowIds = api?.getAllRowIds() || [];
              const currentRowIndex = rowIds.indexOf(id as string);
              const columns = api?.getAllColumns() || [];
              const currentColIndex = columns.findIndex(col => col.field === field);
              
              if (currentRowIndex !== -1 && currentColIndex !== -1) {
                let newRowIndex = currentRowIndex;
                let newColIndex = currentColIndex;
                
                switch (e.key) {
                  case 'ArrowUp':
                    newRowIndex = Math.max(0, currentRowIndex - 1);
                    break;
                  case 'ArrowDown':
                    newRowIndex = Math.min(rowIds.length - 1, currentRowIndex + 1);
                    break;
                  case 'ArrowLeft':
                    newColIndex = Math.max(0, currentColIndex - 1);
                    break;
                  case 'ArrowRight':
                    newColIndex = Math.min(columns.length - 1, currentColIndex + 1);
                    break;
                }
                
                if (rowIds[newRowIndex] && columns[newColIndex]) {
                  api?.setCellFocus(rowIds[newRowIndex], columns[newColIndex].field);
                }
              }
            }
            break;
        }
      }
    },
    [isEditing, startEditing, stopEditing, api, id, field]
  );

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

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

  // Handle boolean values with toggle
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
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              handleToggle(e as any);
            }
          }}
          tabIndex={0}
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            width: '100%',
            backgroundColor: getBackgroundColor(),
            opacity: isDeleted ? DELETED_CELL_STYLES.opacity : 1,
            textDecoration: isDeleted ? DELETED_CELL_STYLES.textDecoration : 'none',
            cursor: 'pointer',
            transition: 'background-color 0.2s ease',
            '&:focus': {
              outline: '2px solid rgb(77, 208, 225)',
              outlineOffset: '-2px',
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

  // Non-editable cells
  if (!isEditable) {
    return (
      <Box
        sx={{
          height: '100%',
          backgroundColor: getBackgroundColor(),
          opacity: isDeleted ? DELETED_CELL_STYLES.opacity : 1,
          textDecoration: isDeleted ? DELETED_CELL_STYLES.textDecoration : 'none',
          alignContent: 'center',
          paddingLeft: '8px',
        }}>
        <CellValue value={value} noLink={true} field={field} />
      </Box>
    );
  }

  // Editing mode
  if (isEditing) {
    const isNumber = typeof value === 'number';
    const isMultiline = isJsonList || (typeof value === 'string' && value.includes('\n'));
    
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          height: '100%',
          width: '100%',
          border: '2px solid rgb(77, 208, 225)',
          backgroundColor: 'rgba(77, 208, 225, 0.1)',
        }}>
        {isMultiline ? (
          <textarea
            ref={inputRef as React.RefObject<HTMLTextAreaElement>}
            value={isJsonList ? JSON.stringify(editedValue, null, 2) : String(editedValue)}
            onChange={e => setEditedValue(isJsonList ? e.target.value : e.target.value)}
            onKeyDown={handleKeyDown}
            onBlur={() => stopEditing(true)}
            style={{
              width: '100%',
              height: '100%',
              border: 'none',
              outline: 'none',
              background: 'none',
              padding: '4px 8px',
              fontFamily: 'monospace',
              fontSize: '12px',
              resize: 'none',
            }}
          />
        ) : (
          <input
            ref={inputRef as React.RefObject<HTMLInputElement>}
            type={isNumber ? 'number' : 'text'}
            value={String(editedValue)}
            onChange={e => setEditedValue(isNumber ? Number(e.target.value) : e.target.value)}
            onKeyDown={handleKeyDown}
            onBlur={() => stopEditing(true)}
            style={{
              width: '100%',
              height: '100%',
              border: 'none',
              outline: 'none',
              background: 'none',
              padding: '0 8px',
              fontFamily: 'inherit',
              fontSize: 'inherit',
            }}
          />
        )}
      </Box>
    );
  }

  // View mode
  return (
    <Box
      onClick={() => startEditing()}
      onDoubleClick={() => startEditing()}
      onKeyDown={handleKeyDown}
      tabIndex={0}
      sx={{
        height: '100%',
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        padding: '0 8px',
        cursor: 'text',
        backgroundColor: getBackgroundColor(),
        opacity: isDeleted ? DELETED_CELL_STYLES.opacity : 1,
        textDecoration: isDeleted ? DELETED_CELL_STYLES.textDecoration : 'none',
        '&:hover': {
          backgroundColor: isEdited ? CELL_COLORS.EDITED : 'rgba(0, 0, 0, 0.04)',
        },
        '&:focus': {
          outline: '2px solid rgb(77, 208, 225)',
          outlineOffset: '-2px',
        },
      }}>
      <span style={{overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>
        {isJsonList ? JSON.stringify(value) : String(value ?? '')}
      </span>
    </Box>
  );
}; 