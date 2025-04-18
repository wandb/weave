import {Box, Tooltip} from '@mui/material';
import {
  GridRenderCellParams,
  GridRenderEditCellParams,
} from '@mui/x-data-grid-pro';
import {Button} from '@wandb/weave/components/Button';
import {Icon} from '@wandb/weave/components/Icon';
import set from 'lodash/set';
import React, {useCallback, useState} from 'react';

import {CellValue} from '../../Browse2/CellValue';
import {isRefPrefixedString} from '../filters/common';
import {DatasetRow, useDatasetEditContext} from './DatasetEditorContext';
import {CodeEditor} from './editors/CodeEditor';
import {DiffEditor} from './editors/DiffEditor';
import {TextEditor} from './editors/TextEditor';
import {EditorMode, EditPopover} from './EditPopover';

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

interface CellViewingRendererProps {
  isEdited?: boolean;
  isDeleted?: boolean;
  isNew?: boolean;
  isEditing?: boolean;
  serverValue?: any;
  disableNewRowHighlight?: boolean;
}

export const CellViewingRenderer: React.FC<
  GridRenderCellParams & CellViewingRendererProps
> = ({
  value,
  isEdited = false,
  isDeleted = false,
  isNew = false,
  isEditing = false,
  api,
  id,
  field,
  serverValue,
  disableNewRowHighlight = false,
}) => {
  const [isHovered, setIsHovered] = useState(false);
  const {setEditedRows, setAddedRows, setFieldEdited} = useDatasetEditContext();

  const isWeaveUrl = isRefPrefixedString(value);
  const isEditable =
    !isWeaveUrl &&
    (typeof value !== 'object' || Array.isArray(value)) &&
    typeof value !== 'boolean';

  const handleEditClick = (event: React.MouseEvent) => {
    event.stopPropagation();
    if (isEditable) {
      api.startCellEditMode({id, field});
    }
  };

  const handleRevert = (event: React.MouseEvent) => {
    event.stopPropagation();
    const existingRow = api.getRow(id);
    const updatedRow = {...existingRow};

    set(updatedRow, field, serverValue);
    api.updateRows([{id, ...updatedRow}]);
    api.setEditCellValue({id, field, value: serverValue});
    setEditedRows(prev => {
      const newMap = new Map(prev);
      newMap.set(existingRow.___weave?.index, updatedRow);
      return newMap;
    });
    if (existingRow.___weave?.index !== undefined) {
      setFieldEdited(existingRow.___weave.index, field, false);
    }
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

  // Format array display for better readability
  const formatArrayForDisplay = (arr: any[]) => {
    if (arr.length <= 3) {
      return JSON.stringify(arr);
    }
    return `[${arr
      .slice(0, 3)
      .map(item => (typeof item === 'string' ? `"${item}"` : item))
      .join(', ')}, ... (${arr.length} items)]`;
  };

  if (typeof value === 'boolean') {
    const handleToggle = (e: React.MouseEvent) => {
      e.stopPropagation();
      e.preventDefault();
      const existingRow = api.getRow(id);
      const updatedRow = {...existingRow, [field]: !value};
      api.updateRows([{id, ...updatedRow}]);
      const rowToUpdate = {...updatedRow};

      if (existingRow.___weave?.isNew) {
        setAddedRows(prev => {
          const newMap = new Map(prev);
          newMap.set(existingRow.___weave?.id, rowToUpdate);
          return newMap;
        });
      } else {
        if (!rowToUpdate.___weave.editedFields) {
          rowToUpdate.___weave.editedFields = new Set<string>();
        }
        rowToUpdate.___weave.editedFields.add(field);
        setEditedRows(prev => {
          const newMap = new Map(prev);
          newMap.set(existingRow.___weave?.index, rowToUpdate);
          return newMap;
        });
      }
    };

    return (
      <Tooltip
        title="Click to toggle"
        enterDelay={1000}
        enterNextDelay={1000}
        leaveDelay={0}
        placement="top"
        slotProps={{
          tooltip: {
            sx: {
              fontFamily: '"Source Sans Pro", sans-serif',
              fontSize: '14px',
            },
          },
        }}>
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
      </Tooltip>
    );
  }

  if (!isEditable) {
    return (
      <Tooltip
        title="Cell type cannot be edited"
        enterDelay={1000}
        enterNextDelay={1000}
        leaveDelay={0}
        placement="top"
        slotProps={{
          tooltip: {
            sx: {
              fontFamily: '"Source Sans Pro", sans-serif',
              fontSize: '14px',
            },
          },
        }}>
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
          onFocus={e => e.target.blur()}
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
          <CellValue value={value} noLink={true} />
        </Box>
      </Tooltip>
    );
  }

  return (
    <Tooltip
      title="Click to edit"
      enterDelay={1000}
      enterNextDelay={1000}
      leaveDelay={0}
      placement="top"
      slotProps={{
        tooltip: {
          sx: {
            fontFamily: '"Source Sans Pro", sans-serif',
            fontSize: '14px',
          },
        },
      }}>
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
          ...(isEditing && {
            border: '2px solid rgb(77, 208, 225)',
            backgroundColor: 'rgba(77, 208, 225, 0.2)',
          }),
        }}>
        <span style={{flex: 1, position: 'relative', overflow: 'hidden'}}>
          {Array.isArray(value) ? formatArrayForDisplay(value) : value}
          {isEditing}
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
    </Tooltip>
  );
};

export interface CellEditingRendererProps extends GridRenderEditCellParams {
  serverValue?: string;
  preserveFieldOrder?: (row: any) => any;
}

const NumberEditor: React.FC<{
  value: number;
  onClose: () => void;
  api: any;
  id: string | number;
  field: string;
  serverValue?: any;
}> = ({value, onClose, api, id, field, serverValue}) => {
  const [inputValue, setInputValue] = useState(value.toString());
  const {setEditedRows, setAddedRows, setFieldEdited} = useDatasetEditContext();

  const handleValueUpdate = (newValue: string) => {
    setInputValue(newValue);
    if (newValue !== '') {
      const numValue = Number(newValue);
      api.setEditCellValue({id, field, value: numValue});
    }
  };

  const handleBlur = () => {
    if (inputValue !== '') {
      const numValue = Number(inputValue);
      const existingRow = api.getRow(id);
      const isValueChanged = numValue !== serverValue;

      if (existingRow.___weave?.isNew) {
        setAddedRows((prev: Map<string, DatasetRow>) => {
          const newMap = new Map(prev);
          const updatedRow = {...existingRow};
          updatedRow[field] = numValue;
          newMap.set(existingRow.___weave?.id, updatedRow);
          return newMap;
        });
      } else {
        const updatedRow = {...existingRow};
        updatedRow[field] = numValue;
        setEditedRows((prev: Map<number, DatasetRow>) => {
          const newMap = new Map(prev);
          newMap.set(existingRow.___weave?.index, updatedRow);
          return newMap;
        });
        if (isValueChanged && existingRow.___weave?.index !== undefined) {
          setFieldEdited(existingRow.___weave.index, field, isValueChanged);
        }
      }
    }
    onClose();
  };

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
        value={inputValue}
        onChange={e => handleValueUpdate(e.target.value)}
        onKeyDown={e => {
          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
            handleBlur();
          } else if (e.key === 'Enter') {
            handleBlur();
          }
        }}
        onBlur={handleBlur}
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
};

const ArrayEditor: React.FC<{
  value: any[];
  serverValue?: any[];
  onClose: () => void;
  params: GridRenderCellParams;
}> = ({value, serverValue, onClose, params}) => {
  const [anchorEl, setAnchorEl] = useState<HTMLDivElement | null>(null);
  const initialWidth = React.useRef<number>();
  const initialHeight = React.useRef<number>();
  const [editorMode, setEditorMode] = useState<EditorMode>('code');
  const [editedValue, setEditedValue] = useState(
    JSON.stringify(value, null, 2)
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const parsedValueRef = React.useRef<any[]>(value);
  const debounceTimerRef = React.useRef<NodeJS.Timeout | null>(null);
  const {setEditedRows, setAddedRows, setFieldEdited} = useDatasetEditContext();

  const handleEditorModeChange = (newMode: EditorMode) => {
    setEditorMode(newMode);
    initialWidth.current = getPopoverWidth(newMode);
    initialHeight.current = getPopoverHeight();
  };

  const validateAndUpdateValue = (newJsonString: string) => {
    try {
      const parsed = JSON.parse(newJsonString);
      if (!Array.isArray(parsed)) {
        setErrorMessage('Value must be a valid JSON array');
        return false;
      }
      setErrorMessage(null);
      setEditedValue(newJsonString);
      parsedValueRef.current = parsed;
      params.api.setEditCellValue({
        id: params.id,
        field: params.field,
        value: parsed,
      });
      return true;
    } catch (e) {
      setErrorMessage((e as Error).message);
      setEditedValue(newJsonString);
      return false;
    }
  };

  // Debounced validation for error display only
  const debouncedValidateErrors = (newValue: string) => {
    // Clear any existing timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    // Set a new timer for error validation only
    debounceTimerRef.current = setTimeout(() => {
      try {
        const parsed = JSON.parse(newValue);
        if (!Array.isArray(parsed)) {
          setErrorMessage('Value must be a valid JSON array');
        } else {
          setErrorMessage(null);
        }
      } catch (e) {
        setErrorMessage((e as Error).message);
      }
      debounceTimerRef.current = null;
    }, 1000); // 1000ms = 1 second
  };

  const handleValueChange = (newValue: string) => {
    // Always update the displayed value immediately
    setEditedValue(newValue);

    // Try to persist valid JSON immediately without waiting for debounce
    try {
      const parsed = JSON.parse(newValue);
      if (Array.isArray(parsed)) {
        // Immediately update the parsed value reference and the grid
        parsedValueRef.current = parsed;
        params.api.setEditCellValue({
          id: params.id,
          field: params.field,
          value: parsed,
        });
        // Clear any error since we have valid JSON
        setErrorMessage(null);
      }
    } catch (e) {
      // Don't update error message immediately - let the debounced validation handle it
    }

    // Debounce the error validation to avoid showing errors while typing
    debouncedValidateErrors(newValue);
  };

  // Clean up the timer on unmount
  React.useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  // Force validation before closing
  const validateBeforeClose = () => {
    // Clear any pending debounce timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = null;
    }
    // Perform immediate validation
    return validateAndUpdateValue(editedValue);
  };

  const getPopoverWidth = useCallback(
    (mode: EditorMode = editorMode) => {
      const screenWidth = window.innerWidth;
      const maxWidth = screenWidth - 48;
      const minWidth = 400;
      const jsonString = JSON.stringify(value);
      const valueLength = jsonString ? jsonString.length : 0;
      const approximateWidth = Math.min(
        Math.max(valueLength, minWidth),
        maxWidth
      );
      return mode === 'diff'
        ? Math.min(approximateWidth * 2, maxWidth)
        : approximateWidth;
    },
    [editorMode, value]
  );

  const getPopoverHeight = useCallback(() => {
    const width = getPopoverWidth();
    const charsPerLine = Math.floor(width / 8);
    const jsonString = JSON.stringify(value, null, 2);
    const lines = jsonString.split('\n').reduce((acc, line) => {
      return acc + Math.ceil(line.length / charsPerLine);
    }, 0);

    const maxHeight = Math.min(window.innerHeight / 2, 400);
    const contentHeight = Math.min(Math.max(lines * 24 + 80, 120), maxHeight);
    return contentHeight;
  }, [value, getPopoverWidth]);

  React.useLayoutEffect(() => {
    const element = document.activeElement?.closest('.MuiDataGrid-cell');
    if (element) {
      setAnchorEl(element as HTMLDivElement);
      if (!initialWidth.current) {
        initialWidth.current = getPopoverWidth();
      }
      if (!initialHeight.current) {
        initialHeight.current = getPopoverHeight();
      }
    }
  }, [getPopoverWidth, getPopoverHeight]);

  const handlePopoverClose = () => {
    try {
      // Always try to use the latest parsed value
      if (parsedValueRef.current) {
        // Get the existing row and update it
        const existingRow = params.api.getRow(params.id);
        const updatedRow = {...existingRow};
        updatedRow[params.field] = parsedValueRef.current;

        // Update the grid first with the new row data
        params.api.updateRows([{id: params.id, ...updatedRow}]);

        // Set the edit cell value to ensure the new value is in the edit buffer
        params.api.setEditCellValue({
          id: params.id,
          field: params.field,
          value: parsedValueRef.current,
        });

        // Now gracefully stop editing to commit the changes
        params.api.stopCellEditMode({
          id: params.id,
          field: params.field,
        });

        // Handle differently based on whether this is a new row or an edited row
        if (existingRow.___weave?.isNew) {
          setAddedRows(prev => {
            const newMap = new Map(prev);
            newMap.set(existingRow.___weave?.id, updatedRow);
            return newMap;
          });
        } else {
          // Mark the field as edited if it's different from the server value
          const isValueChanged =
            JSON.stringify(parsedValueRef.current) !==
            JSON.stringify(serverValue);

          if (isValueChanged && !updatedRow.___weave.editedFields) {
            updatedRow.___weave.editedFields = new Set<string>();
          }

          if (isValueChanged) {
            updatedRow.___weave.editedFields.add(params.field);

            // Use setFieldEdited for better tracking
            if (existingRow.___weave?.index !== undefined) {
              setFieldEdited(existingRow.___weave.index, params.field, true);
            }
          }

          setEditedRows(prev => {
            const newMap = new Map(prev);

            if (!isValueChanged || !updatedRow.___weave.editedFields?.size) {
              newMap.delete(existingRow.___weave?.index);
            } else {
              newMap.set(existingRow.___weave?.index, updatedRow);
            }

            return newMap;
          });
        }

        onClose();
      } else {
        // If we don't have a valid parsed value, force validation now
        if (validateBeforeClose()) {
          const parsedValue = JSON.parse(editedValue);

          // Get the existing row and update it
          const existingRow = params.api.getRow(params.id);
          const updatedRow = {...existingRow};
          updatedRow[params.field] = parsedValue;

          // Update the grid with the complete row data first
          params.api.updateRows([{id: params.id, ...updatedRow}]);

          // Set the edit cell value to ensure it's in the edit buffer
          params.api.setEditCellValue({
            id: params.id,
            field: params.field,
            value: parsedValue,
          });

          // Now stop edit mode to commit the changes
          params.api.stopCellEditMode({
            id: params.id,
            field: params.field,
          });

          if (existingRow.___weave?.isNew) {
            setAddedRows(prev => {
              const newMap = new Map(prev);
              newMap.set(existingRow.___weave?.id, updatedRow);
              return newMap;
            });
          } else {
            const isValueChanged =
              JSON.stringify(parsedValue) !== JSON.stringify(serverValue);

            if (isValueChanged && !updatedRow.___weave.editedFields) {
              updatedRow.___weave.editedFields = new Set<string>();
            }

            if (isValueChanged) {
              updatedRow.___weave.editedFields.add(params.field);

              // Use setFieldEdited for better tracking
              if (existingRow.___weave?.index !== undefined) {
                setFieldEdited(existingRow.___weave.index, params.field, true);
              }
            }

            setEditedRows(prev => {
              const newMap = new Map(prev);

              if (!isValueChanged || !updatedRow.___weave.editedFields?.size) {
                newMap.delete(existingRow.___weave?.index);
              } else {
                newMap.set(existingRow.___weave?.index, updatedRow);
              }

              return newMap;
            });
          }

          onClose();
        }
      }
    } catch (e) {
      // If any unexpected error, update error message
      setErrorMessage((e as Error).message);
    }
  };

  const renderEditor = () => {
    switch (editorMode) {
      case 'code':
        return (
          <div
            style={{display: 'flex', flexDirection: 'column', height: '100%'}}>
            <CodeEditor
              value={editedValue}
              onChange={handleValueChange}
              onClose={handlePopoverClose}
            />
          </div>
        );
      case 'diff':
        const originalValueString = Array.isArray(serverValue)
          ? JSON.stringify(serverValue, null, 2)
          : '[]';

        return (
          <div
            style={{display: 'flex', flexDirection: 'column', height: '100%'}}>
            <DiffEditor
              value={editedValue}
              originalValue={originalValueString}
              onChange={handleValueChange}
              onClose={handlePopoverClose}
            />
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <>
      <CellViewingRenderer {...params} isEditing />
      <EditPopover
        anchorEl={anchorEl}
        onClose={handlePopoverClose}
        initialWidth={initialWidth.current}
        initialHeight={initialHeight.current}
        editorMode={editorMode}
        setEditorMode={handleEditorModeChange}
        allowedModes={['code', 'diff'] as EditorMode[]}
        errorMessage={errorMessage}>
        {renderEditor()}
      </EditPopover>
    </>
  );
};

const StringEditor: React.FC<{
  value: string;
  serverValue?: string;
  onClose: () => void;
  params: GridRenderCellParams;
}> = ({value, serverValue, onClose, params}) => {
  const inputRef = React.useRef<HTMLTextAreaElement>(null);
  const [anchorEl, setAnchorEl] = useState<HTMLDivElement | null>(null);
  const [hasInitialFocus, setHasInitialFocus] = useState(false);
  const initialWidth = React.useRef<number>();
  const initialHeight = React.useRef<number>();
  const [editorMode, setEditorMode] = useState<EditorMode>('text');
  const [editedValue, setEditedValue] = useState(value);

  const handleEditorModeChange = (newMode: EditorMode) => {
    setEditorMode(newMode);
    initialWidth.current = getPopoverWidth(newMode);
    initialHeight.current = getPopoverHeight();
  };

  const handleValueChange = (newValue: string) => {
    setEditedValue(newValue);
    params.api.setEditCellValue({
      id: params.id,
      field: params.field,
      value: newValue,
    });
  };

  const getPopoverWidth = useCallback(
    (mode: EditorMode = editorMode) => {
      const screenWidth = window.innerWidth;
      const maxWidth = screenWidth - 48;
      const minWidth = 400;
      const valueLength = typeof value === 'string' ? value.length : 0;
      const approximateWidth = Math.min(
        Math.max(valueLength, minWidth),
        maxWidth
      );
      return mode === 'diff'
        ? Math.min(approximateWidth * 2, maxWidth)
        : approximateWidth;
    },
    [editorMode, value]
  );

  const getPopoverHeight = useCallback(() => {
    const width = getPopoverWidth();
    const charsPerLine = Math.floor(width / 8);
    const lines =
      typeof value === 'string'
        ? value.split('\n').reduce((acc, line) => {
            return acc + Math.ceil(line.length / charsPerLine);
          }, 0)
        : 1;

    const maxHeight = Math.min(window.innerHeight / 2, 400);
    const contentHeight = Math.min(Math.max(lines * 24 + 80, 120), maxHeight);
    return contentHeight;
  }, [value, getPopoverWidth]);

  React.useLayoutEffect(() => {
    const element = document.activeElement?.closest('.MuiDataGrid-cell');
    if (element) {
      setAnchorEl(element as HTMLDivElement);
      if (!initialWidth.current) {
        initialWidth.current = getPopoverWidth();
      }
      if (!initialHeight.current) {
        initialHeight.current = getPopoverHeight();
      }
    }
  }, [getPopoverWidth, getPopoverHeight]);

  React.useEffect(() => {
    if (!hasInitialFocus) {
      setTimeout(() => {
        const textarea = inputRef.current?.querySelector('textarea');
        if (textarea) {
          textarea.focus();
          textarea.setSelectionRange(0, textarea.value.length);
          setHasInitialFocus(true);
        }
      }, 0);
    }
  }, [hasInitialFocus]);

  const renderEditor = () => {
    switch (editorMode) {
      case 'text':
        return (
          <TextEditor
            value={editedValue}
            onChange={handleValueChange}
            onClose={() => {
              // For string editor, make sure changes are applied immediately when closing
              const currentValue = params.api.getCellValue(
                params.id,
                params.field
              );
              const existingRow = params.api.getRow(params.id);
              const updatedRow = {...existingRow, [params.field]: currentValue};

              // First update the row in the grid
              params.api.updateRows([{id: params.id, ...updatedRow}]);

              // Then stop editing mode
              onClose();
            }}
            inputRef={inputRef}
          />
        );
      case 'code':
        return (
          <CodeEditor
            value={editedValue}
            onChange={handleValueChange}
            onClose={() => {
              // For string editor, make sure changes are applied immediately when closing
              const currentValue = params.api.getCellValue(
                params.id,
                params.field
              );
              const existingRow = params.api.getRow(params.id);
              const updatedRow = {...existingRow, [params.field]: currentValue};

              // First update the row in the grid
              params.api.updateRows([{id: params.id, ...updatedRow}]);

              // Then stop editing mode
              onClose();
            }}
          />
        );
      case 'diff':
        return (
          <DiffEditor
            value={editedValue}
            originalValue={serverValue ?? ''}
            onChange={handleValueChange}
            onClose={() => {
              // For string editor, make sure changes are applied immediately when closing
              const currentValue = params.api.getCellValue(
                params.id,
                params.field
              );
              const existingRow = params.api.getRow(params.id);
              const updatedRow = {...existingRow, [params.field]: currentValue};

              // First update the row in the grid
              params.api.updateRows([{id: params.id, ...updatedRow}]);

              // Then stop editing mode
              onClose();
            }}
          />
        );
    }
  };

  return (
    <>
      <CellViewingRenderer {...params} isEditing />
      <EditPopover
        anchorEl={anchorEl}
        onClose={() => {
          // For string editor, make sure changes are applied immediately when closing
          const currentValue = params.api.getCellValue(params.id, params.field);
          const existingRow = params.api.getRow(params.id);
          const updatedRow = {...existingRow, [params.field]: currentValue};

          // First update the row in the grid
          params.api.updateRows([{id: params.id, ...updatedRow}]);

          // Then stop editing mode
          onClose();
        }}
        initialWidth={initialWidth.current}
        initialHeight={initialHeight.current}
        editorMode={editorMode}
        setEditorMode={handleEditorModeChange}>
        {renderEditor()}
      </EditPopover>
    </>
  );
};

export const CellEditingRenderer: React.FC<
  CellEditingRendererProps
> = props => {
  const {setEditedRows, setAddedRows} = useDatasetEditContext();
  const {id, value, field, api, serverValue, preserveFieldOrder} = props;

  // Convert edit params to render params
  const renderParams: GridRenderCellParams = {
    ...props,
    value,
  };

  const updateRow = useCallback(
    (existingRow: any, newValue: any) => {
      const baseRow = {...existingRow};
      baseRow[field] = newValue;
      return preserveFieldOrder ? preserveFieldOrder(baseRow) : baseRow;
    },
    [field, preserveFieldOrder]
  );

  // For boolean values, don't show edit mode at all
  if (typeof value === 'boolean') {
    return null;
  }

  // For numeric values, show number editor
  if (typeof value === 'number') {
    return (
      <NumberEditor
        value={value}
        onClose={() => api.stopCellEditMode({id, field})}
        api={api}
        id={id}
        field={field}
        serverValue={serverValue}
      />
    );
  }

  // For array values, show array editor
  if (Array.isArray(value)) {
    return (
      <ArrayEditor
        value={value}
        serverValue={Array.isArray(serverValue) ? serverValue : undefined}
        onClose={() => {
          const existingRow = api.getRow(id);
          const currentValue = api.getCellValue(id, field);
          const updatedRow = updateRow(existingRow, currentValue);

          const isValueChanged =
            JSON.stringify(currentValue) !== JSON.stringify(serverValue);
          const rowToUpdate = {...updatedRow};

          if (existingRow.___weave?.isNew) {
            // For added rows, ensure we properly update the entire row
            setAddedRows(prev => {
              const newMap = new Map(prev);
              // Make sure the field gets updated with the current array value
              const updatedAddedRow = {...rowToUpdate};
              updatedAddedRow[field] = currentValue;
              newMap.set(existingRow.___weave?.id, updatedAddedRow);
              return newMap;
            });
          } else {
            if (!rowToUpdate.___weave.editedFields) {
              rowToUpdate.___weave.editedFields = new Set<string>();
            }

            if (isValueChanged) {
              rowToUpdate.___weave.editedFields.add(field);
            } else {
              rowToUpdate.___weave.editedFields.delete(field);
            }

            setEditedRows(prev => {
              const newMap = new Map(prev);

              if (rowToUpdate.___weave.editedFields.size === 0) {
                newMap.delete(existingRow.___weave?.index);
              } else {
                newMap.set(existingRow.___weave?.index, rowToUpdate);
              }

              return newMap;
            });
          }
          api.stopCellEditMode({id, field});
        }}
        params={renderParams}
      />
    );
  }

  // Text editor with popover for string values
  return (
    <StringEditor
      value={value as string}
      serverValue={serverValue}
      onClose={() => {
        const existingRow = api.getRow(id);
        const updatedRow = updateRow(existingRow, value);

        const isValueChanged = value !== serverValue;
        const rowToUpdate = {...updatedRow};

        if (existingRow.___weave?.isNew) {
          setAddedRows(prev => {
            const newMap = new Map(prev);
            newMap.set(existingRow.___weave?.id, rowToUpdate);
            return newMap;
          });
        } else {
          if (!rowToUpdate.___weave.editedFields) {
            rowToUpdate.___weave.editedFields = new Set<string>();
          }

          if (isValueChanged) {
            rowToUpdate.___weave.editedFields.add(field);
          } else {
            rowToUpdate.___weave.editedFields.delete(field);
          }

          setEditedRows(prev => {
            const newMap = new Map(prev);

            // If we don't have any edited fields and it's not a new row,
            // don't add it to the editedRows map
            if (rowToUpdate.___weave.editedFields.size === 0) {
              newMap.delete(existingRow.___weave?.index);
            } else {
              newMap.set(existingRow.___weave?.index, rowToUpdate);
            }

            return newMap;
          });
        }
        api.stopCellEditMode({id, field});
      }}
      params={renderParams}
    />
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
