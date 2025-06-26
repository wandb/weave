import {Box} from '@mui/material';
import {GridRenderCellParams} from '@mui/x-data-grid-pro';
import {Icon} from '@wandb/weave/components/Icon';
import React, {useCallback, useEffect, useRef, useState} from 'react';

import {CellValue} from '../../Browse2/CellValue';
import {isRefPrefixedString} from '../filters/common';
import {CELL_COLORS, CellTooltip, DELETED_CELL_STYLES} from './CellRenderers';
import {useDatasetEditContext} from './DatasetEditorContext';

interface InlineCellProps extends GridRenderCellParams {
  isEdited?: boolean;
  isDeleted?: boolean;
  isNew?: boolean;
  serverValue?: any;
  disableNewRowHighlight?: boolean;
  preserveFieldOrder?: (row: any) => any;
  onCellEditStart?: (params: {id: string; field: string}) => void;
  onCellEditStop?: () => void;
  isLastCell?: boolean;
  onTabAtEnd?: () => void;
  rowHasContent?: boolean;
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
  isLastCell,
  onTabAtEnd,
  rowHasContent = true,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editedValue, setEditedValue] = useState(value);
  const {updateCellValue} = useDatasetEditContext();
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement>(null);
  const [startedWithChar, setStartedWithChar] = useState(false);
  const [appendedContent, setAppendedContent] = useState(false);
  const [lastCursorPosition, setLastCursorPosition] = useState<number | null>(
    null
  );

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
      setStartedWithChar(false);
      setAppendedContent(false);
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
    [
      isEditing,
      editedValue,
      value,
      isJsonList,
      handleUpdateValue,
      onCellEditStop,
    ]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      // Don't handle keys if an input/textarea is focused (they should handle their own keys)
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      if (!isEditing && (e.key === 'Enter' || e.key === 'F2')) {
        e.preventDefault();
        e.stopPropagation();
        startEditing();
        return;
      }

      // Start editing immediately if a printable character is typed
      if (
        !isEditing &&
        isEditable &&
        e.key.length === 1 &&
        !e.ctrlKey &&
        !e.metaKey &&
        !e.altKey
      ) {
        e.preventDefault();
        e.stopPropagation();

        // For numbers, start with the typed digit
        if (typeof value === 'number' && /^\d$/.test(e.key)) {
          setEditedValue(Number(e.key));
          setAppendedContent(false);
        } else if (
          typeof value === 'number' &&
          (e.key === '-' || e.key === '.')
        ) {
          // Allow starting with negative or decimal for numbers
          setEditedValue(e.key === '-' ? '-' : '0.');
          setAppendedContent(false);
        } else if (typeof value !== 'number') {
          // For text values, handle space specially to append instead of replace
          if (e.key === ' ' && typeof value === 'string') {
            setEditedValue(value + ' ');
            setAppendedContent(true);
          } else {
            // Replace content with the typed character
            setEditedValue(e.key);
            setAppendedContent(false);
          }
        }

        setIsEditing(true);
        setStartedWithChar(true);
        onCellEditStart?.({id: id as string, field});

        // Focus will be set by the useEffect
        return;
      }

      // Handle Delete or Backspace to clear cell when not editing
      if (
        !isEditing &&
        isEditable &&
        (e.key === 'Delete' || e.key === 'Backspace')
      ) {
        e.preventDefault();
        e.stopPropagation();

        // Clear the cell value
        if (typeof value === 'number') {
          handleUpdateValue(0);
        } else if (isJsonList) {
          handleUpdateValue([]);
        } else {
          handleUpdateValue('');
        }
        return;
      }
    },
    [
      isEditing,
      isEditable,
      value,
      handleUpdateValue,
      startEditing,
      isJsonList,
      onCellEditStart,
      id,
      field,
    ]
  );

  // Separate handler for edit mode - only intercept specific keys
  const handleEditKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      switch (e.key) {
        case 'Enter':
          // For multiline content, Enter adds newlines, Ctrl/Cmd+Enter saves
          const isMultilineContent =
            isJsonList ||
            (typeof editedValue === 'string' &&
              (editedValue.includes('\n') || editedValue.length > 50));

          if (isMultilineContent && !e.ctrlKey && !e.metaKey) {
            // Let the default behavior happen (add newline)
            return;
          }

          // Save on Enter for single-line, or Ctrl/Cmd+Enter for multiline
          e.preventDefault();
          e.stopPropagation();
          stopEditing(true);

          // Move to next row only for single-line content
          if (!isMultilineContent) {
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
          // Check if we're at the last cell and Tab was pressed (not Shift+Tab)
          if (isLastCell && !e.shiftKey && onTabAtEnd) {
            onTabAtEnd();
          }
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
          // Only navigate cells if modifier keys are pressed
          if (e.shiftKey || e.ctrlKey || e.metaKey) {
            e.preventDefault();
            e.stopPropagation();
            stopEditing(true);

            // Navigate to the appropriate cell
            const rowIds = api?.getAllRowIds() || [];
            const currentRowIndex = rowIds.indexOf(id as string);
            const columns = api?.getAllColumns() || [];
            const currentColIndex = columns.findIndex(
              col => col.field === field
            );

            if (currentRowIndex !== -1 && currentColIndex !== -1) {
              let newRowIndex = currentRowIndex;
              let newColIndex = currentColIndex;

              switch (e.key) {
                case 'ArrowUp':
                  newRowIndex = Math.max(0, currentRowIndex - 1);
                  break;
                case 'ArrowDown':
                  newRowIndex = Math.min(
                    rowIds.length - 1,
                    currentRowIndex + 1
                  );
                  break;
                case 'ArrowLeft':
                  newColIndex = Math.max(0, currentColIndex - 1);
                  break;
                case 'ArrowRight':
                  newColIndex = Math.min(
                    columns.length - 1,
                    currentColIndex + 1
                  );
                  break;
              }

              if (rowIds[newRowIndex] && columns[newColIndex]) {
                api?.setCellFocus(
                  rowIds[newRowIndex],
                  columns[newColIndex].field
                );
              }
            }
          }
          // Let arrow keys work normally for text navigation when no modifiers
          break;
        // Don't handle any other keys - let them work normally
      }
    },
    [
      editedValue,
      isJsonList,
      stopEditing,
      api,
      id,
      field,
      isLastCell,
      onTabAtEnd,
    ]
  );

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      // Place cursor at end, or after first character if we started by typing
      if ('setSelectionRange' in inputRef.current) {
        if (startedWithChar && !appendedContent) {
          // Put cursor after the first character when we replaced content
          inputRef.current.setSelectionRange(1, 1);
          setStartedWithChar(false);
          setAppendedContent(false);
        } else if (lastCursorPosition !== null) {
          // Restore cursor position when switching between input types
          const pos = Math.min(
            lastCursorPosition,
            inputRef.current.value.length
          );
          inputRef.current.setSelectionRange(pos, pos);
          setLastCursorPosition(null);
        } else {
          // Put cursor at end when appending or normal editing
          const length = inputRef.current.value.length;
          inputRef.current.setSelectionRange(length, length);
          setStartedWithChar(false);
          setAppendedContent(false);
        }
      }
    }
  }, [isEditing, startedWithChar, appendedContent, lastCursorPosition]);

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
          onKeyDown={e => {
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
            textDecoration: isDeleted
              ? DELETED_CELL_STYLES.textDecoration
              : 'none',
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
          textDecoration: isDeleted
            ? DELETED_CELL_STYLES.textDecoration
            : 'none',
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
    // Switch to multiline for JSON, existing newlines, or long text
    const isMultiline =
      isJsonList ||
      (typeof editedValue === 'string' &&
        (editedValue.includes('\n') || editedValue.length > 50));

    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          height: '100%',
          width: '100%',
          border: '2px solid rgb(77, 208, 225)',
          backgroundColor: 'rgba(77, 208, 225, 0.1)',
          position: 'relative',
        }}>
        {isMultiline ? (
          <>
            <textarea
              ref={inputRef as React.RefObject<HTMLTextAreaElement>}
              value={
                isJsonList
                  ? JSON.stringify(editedValue, null, 2)
                  : String(editedValue)
              }
              onChange={e => {
                setEditedValue(isJsonList ? e.target.value : e.target.value);
                // Track cursor position for smooth transitions
                setLastCursorPosition(e.target.selectionStart);
              }}
              onKeyDown={handleEditKeyDown}
              onBlur={() => stopEditing(true)}
              style={{
                width: '100%',
                height: '100%',
                border: 'none',
                outline: 'none',
                background: 'none',
                padding: '4px 8px',
                fontFamily: isJsonList ? 'monospace' : 'inherit',
                fontSize: isJsonList ? '12px' : 'inherit',
                resize: 'none',
                lineHeight: '1.5',
              }}
              placeholder={isJsonList ? 'Enter JSON array...' : 'Enter text...'}
            />
            <CellTooltip
              title="Enter for new line, Ctrl+Enter to save"
              placement="top">
              <Box
                sx={{
                  position: 'absolute',
                  bottom: 2,
                  right: 4,
                  opacity: 0.5,
                  fontSize: '10px',
                  color: 'text.secondary',
                  pointerEvents: 'none',
                  backgroundColor: 'rgba(255, 255, 255, 0.8)',
                  padding: '0 2px',
                  borderRadius: '2px',
                }}>
                ⌃↵
              </Box>
            </CellTooltip>
          </>
        ) : (
          <input
            ref={inputRef as React.RefObject<HTMLInputElement>}
            type={isNumber ? 'number' : 'text'}
            value={String(editedValue)}
            onChange={e => {
              setEditedValue(
                isNumber ? Number(e.target.value) : e.target.value
              );
              // Track cursor position for smooth transitions
              if (!isNumber) {
                setLastCursorPosition(e.target.selectionStart);
              }
            }}
            onKeyDown={handleEditKeyDown}
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
            placeholder={isNumber ? 'Enter number...' : 'Enter text...'}
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
          backgroundColor: isEdited
            ? CELL_COLORS.EDITED
            : 'rgba(0, 0, 0, 0.04)',
        },
        '&:focus': {
          outline: '2px solid rgb(77, 208, 225)',
          outlineOffset: '-2px',
        },
      }}>
      <span
        style={{
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}>
        {isJsonList ? JSON.stringify(value) : String(value ?? '')}
      </span>
      {isLastCell && onTabAtEnd && rowHasContent && (
        <CellTooltip title="Press Tab to add a new row" placement="left">
          <Box
            sx={{
              marginLeft: 'auto',
              paddingLeft: '4px',
              opacity: 0.5,
              fontSize: '10px',
              color: 'text.secondary',
            }}>
            Tab →
          </Box>
        </CellTooltip>
      )}
    </Box>
  );
};
