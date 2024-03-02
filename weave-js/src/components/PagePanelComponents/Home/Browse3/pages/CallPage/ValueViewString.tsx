import copyToClipboard from 'copy-to-clipboard';
import React, {ReactNode, useCallback, useEffect, useState} from 'react';
import styled from 'styled-components';

import {toast} from '../../../../../../common/components/elements/Toast';
import Markdown from '../../../../../../common/components/Markdown';
import {MOON_150} from '../../../../../../common/css/color.styles';
import {Button} from '../../../../../Button';
import {CodeEditor} from '../../../../../CodeEditor';
import {ValueViewStringFormatMenu} from './ValueViewStringFormatMenu';

type ValueViewStringProps = {
  value: string;
  isExpanded: boolean;
};

const MAX_SCROLL_HEIGHT = 300;

const Column = styled.div`
  display: flex;
  flex-direction: column;
  width: 100%;
`;
Column.displayName = 'S.Column';

const Toolbar = styled.div`
  display: flex;
  align-items: center;
  padding: 4px 0;
  border-bottom: 1px solid ${MOON_150};
`;
Toolbar.displayName = 'S.Toolbar';

const Spacer = styled.div`
  flex: 1 1 auto;
`;
Spacer.displayName = 'S.Spacer';

const Collapsed = styled.div<{hasScrolling: boolean}>`
  min-height: 38px;
  line-height: 38px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: ${props => (props.hasScrolling ? 'pointer' : 'default')};
`;
Collapsed.displayName = 'S.Collapsed';

const Scrolling = styled.div`
  min-height: 38px;
  max-height: ${MAX_SCROLL_HEIGHT}px;
  display: flex;
  align-items: center;
  overflow: auto;
  white-space: break-spaces;
`;
Scrolling.displayName = 'S.Scrolling';

const ScrollingInner = styled.div`
  width: 100%;
  max-height: ${MAX_SCROLL_HEIGHT}px;
`;
ScrollingInner.displayName = 'S.ScrollingInner';

const Full = styled.div`
  white-space: break-spaces;
`;
Full.displayName = 'S.Full';

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

export const ValueViewString = ({value, isExpanded}: ValueViewStringProps) => {
  const trimmed = value.trim();
  const hasScrolling = trimmed.indexOf('\n') !== -1 || value.length > 100;
  const [hasFull, setHasFull] = useState(false);

  const json = isJSON(trimmed);
  const [format, setFormat] = useState(json ? 'JSON' : 'Text');

  const [mode, setMode] = useState(hasScrolling ? (isExpanded ? 1 : 0) : 0);

  useEffect(() => {
    setMode(hasScrolling ? (isExpanded ? 1 : 0) : 0);
  }, [hasScrolling, isExpanded]);

  const onClick = hasScrolling
    ? () => {
        const numModes = hasFull ? 3 : 2;
        setMode((mode + 1) % numModes);
      }
    : undefined;
  const copy = useCallback(() => {
    copyToClipboard(value);
    toast('Copied to clipboard');
  }, [value]);

  const onSetFormat = (newFormat: string) => {
    setFormat(newFormat);
  };

  const scrollingRef = React.createRef<HTMLDivElement>();

  useEffect(() => {
    if (scrollingRef.current) {
      setHasFull(scrollingRef.current.offsetHeight >= MAX_SCROLL_HEIGHT);
    }
  }, [mode, value, scrollingRef]);

  let toolbar = null;
  if (mode !== 0) {
    toolbar = (
      <Toolbar>
        {mode === 1 && hasFull && (
          <Button
            size="small"
            variant="ghost"
            icon="expand-uncollapse"
            tooltip="Maximize"
            onClick={() => setMode(2)}
          />
        )}
        <Button
          size="small"
          variant="ghost"
          icon="collapse"
          tooltip="Minimize"
          onClick={() => setMode(0)}
        />
        <Button
          style={{marginLeft: 8}}
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
        <ValueViewStringFormatMenu format={format} onSetFormat={onSetFormat} />
      </Toolbar>
    );
  }

  let content: ReactNode = trimmed;
  if (format === 'JSON') {
    let reformatted = trimmed;
    try {
      reformatted = JSON.stringify(JSON.parse(trimmed), null, 2);
    } catch (err) {
      // ignore
    }
    content = <CodeEditor value={reformatted} language="json" readOnly />;
  } else if (format === 'Markdown') {
    content = <Markdown content={trimmed} />;
  } else if (format === 'Code') {
    content = <CodeEditor value={trimmed} readOnly />;
  }

  if (mode === 2) {
    return (
      <Column>
        {toolbar}
        <Full>{content}</Full>
      </Column>
    );
  }
  if (mode === 1) {
    return (
      <Column>
        {toolbar}
        <Scrolling ref={scrollingRef}>
          <ScrollingInner>{content}</ScrollingInner>
        </Scrolling>
      </Column>
    );
  }
  return (
    <Collapsed hasScrolling={hasScrolling} onClick={onClick}>
      {value}
    </Collapsed>
  );
};
