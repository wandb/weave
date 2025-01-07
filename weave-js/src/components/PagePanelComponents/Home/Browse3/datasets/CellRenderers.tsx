import {Box, Tooltip} from '@mui/material';
import {
  GridRenderCellParams,
  GridRenderEditCellParams,
} from '@mui/x-data-grid-pro';
import {Button} from '@wandb/weave/components/Button';
import {Icon} from '@wandb/weave/components/Icon';
import React, {useCallback, useState} from 'react';

import {CellValue} from '../../Browse2/CellValue';
import {CodeEditor} from './editors/CodeEditor';
import {DiffEditor} from './editors/DiffEditor';
import {TextEditor} from './editors/TextEditor';
import {EditorMode, EditPopover} from './EditPopover';

export const CELL_COLORS = {
  DELETED: 'rgba(255, 0, 0, 0.1)',
  EDITED: 'rgba(0, 128, 128, 0.1)',
  NEW: 'rgba(0, 255, 0, 0.1)',
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
}

const ShimmerOverlay: React.FC = () => (
  <Box
    sx={{
      position: 'absolute',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background:
        'linear-gradient(90deg, transparent 0%, rgba(128, 128, 128, 0) 20%, rgba(128, 128, 128, 0.2) 50%, rgba(128, 128, 128, 0) 80%, transparent 100%)',
      animation: 'shimmer-wobble 2s infinite ease-in-out',
      '@keyframes shimmer-wobble': {
        '0%': {
          transform: 'translateX(-100%) skewX(-15deg)',
          opacity: 0,
        },
        '20%': {
          opacity: 1,
        },
        '80%': {
          opacity: 1,
        },
        '100%': {
          transform: 'translateX(100%) skewX(-15deg)',
          opacity: 0,
        },
      },
      pointerEvents: 'none',
    }}
  />
);

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
}) => {
  const [isHovered, setIsHovered] = useState(false);

  const isEditable = typeof value !== 'object';

  const handleEditClick = (event: React.MouseEvent) => {
    event.stopPropagation();
    if (isEditable) {
      api.startCellEditMode({id, field});
    }
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

  if (!isEditable) {
    return (
      <Tooltip
        title="Cell type cannot be edited"
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
        textDecoration: isDeleted ? DELETED_CELL_STYLES.textDecoration : 'none',
        '@keyframes shimmer': {
          '0%': {
            transform: 'translateX(-100%)',
          },
          '100%': {
            transform: 'translateX(100%)',
          },
        },
        '&:hover': {
          backgroundColor: 'rgba(0, 0, 0, 0.04)',
        },
        ...(isEditing && {
          outline: '2px solid rgb(77, 208, 225)',
        }),
      }}>
      <span style={{flex: 1, position: 'relative', overflow: 'hidden'}}>
        {value}
        {isEditing && <ShimmerOverlay />}
      </span>
      {isHovered && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
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
          <Icon name="pencil-edit" height={14} width={14} />
        </Box>
      )}
    </Box>
  );
};

export interface CellEditingRendererProps extends GridRenderEditCellParams {
  serverValue?: string;
}

export const CellEditingRenderer: React.FC<
  CellEditingRendererProps
> = params => {
  const {id, value, field, hasFocus, api, serverValue} = params;
  const inputRef = React.useRef<HTMLTextAreaElement>(null);
  const [anchorEl, setAnchorEl] = useState<HTMLDivElement | null>(null);
  const [hasInitialFocus, setHasInitialFocus] = useState(false);
  const initialWidth = React.useRef<number>();
  const initialHeight = React.useRef<number>();
  const [editorMode, setEditorMode] = useState<EditorMode>('text');
  const [editedValue, setEditedValue] = useState(value as string);

  const handleEditorModeChange = (newMode: EditorMode) => {
    setEditorMode(newMode);
    initialWidth.current = getPopoverWidth(newMode);
    initialHeight.current = getPopoverHeight();
  };

  const handleValueChange = (newValue: string) => {
    setEditedValue(newValue);
    api.setEditCellValue({id, field, value: newValue});
  };

  const handleClose = () => {
    setAnchorEl(null);
    api.stopCellEditMode({id, field});
    initialWidth.current = undefined;
    initialHeight.current = undefined;
  };

  const handleRevertToServer = () => {
    api.setEditCellValue({id, field, value: serverValue ?? ''});
    handleClose();
  };

  const getPopoverWidth = useCallback(
    (mode: EditorMode = editorMode) => {
      if (typeof value !== 'string') {
        return 400;
      }
      const screenWidth = window.innerWidth;
      const maxWidth = screenWidth - 48; // Leave 24px padding on each side

      // For code and diff modes, use a larger minimum width
      const minWidth = 400;
      const approximateWidth = Math.min(
        Math.max(value.length * 10, minWidth),
        maxWidth
      );
      return mode === 'diff'
        ? Math.min(approximateWidth * 2, maxWidth)
        : approximateWidth;
    },
    [editorMode, value]
  );

  const getPopoverHeight = useCallback(() => {
    if (typeof value !== 'string') {
      return 300;
    }
    const width = getPopoverWidth();
    const charsPerLine = Math.floor(width / 8);
    const lines = value.split('\n').reduce((acc, line) => {
      return acc + Math.ceil(line.length / charsPerLine);
    }, 0);

    const maxHeight = Math.min(window.innerHeight / 2, 400);
    const contentHeight = Math.min(Math.max(lines * 24 + 80, 120), maxHeight);
    return contentHeight;
  }, [value, getPopoverWidth]);

  React.useLayoutEffect(() => {
    const element = api.getCellElement(id, field);
    if (element) {
      setAnchorEl(element);
      if (!initialWidth.current) {
        initialWidth.current = getPopoverWidth();
      }
      if (!initialHeight.current) {
        initialHeight.current = getPopoverHeight();
      }
    }
  }, [
    api,
    id,
    field,
    initialWidth,
    initialHeight,
    getPopoverWidth,
    getPopoverHeight,
    editorMode,
  ]);

  React.useEffect(() => {
    if (hasFocus && !hasInitialFocus) {
      setTimeout(() => {
        const textarea = inputRef.current?.querySelector('textarea');
        if (textarea) {
          textarea.focus();
          textarea.setSelectionRange(0, textarea.value.length);
          setHasInitialFocus(true);
        }
      }, 0);
    }
  }, [hasFocus, hasInitialFocus]);

  const renderEditor = () => {
    switch (editorMode) {
      case 'text':
        return (
          <TextEditor
            value={editedValue}
            onChange={handleValueChange}
            onClose={handleClose}
            inputRef={inputRef}
          />
        );
      case 'code':
        return (
          <CodeEditor
            value={editedValue}
            onChange={handleValueChange}
            onClose={handleClose}
          />
        );
      case 'diff':
        return (
          <DiffEditor
            value={editedValue}
            originalValue={serverValue ?? ''}
            onChange={handleValueChange}
            onClose={handleClose}
          />
        );
    }
  };

  return (
    <>
      <CellViewingRenderer {...params} isEditing={true} />
      <EditPopover
        anchorEl={anchorEl}
        onClose={handleClose}
        initialWidth={initialWidth.current}
        initialHeight={initialHeight.current}
        editorMode={editorMode}
        setEditorMode={handleEditorModeChange}
        onRevert={handleRevertToServer}>
        {renderEditor()}
      </EditPopover>
    </>
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
        <Button
          onClick={() => {
            if (isNew) {
              deleteAddedRow(params.row.___weave?.id);
            } else if (isDeleted) {
              restoreRow(params.row.___weave?.index);
            } else {
              deleteRow(params.row.___weave?.index);
            }
          }}
          tooltip={isNew ? 'Remove' : isDeleted ? 'Restore' : 'Delete'}
          icon={isNew ? 'close' : isDeleted ? 'undo' : 'delete'}
          size="small"
          variant="secondary"
        />
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
