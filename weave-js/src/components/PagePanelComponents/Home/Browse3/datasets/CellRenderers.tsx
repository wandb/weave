import Editor from '@monaco-editor/react';
import {Box, TextField, Typography} from '@mui/material';
import {Popover} from '@mui/material';
import {
  GridRenderCellParams,
  GridRenderEditCellParams,
} from '@mui/x-data-grid-pro';
import {Button} from '@wandb/weave/components/Button';
import {Icon} from '@wandb/weave/components/Icon';
import React, {useCallback, useState} from 'react';
import {ResizableBox} from 'react-resizable';

import {DraggableGrow, DraggableHandle} from '../../../../DraggablePopups';

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

export const CellViewingRenderer: React.FC<
  GridRenderCellParams & CellViewingRendererProps
> = ({
  value,
  isEdited = false,
  isDeleted = false,
  isNew = false,
  api,
  id,
  field,
  isEditing = false,
}) => {
  const [isHovered, setIsHovered] = useState(false);

  const handleEditClick = (event: React.MouseEvent) => {
    event.stopPropagation();
    api.startCellEditMode({id, field});
  };

  const getBackgroundColor = () => {
    if (isDeleted) {
      return 'rgba(255, 0, 0, 0.1)';
    }
    if (isEdited) {
      return 'rgba(0, 128, 128, 0.1)';
    }
    if (isNew) {
      return 'rgba(0, 255, 0, 0.1)';
    }
    return 'transparent';
  };

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
        opacity: isDeleted ? 0.5 : 1,
        textDecoration: isDeleted ? 'line-through' : 'none',
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
      }}>
      <span style={{flex: 1, position: 'relative', overflow: 'hidden'}}>
        {value}
        {isEditing && (
          <Box
            sx={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background:
                'linear-gradient(90deg, transparent 0%, transparent 10%, rgba(255, 255, 255, 0.8) 35%, transparent 60%, transparent 100%)',
              transform: 'translateX(-100%)',
              animation: 'shimmer 3s infinite linear',
              pointerEvents: 'none',
            }}
          />
        )}
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

export const CellEditingRenderer: React.FC<
  GridRenderEditCellParams
> = params => {
  const {id, value, field, hasFocus, api} = params;
  const inputRef = React.useRef<HTMLTextAreaElement>(null);
  const [anchorEl, setAnchorEl] = useState<HTMLDivElement | null>(null);
  const [hasInitialFocus, setHasInitialFocus] = useState(false);
  const initialWidth = React.useRef<number>();
  const initialHeight = React.useRef<number>();
  const [editorMode, setEditorMode] = useState<'text' | 'code'>('text');

  const getPopoverWidth = useCallback(() => {
    if (typeof value !== 'string') {
      return 400;
    }
    const approximateWidth = Math.min(Math.max(value.length * 8, 400), 960);
    return approximateWidth;
  }, [value]);

  const getPopoverHeight = useCallback(() => {
    if (typeof value !== 'string') {
      return 300;
    }
    const width = getPopoverWidth();
    const charsPerLine = Math.floor(width / 8);
    const lines = value.split('\n').reduce((acc, line) => {
      return acc + Math.ceil(line.length / charsPerLine);
    }, 0);

    const contentHeight = Math.min(Math.max(lines * 24 + 80, 120), 600);
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

  const handleValueChange = (
    event: React.ChangeEvent<HTMLInputElement> | string
  ) => {
    const newValue = typeof event === 'string' ? event : event.target.value;
    api.setEditCellValue({id, field, value: newValue});
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.metaKey) {
      event.stopPropagation();
    }
  };

  const renderEditor = () => {
    if (editorMode === 'text') {
      return (
        <TextField
          inputRef={inputRef}
          value={value as string}
          onChange={e => handleValueChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={e => {
            const target = e.target as HTMLTextAreaElement;
            target.setSelectionRange(0, target.value.length);
          }}
          fullWidth
          multiline
          autoFocus
          sx={{
            '& .MuiInputBase-root': {
              fontFamily: '"Source Sans Pro", sans-serif',
              fontSize: '14px',
              border: 'none',
              backgroundColor: 'white',
            },
            '& .MuiInputBase-input': {
              padding: '0px',
            },
            '& .MuiOutlinedInput-notchedOutline': {
              border: 'none',
            },
            '& textarea': {
              overflow: 'visible !important',
            },
          }}
        />
      );
    } else {
      return (
        <Box
          onKeyDown={handleKeyDown}
          sx={
            {
              height: '100%',
              width: '100%',
              '& .monaco-editor': {
                border: 'none !important',
                outline: 'none !important',
              },
              '& .monaco-editor .overflow-guard': {
                width: '100% !important',
                height: '100% !important',
              },
              '& .monaco-scrollable-element': {
                width: '100% !important',
                height: '100% !important',
              },
            } as const
          }>
          <Editor
            height="100%"
            width="100%"
            defaultValue={value as string}
            onChange={value => handleValueChange(value ?? '')}
            onMount={(editor, monacoInstance) => {
              // Handle Cmd+Enter to close
              editor.addCommand(
                monacoInstance.KeyMod.CtrlCmd | monacoInstance.KeyCode.Enter,
                () => {
                  api.stopCellEditMode({id, field});
                }
              );

              // Handle regular Enter
              const disposable = editor.onKeyDown(e => {
                if (e.browserEvent.key === 'Enter' && !e.browserEvent.metaKey) {
                  e.browserEvent.preventDefault();
                  e.browserEvent.stopPropagation();
                  editor.trigger('keyboard', 'type', {text: '\n'});
                }
              });

              // Clean up the event listener when editor is disposed
              editor.onDidDispose(() => {
                disposable.dispose();
              });

              // Force layout update
              setTimeout(() => {
                editor.layout();
              }, 0);
            }}
            options={{
              minimap: {enabled: false},
              scrollBeyondLastLine: true,
              fontSize: 12,
              fontFamily: 'monospace',
              lineNumbers: 'on',
              folding: false,
              automaticLayout: true,
              padding: {top: 12, bottom: 12},
              fixedOverflowWidgets: true,
              wordWrap: 'on',
            }}
          />
        </Box>
      );
    }
  };

  return (
    <>
      <CellViewingRenderer {...params} isEditing={true} />
      <Popover
        open={!!anchorEl}
        anchorEl={anchorEl}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'left',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'left',
        }}
        onClose={() => {
          setAnchorEl(null);
          api.stopCellEditMode({id, field});
          initialWidth.current = undefined;
          initialHeight.current = undefined;
        }}
        TransitionComponent={DraggableGrow}
        sx={{
          '& .MuiPaper-root': {
            backgroundColor: 'white',
            boxShadow:
              '0px 4px 20px rgba(0, 0, 0, 0.15), 0px 0px 40px rgba(0, 0, 0, 0.05)',
            border: 'none',
            borderRadius: '4px',
            overflow: 'hidden',
            padding: '0px',
          },
        }}>
        <ResizableBox
          width={initialWidth.current ?? 400}
          height={initialHeight.current ?? 300}>
          <Box
            sx={{
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
            }}>
            <DraggableHandle>
              <Box
                sx={{
                  cursor: 'grab',
                  backgroundColor: 'white',
                  display: 'flex',
                  justifyContent: 'space-between',
                  padding: '8px',
                  borderBottom: '1px solid rgba(0, 0, 0, 0.05)',
                }}>
                <Box>
                  <Button
                    tooltip="Text mode"
                    icon="text-language"
                    size="small"
                    variant={editorMode === 'text' ? 'secondary' : 'ghost'}
                    onClick={() => setEditorMode('text')}
                  />
                  <Button
                    tooltip="Code mode"
                    icon="code-alt"
                    size="small"
                    variant={editorMode === 'code' ? 'secondary' : 'ghost'}
                    onClick={() => setEditorMode('code')}
                  />
                </Box>
                <Typography
                  variant="caption"
                  sx={{
                    fontFamily: '"Source Sans Pro", sans-serif',
                    color: 'gray.500',
                  }}>
                  ⌘+Enter to close
                </Typography>
                <Button
                  icon="close"
                  size="small"
                  variant="ghost"
                  onClick={() => api.stopCellEditMode({id, field})}
                />
              </Box>
            </DraggableHandle>
            <Box
              sx={{
                flex: 1,
                overflow: 'auto',
                padding: editorMode === 'text' ? '12px' : '0px',
              }}>
              {renderEditor()}
            </Box>
          </Box>
        </ResizableBox>
      </Popover>
    </>
  );
};
