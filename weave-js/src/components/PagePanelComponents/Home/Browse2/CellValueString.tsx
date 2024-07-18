/**
 * TODO: Combine common functionality between this and ValueViewString
 */

import {Popover} from '@mui/material';
import copyToClipboard from 'copy-to-clipboard';
import isUrl from 'is-url';
import React, {ReactNode, useCallback, useRef, useState} from 'react';
import styled from 'styled-components';

import {toast} from '../../../../common/components/elements/Toast';
import Markdown from '../../../../common/components/Markdown';
import * as Colors from '../../../../common/css/color.styles';
import {TargetBlank} from '../../../../common/util/links';
import {Button} from '../../../Button';
import {CodeEditor} from '../../../CodeEditor';
import {
  DraggableGrow,
  DraggableHandle,
  PoppedBody,
  StyledTooltip,
  TooltipHint,
} from '../../../DraggablePopups';

const isJSON = (value: string): boolean => {
  try {
    const parsed = JSON.parse(value);
    if (typeof parsed === 'object') {
      return true;
    }
  } catch (err) {
    // ignore
  }
  return false;
};

type CellValueStringProps = {
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

const TooltipText = styled.div<{isJSON: boolean}>`
  max-height: 35vh;
  overflow: auto;
  white-space: break-spaces;
  ${props => props.isJSON && 'font-family: monospace;'}
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
  border-bottom: 1px solid ${Colors.MOON_150};
`;
Toolbar.displayName = 'S.Toolbar';

const Spacer = styled.div`
  flex: 1 1 auto;
`;
Spacer.displayName = 'S.Spacer';

const CellValueStringWithPopup = ({value}: CellValueStringProps) => {
  const ref = useRef<HTMLDivElement>(null);
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const onClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(anchorEl ? null : ref.current);
  };

  const open = Boolean(anchorEl);
  const id = open ? 'simple-popper' : undefined;

  const trimmed = value.trim();
  const json = isJSON(trimmed);
  const [format, setFormat] = useState('Text');

  const copy = useCallback(() => {
    copyToClipboard(value);
    toast('Copied to clipboard');
  }, [value]);

  let content: ReactNode = <TooltipText isJSON={json}>{trimmed}</TooltipText>;
  if (format === 'Code') {
    let language;
    let reformatted = trimmed;
    try {
      reformatted = JSON.stringify(JSON.parse(trimmed), null, 2);
      language = 'json';
    } catch (err) {
      // ignore
    }
    content = <CodeEditor value={reformatted} language={language} readOnly />;
  } else if (format === 'Markdown') {
    content = <Markdown content={trimmed} />;
  }

  const title = open ? (
    '' // Suppress tooltip when popper is open.
  ) : (
    <TooltipContent onClick={onClick}>
      <TooltipText isJSON={json}>{trimmed}</TooltipText>
      <TooltipHint>Click for more details</TooltipHint>
    </TooltipContent>
  );

  // Unfortunate but necessary to get appear on top of peek drawer.
  const stylePopper = {zIndex: 1};

  return (
    <>
      <StyledTooltip enterDelay={500} title={title}>
        <Collapsed ref={ref} onClick={onClick}>
          {trimmed}
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
                  icon="copy"
                  tooltip="Copy to clipboard"
                  onClick={e => {
                    e.stopPropagation();
                    copy();
                  }}
                />
                <Spacer />
                <Button
                  size="small"
                  variant="quiet"
                  active={format === 'Text'}
                  icon="text-language"
                  tooltip="Text mode"
                  onClick={e => {
                    e.stopPropagation();
                    setFormat('Text');
                  }}
                />
                <Button
                  size="small"
                  variant="quiet"
                  active={format === 'Markdown'}
                  icon="document"
                  tooltip="Markdown mode"
                  onClick={e => {
                    e.stopPropagation();
                    setFormat('Markdown');
                  }}
                />
                <Button
                  size="small"
                  variant="quiet"
                  active={format === 'Code'}
                  icon="job-program-code"
                  tooltip="Code mode"
                  onClick={e => {
                    e.stopPropagation();
                    setFormat('Code');
                  }}
                />
                <Spacer />
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

export const CellValueString = ({value}: CellValueStringProps) => {
  const trimmed = value.trim();
  if (isUrl(trimmed)) {
    return <TargetBlank href={trimmed}>{trimmed}</TargetBlank>;
  }
  return <CellValueStringWithPopup value={value} />;
};
