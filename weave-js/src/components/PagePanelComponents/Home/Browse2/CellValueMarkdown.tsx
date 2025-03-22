import {Popover} from '@mui/material';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import copyToClipboard from 'copy-to-clipboard';
import React, {ReactNode, useCallback, useRef, useState} from 'react';
import styled from 'styled-components';

import {toast} from '../../../../common/components/elements/Toast';
import Markdown from '../../../../common/components/Markdown';
import * as Colors from '../../../../common/css/color.styles';
import {Button} from '../../../Button';
import {CodeEditor} from '../../../CodeEditor';
import {
  DraggableGrow,
  DraggableHandle,
  PoppedBody,
  StyledTooltip,
  TooltipHint,
} from '../../../DraggablePopups';
import {Icon} from '../../../Icon';

type CellValueMarkdownProps = {
  value: string;
};

const Collapsed = styled.div`
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
`;
Collapsed.displayName = 'S.Collapsed';

const TooltipContent = styled.div`
  display: flex;
  flex-direction: column;
`;
TooltipContent.displayName = 'S.TooltipContent';

const TooltipText = styled.div`
  max-height: 35vh;
  overflow: auto;
  white-space: break-spaces;
`;
TooltipText.displayName = 'S.TooltipText';

const Popped = styled.div`
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 0.8rem;
  word-wrap: break-word;
  background-color: #fff;
  color: ${Colors.MOON_700};
  border: 1px solid ${Colors.MOON_300};
`;
Popped.displayName = 'S.Popped';

const Toolbar = styled.div`
  display: flex;
  align-items: center;
  padding: 4px 0;
`;
Toolbar.displayName = 'S.Toolbar';

const Spacer = styled.div`
  flex: 1 1 auto;
`;
Spacer.displayName = 'S.Spacer';

const truncateText = (text: string, maxLength: number) => {
  if (text.length <= maxLength) {
    return text;
  }
  return text.slice(0, maxLength) + '...';
};

export const CellValueMarkdown = ({value}: CellValueMarkdownProps) => {
  const ref = useRef<HTMLDivElement>(null);
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const onClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(anchorEl ? null : ref.current);
  };

  const open = Boolean(anchorEl);
  const id = open ? 'simple-popper' : undefined;

  const trimmed = value.trim();
  const [format, setFormat] = useState('Markdown');

  const copy = useCallback(() => {
    copyToClipboard(value);
    toast('Copied to clipboard');
  }, [value]);

  let content: ReactNode = <TooltipText>{trimmed}</TooltipText>;
  if (format === 'Code') {
    content = (
      <CodeEditor
        value={trimmed}
        language="markdown"
        readOnly
        handleMouseWheel
        alwaysConsumeMouseWheel={false}
      />
    );
  } else if (format === 'Markdown') {
    content = <Markdown content={trimmed} />;
  }

  const title = open ? (
    '' // Suppress tooltip when popper is open.
  ) : (
    <TooltipContent onClick={onClick}>
      <Markdown content={trimmed} />
      <TooltipHint>Click for more details</TooltipHint>
    </TooltipContent>
  );

  // Unfortunate but necessary to get appear on top of peek drawer.
  const stylePopper = {zIndex: 1};

  return (
    <>
      <StyledTooltip enterDelay={500} title={title}>
        <Collapsed ref={ref} onClick={onClick}>
          <Tailwind>
            <div className="flex items-center gap-4">
              <div className="flex h-[22px] w-[22px] flex-none items-center justify-center rounded-full bg-moon-300/[0.48]">
                <Icon
                  role="presentation"
                  className="h-[14px] w-[14px]"
                  name="markdown"
                />
              </div>
              {truncateText(trimmed, 200)}
            </div>
          </Tailwind>
        </Collapsed>
      </StyledTooltip>
      <Popover
        id={id}
        open={open}
        anchorEl={anchorEl}
        style={stylePopper}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'center',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'center',
        }}
        onClose={() => setAnchorEl(null)}
        TransitionComponent={DraggableGrow}>
        <Popped>
          <TooltipContent>
            <DraggableHandle>
              <Toolbar>
                <Button
                  size="small"
                  variant="ghost"
                  active={format === 'Markdown'}
                  icon="markdown"
                  tooltip="Markdown mode"
                  onClick={e => {
                    e.stopPropagation();
                    setFormat('Markdown');
                  }}
                />
                <Button
                  size="small"
                  variant="ghost"
                  active={format === 'Code'}
                  icon="code-alt"
                  tooltip="Code mode"
                  onClick={e => {
                    e.stopPropagation();
                    setFormat('Code');
                  }}
                />
                <Button
                  size="small"
                  variant="ghost"
                  active={format === 'Text'}
                  icon="text-language"
                  tooltip="Text mode"
                  onClick={e => {
                    e.stopPropagation();
                    setFormat('Text');
                  }}
                />
                <Spacer />
                <Button
                  size="small"
                  variant="ghost"
                  icon="copy"
                  tooltip="Copy to clipboard"
                  onClick={e => {
                    e.stopPropagation();
                    copy();
                  }}
                />
                <Button
                  size="small"
                  variant="ghost"
                  icon="close"
                  tooltip="Close preview"
                  onClick={e => {
                    e.stopPropagation();
                    setAnchorEl(null);
                  }}
                />
              </Toolbar>
            </DraggableHandle>
            <PoppedBody>{content}</PoppedBody>
          </TooltipContent>
        </Popped>
      </Popover>
    </>
  );
};
