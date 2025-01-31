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
  fontFamily: '"Source Sans Pro", sans-serif',
  fontSize: '14px',
  lineHeight: '1.5',
  padding: '8px 12px',
  display: 'flex',
  alignItems: 'center',
  transition: 'background-color 0.2s ease',
};

interface CellViewingRendererProps {
  isEdited?: boolean;
  isDeleted?: boolean;
  isNew?: boolean;
  isEditing?: boolean;
  serverValue?: any;
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
}) => {
  const [isHovered, setIsHovered] = useState(false);
  const {setEditedRows} = useDatasetEditContext();

  const isEditable = typeof value !== 'object' && typeof value !== 'boolean';

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
  };

  const getBackgroundColor = () => {
    if (isDeleted) {
      return CELL_COLORS.DELETED;
    }
    if (isEdited) {
      return CELL_COLORS.EDITED;
    }
    if (isNew) {
      return CELL_COLORS.NEW;
    }
    return CELL_COLORS.TRANSPARENT;
  };

  if (typeof value === 'boolean') {
    const handleToggle = (e: React.MouseEvent) => {
      e.stopPropagation();
      e.preventDefault();
      const existingRow = api.getRow(id);
      const updatedRow = {...existingRow, [field]: !value};
      api.updateRows([{id, ...updatedRow}]);
      setEditedRows(prev => {
        const newMap = new Map(prev);
        newMap.set(existingRow.___weave?.index, updatedRow);
        return newMap;
      });
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
            }
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
          onClick={e => e.stopPropagation()}
          onDoubleClick={e => e.stopPropagation()}
          sx={{
            backgroundColor: getBackgroundColor(),
            opacity: isDeleted ? DELETED_CELL_STYLES.opacity : 1,
            textDecoration: isDeleted
              ? DELETED_CELL_STYLES.textDecoration
              : 'none',
          }}>
          <CellValue value={value} />
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
          {value}
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
}> = ({value, onClose, api, id, field}) => {
  const [inputValue, setInputValue] = useState(value.toString());
  const {setEditedRows, setAddedRows} = useDatasetEditContext();

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
            onClose={onClose}
            inputRef={inputRef}
          />
        );
      case 'code':
        return (
          <CodeEditor
            value={editedValue}
            onChange={handleValueChange}
            onClose={onClose}
          />
        );
      case 'diff':
        return (
          <DiffEditor
            value={editedValue}
            originalValue={serverValue ?? ''}
            onChange={handleValueChange}
            onClose={onClose}
          />
        );
    }
  };

  return (
    <>
      <CellViewingRenderer {...params} isEditing />
      <EditPopover
        anchorEl={anchorEl}
        onClose={onClose}
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
> = params => {
  const {setEditedRows, setAddedRows} = useDatasetEditContext();
  const {id, value, field, api, serverValue, preserveFieldOrder} = params;

  // Convert edit params to render params
  const renderParams: GridRenderCellParams = {
    ...params,
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
        if (existingRow.___weave?.isNew) {
          setAddedRows(prev => {
            const newMap = new Map(prev);
            newMap.set(existingRow.___weave?.id, updatedRow);
            return newMap;
          });
        } else {
          setEditedRows(prev => {
            const newMap = new Map(prev);
            newMap.set(existingRow.___weave?.index, updatedRow);
            return newMap;
          });
        }
        api.stopCellEditMode({id, field});
      }}
      params={renderParams}
    />
  );
};

interface ControlCellProps {
  params: GridRenderCellParams;
  deleteRow: (absoluteIndex: number) => void;
  restoreRow: (absoluteIndex: number) => void;
  deleteAddedRow: (rowId: string) => void;
  isDeleted: boolean;
  isNew: boolean;
}

export const ControlCell: React.FC<ControlCellProps> = ({
  params,
  deleteRow,
  restoreRow,
  deleteAddedRow,
  isDeleted,
  isNew,
}) => {
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
          : isNew
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
        }}>
        {isNew && (
          <Button
            onClick={() => deleteAddedRow(params.row.___weave?.id)}
            tooltip="Remove"
            icon="close"
            size="small"
            variant="secondary"
          />
        )}
        {isDeleted && (
          <Button
            onClick={() => restoreRow(params.row.___weave?.index)}
            tooltip="Restore"
            icon="undo"
            size="small"
            variant="secondary"
          />
        )}
        {!isNew && !isDeleted && (
          <Button
            onClick={() => deleteRow(params.row.___weave?.index)}
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
