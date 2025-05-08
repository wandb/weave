import {Box, Popover, PopoverProps} from '@mui/material';
import {Button} from '@wandb/weave/components/Button';
import React, {useEffect, useRef, useState} from 'react';
import {ResizableBox} from 'react-resizable';

import {DraggableGrow, DraggableHandle} from '../../../../DraggablePopups';
import {CodeEditor} from './editors/CodeEditor';
import {DiffEditor} from './editors/DiffEditor';
import {TextEditor} from './editors/TextEditor';

export type EditorMode = 'text' | 'code' | 'diff';

// Helper functions for value conversion
export const isJsonList = (value: any): boolean => Array.isArray(value);

export const stringifyValue = (value: any): string =>
  isJsonList(value)
    ? JSON.stringify(value, null, 2)
    : typeof value === 'string'
    ? value
    : String(value);

export const parseJsonList = (
  value: string
): {parsed?: any[]; error?: string} => {
  try {
    const parsed = JSON.parse(value);
    if (Array.isArray(parsed)) {
      return {parsed};
    }
    return {error: 'Value must be a JSON array'};
  } catch (err) {
    return {error: (err as Error).message};
  }
};

interface EditPopoverProps {
  anchorEl: HTMLElement | null;
  onClose: (value?: string | any[]) => void;
  initialWidth?: number;
  initialHeight?: number;
  initialEditorMode?: EditorMode;
  value: string | any[];
  originalValue?: string | any[];
  onChange: (value: string | any[]) => void;
  inputRef?: React.RefObject<HTMLTextAreaElement>;
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
}) => {
  const valueIsJsonList = isJsonList(value);
  const stringifiedValue = stringifyValue(value);
  const stringifiedOriginal = stringifyValue(originalValue);

  // Using a key derived from the stringified value to force re-initialization
  // of the editor state when the external value changes significantly
  const editorStateKey = stringifiedValue;

  const [editorMode, setEditorMode] =
    React.useState<EditorMode>(initialEditorMode);
  const [boxWidth, setBoxWidth] = useState(initialWidth);
  const [boxHeight, setBoxHeight] = useState(initialHeight);
  const boxRef = useRef<HTMLDivElement>(null);
  const hasInitializedSize = useRef(false);
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [currentEditorValue, setCurrentEditorValue] =
    useState<string>(stringifiedValue);

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

  // Process value changes and validate JSON when needed
  const handleValueChange = (newValue: string) => {
    setCurrentEditorValue(newValue);

    if (valueIsJsonList) {
      const {parsed, error} = parseJsonList(newValue);
      setJsonError(error || null);
      onChange(error ? newValue : parsed!);
    } else {
      onChange(newValue);
    }
  };

  // Handle closing with proper value conversion
  const handleClose = (finalValue?: string) => {
    // Use currentEditorValue as the default value if finalValue is not provided
    const valueToUse =
      finalValue !== undefined ? finalValue : currentEditorValue;

    if (valueToUse !== undefined) {
      if (valueIsJsonList) {
        const {parsed, error} = parseJsonList(valueToUse);
        if (error) {
          setJsonError(error);
          return; // Don't close if we have an error
        }
        onClose(parsed);
      } else {
        onClose(valueToUse);
      }
    } else {
      onClose();
    }
  };

  const renderEditor = () => {
    switch (editorMode) {
      case 'text':
        return (
          <TextEditor
            key={`text-${editorStateKey}`}
            value={currentEditorValue}
            onChange={handleValueChange}
            onClose={handleClose}
            inputRef={inputRef}
          />
        );
      case 'code':
        return (
          <CodeEditor
            key={`code-${editorStateKey}`}
            value={currentEditorValue}
            onChange={handleValueChange}
            onClose={handleClose}
            language={valueIsJsonList ? 'json' : undefined}
            disableClosing={valueIsJsonList && jsonError !== null}
          />
        );
      case 'diff':
        return (
          <DiffEditor
            key={`diff-${editorStateKey}`}
            value={currentEditorValue}
            originalValue={stringifiedOriginal}
            onChange={handleValueChange}
            onClose={handleClose}
            language={valueIsJsonList ? 'json' : undefined}
            disableClosing={valueIsJsonList && jsonError !== null}
          />
        );
      default:
        return null;
    }
  };

  // Handle MUI Popover close events separately from our value-based close
  const handlePopoverClose: PopoverProps['onClose'] = (event, reason) => {
    // Don't close the popover if JSON is invalid
    if (valueIsJsonList && jsonError !== null) {
      return;
    }

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
                {!valueIsJsonList && (
                  <Button
                    tooltip="Text mode"
                    icon="text-language"
                    size="small"
                    variant={editorMode === 'text' ? 'secondary' : 'ghost'}
                    onClick={() => setEditorMode('text')}
                  />
                )}
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
              <Box sx={{display: 'flex', gap: '4px'}}>
                <Button
                  tooltip="Confirm changes (Cmd+Enter)"
                  icon="checkmark"
                  size="small"
                  variant="primary"
                  disabled={valueIsJsonList && jsonError !== null}
                  onClick={e => {
                    e.preventDefault();
                    handleClose(currentEditorValue);
                  }}
                />
              </Box>
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
          {jsonError && (
            <Box
              sx={{
                padding: '8px 12px',
                backgroundColor: '#FFEBE6',
                color: '#BF2600',
                borderTop: '1px solid #FF8F73',
                fontSize: '12px',
                fontFamily: 'monospace',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}>
              {jsonError}
            </Box>
          )}
        </Box>
      </ResizableBox>
    </Popover>
  );
};
