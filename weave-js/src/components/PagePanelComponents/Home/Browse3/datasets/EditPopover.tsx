import {Box, Popover} from '@mui/material';
import {Button} from '@wandb/weave/components/Button';
import React from 'react';
import {ResizableBox} from 'react-resizable';

import {DraggableGrow, DraggableHandle} from '../../../../DraggablePopups';

export type EditorMode = 'text' | 'code' | 'diff';

interface EditPopoverProps {
  anchorEl: HTMLElement | null;
  onClose: () => void;
  initialWidth?: number;
  initialHeight?: number;
  editorMode: EditorMode;
  setEditorMode: (mode: EditorMode) => void;
  onRevert?: () => void;
  children: React.ReactNode;
}

export const EditPopover: React.FC<EditPopoverProps> = ({
  anchorEl,
  onClose,
  initialWidth = 400,
  initialHeight = 300,
  editorMode,
  setEditorMode,
  onRevert,
  children,
}) => {
  const [position, setPosition] = React.useState<{
    top: number;
    left: number;
  } | null>(null);

  React.useLayoutEffect(() => {
    if (anchorEl) {
      const rect = anchorEl.getBoundingClientRect();
      const isInTopHalf = rect.top < window.innerHeight / 2;

      setPosition({
        left: rect.left + window.scrollX,
        top: isInTopHalf
        ? rect.bottom + window.scrollY - 36  // Move up by 36px when below
        : rect.top + window.scrollY - initialHeight + 36, // Move down by 36px when above
    });
    } else {
      setPosition(null);
    }
  }, [anchorEl, initialHeight]);

  if (!position) {
    return null;
  }

  return (
    <Popover
      open={!!anchorEl}
      anchorReference="anchorPosition"
      anchorPosition={position}
      transformOrigin={{
        vertical: 'top',
        horizontal: 'left',
      }}
      onClose={onClose}
      TransitionComponent={DraggableGrow}
      sx={{
        '& .MuiPaper-root': {
          backgroundColor: 'white',
          boxShadow:
            '0px 4px 20px rgba(0, 0, 0, 0.15), 0px 0px 40px rgba(0, 0, 0, 0.05)',
          border: '1px solid rgba(0, 0, 0, 0.2)',
          borderRadius: '4px',
          overflow: 'hidden',
          padding: '0px',
        },
      }}>
      <ResizableBox
        width={initialWidth}
        height={initialHeight}
        resizeHandles={['se']}
        handle={
          <div
            className="react-resizable-handle react-resizable-handle-se"
            style={{
              position: 'absolute',
              right: 0,
              bottom: 0,
              width: '20px',
              height: '20px',
              cursor: 'se-resize',
              zIndex: 1000,
            }}
          />
        }>
        <Box
          sx={{
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            position: 'relative',
            '& .monaco-editor, & .monaco-diff-editor': {
              position: 'relative',
              zIndex: 1,
            },
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
                <Button
                  tooltip="Diff mode"
                  icon="diff"
                  size="small"
                  variant={editorMode === 'diff' ? 'secondary' : 'ghost'}
                  onClick={() => setEditorMode('diff')}
                />
              </Box>
              {onRevert && (
                <Box>
                  <Button
                    tooltip="Revert"
                    icon="undo"
                    size="small"
                    variant="ghost"
                    onClick={onRevert}
                  />
                </Box>
              )}
            </Box>
          </DraggableHandle>
          <Box
            sx={{
              flex: 1,
              overflow: 'auto',
              padding: editorMode === 'text' ? '12px' : '0px',
            }}>
            {children}
          </Box>
        </Box>
      </ResizableBox>
    </Popover>
  );
};
