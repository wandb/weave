import {Box, Popover, PopoverProps} from '@mui/material';
import {Button} from '@wandb/weave/components/Button';
import React, {useEffect, useRef, useState} from 'react';
import {ResizableBox} from 'react-resizable';

import {DraggableGrow, DraggableHandle} from '../../../../DraggablePopups';
import {CodeEditor} from './editors/CodeEditor';
import {DiffEditor} from './editors/DiffEditor';
import {TextEditor} from './editors/TextEditor';

export type EditorMode = 'text' | 'code' | 'diff';

interface EditPopoverProps {
  anchorEl: HTMLElement | null;
  onClose: (value?: string) => void;
  initialWidth?: number;
  initialHeight?: number;
  initialEditorMode?: EditorMode;
  value: string;
  originalValue?: string;
  onChange: (value: string) => void;
  inputRef?: React.RefObject<HTMLTextAreaElement>;
  disabledModes?: EditorMode[];
  validationError?: string | null;
}

export const EditPopover: React.FC<EditPopoverProps> = ({
  anchorEl,
  onClose,
  initialWidth = 400,
  initialHeight = 300,
  initialEditorMode = 'text',
  value,
  originalValue = '',
  onChange,
  inputRef,
  disabledModes = [],
  validationError,
}) => {
  const [editorMode, setEditorMode] =
    React.useState<EditorMode>(initialEditorMode);
  const [boxWidth, setBoxWidth] = useState(initialWidth);
  const [boxHeight, setBoxHeight] = useState(initialHeight);
  const boxRef = useRef<HTMLDivElement>(null);
  const hasInitializedSize = useRef(false);

  // Calculate position directly from anchorEl when rendering
  let position = null;
  if (anchorEl) {
    const rect = anchorEl.getBoundingClientRect();
    const isInTopHalf = rect.top < window.innerHeight / 2;

    position = {
      left: rect.left + window.scrollX,
      top: isInTopHalf
        ? rect.bottom + window.scrollY - 36 // Move up by 36px when below
        : rect.top + window.scrollY - initialHeight + 36, // Move down by 36px when above
    };
  }

  // Only calculate the initial size once when the component mounts
  useEffect(() => {
    if (boxRef.current && !hasInitializedSize.current) {
      const contentWidth = Math.max(boxRef.current.scrollWidth, initialWidth);
      const contentHeight = Math.max(
        boxRef.current.scrollHeight,
        initialHeight
      );

      // Limit sizes to avoid excessive popover
      const maxWidth = Math.min(window.innerWidth * 0.8, 1000);
      const maxHeight = Math.min(window.innerHeight * 0.8, 800);

      setBoxWidth(Math.min(contentWidth, maxWidth));
      setBoxHeight(Math.min(contentHeight, maxHeight));

      hasInitializedSize.current = true;
    }
  }, [initialWidth, initialHeight]);

  // Handle resize events from ResizableBox
  const handleResize = (
    e: any,
    data: {size: {width: number; height: number}}
  ) => {
    setBoxWidth(data.size.width);
    setBoxHeight(data.size.height);
  };

  const renderEditor = () => {
    switch (editorMode) {
      case 'text':
        return (
          <TextEditor
            value={value}
            onChange={onChange}
            onClose={finalValue =>
              finalValue !== undefined ? onClose(finalValue) : onClose()
            }
            inputRef={inputRef}
          />
        );
      case 'code':
        return (
          <CodeEditor
            value={value}
            onChange={onChange}
            onClose={finalValue =>
              finalValue !== undefined ? onClose(finalValue) : onClose()
            }
          />
        );
      case 'diff':
        return (
          <DiffEditor
            value={value}
            originalValue={originalValue}
            onChange={onChange}
            onClose={finalValue =>
              finalValue !== undefined ? onClose(finalValue) : onClose()
            }
          />
        );
      default:
        return null;
    }
  };

  // Handle MUI Popover close events separately from our value-based close
  const handlePopoverClose: PopoverProps['onClose'] = (event, reason) => {
    // When closing via backdrop or escape key, just call the onClose handler
    // Need to cast the function to handle any type of parameter
    (onClose as any)();
  };

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
      onClose={handlePopoverClose}
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
        width={boxWidth}
        height={boxHeight}
        minConstraints={[initialWidth, initialHeight]}
        resizeHandles={['se']}
        onResize={handleResize}
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
          ref={boxRef}
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
                {!disabledModes.includes('text') && (
                  <Button
                    tooltip="Text mode"
                    icon="text-language"
                    size="small"
                    variant={editorMode === 'text' ? 'secondary' : 'ghost'}
                    onClick={() => setEditorMode('text')}
                  />
                )}
                {!disabledModes.includes('code') && (
                  <Button
                    tooltip="Code mode"
                    icon="code-alt"
                    size="small"
                    variant={editorMode === 'code' ? 'secondary' : 'ghost'}
                    onClick={() => setEditorMode('code')}
                  />
                )}
                {!disabledModes.includes('diff') && (
                  <Button
                    tooltip="Diff mode"
                    icon="diff"
                    size="small"
                    variant={editorMode === 'diff' ? 'secondary' : 'ghost'}
                    onClick={() => setEditorMode('diff')}
                  />
                )}
              </Box>
              <Box sx={{display: 'flex', gap: '4px'}}>
                <Button
                  tooltip="Confirm changes (Cmd+Enter)"
                  icon="checkmark"
                  size="small"
                  variant="primary"
                  onClick={e => {
                    e.preventDefault();
                    onClose(value);
                  }}
                  disabled={!!validationError}
                />
              </Box>
            </Box>
          </DraggableHandle>
          {validationError && (
            <Box
              sx={{
                padding: '8px 12px',
                backgroundColor: '#FFEBEE',
                color: '#D32F2F',
                fontSize: '12px',
                borderBottom: '1px solid rgba(0, 0, 0, 0.05)',
              }}>
              {validationError}
            </Box>
          )}
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
  );
};
