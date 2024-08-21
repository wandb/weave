import copyToClipboard from 'copy-to-clipboard';
import isUrl from 'is-url';
import React, {ReactNode, useCallback, useEffect, useState} from 'react';
import styled from 'styled-components';

import {toast} from '../../../../../../common/components/elements/Toast';
import Markdown from '../../../../../../common/components/Markdown';
import {MOON_150} from '../../../../../../common/css/color.styles';
import {TargetBlank} from '../../../../../../common/util/links';
import {Alert} from '../../../../../Alert';
import {Button} from '../../../../../Button';
import {CodeEditor} from '../../../../../CodeEditor';
import {Format, ValueViewStringFormatMenu} from './ValueViewStringFormatMenu';

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
`;
Scrolling.displayName = 'S.Scrolling';

const ScrollingInner = styled.div`
  width: 100%;
  max-height: ${MAX_SCROLL_HEIGHT}px;
`;
ScrollingInner.displayName = 'S.ScrollingInner';

const Full = styled.div``;
Full.displayName = 'S.Full';

const PreserveWrapping = styled.div`
  white-space: break-spaces;
`;
PreserveWrapping.displayName = 'S.PreserveWrapping';

// Regular expressions for common Markdown syntax
// Note this is intentionally limited in scope to reduce false positives.
const LIKELY_MARKDOWN_PATTERNS: RegExp[] = [
  /```[\s\S]*```/, // Code block
  /\[.+\]\(.+\)/, // Links [text](url)
  /!\[.*\]\(.+\)/, // Images ![alt](url)
];

const isLikelyMarkdown = (value: string): boolean => {
  return LIKELY_MARKDOWN_PATTERNS.some(pattern => pattern.test(value));
};

const getDefaultFormat = (value: string): Format => {
  // TODO: Add JSON detection.
  if (isLikelyMarkdown(value)) {
    return 'Markdown';
  }
  return 'Text';
};

export const ValueViewString = ({value, isExpanded}: ValueViewStringProps) => {
  const trimmed = value.trim();
  const hasScrolling = trimmed.indexOf('\n') !== -1 || value.length > 100;
  const [hasFull, setHasFull] = useState(false);

  const [format, setFormat] = useState(getDefaultFormat(value));
  useEffect(() => {
    setFormat(getDefaultFormat(value));
  }, [value]);

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

  const onSetFormat = (newFormat: Format) => {
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
    let jsonValidationError = null;
    let reformatted = trimmed;
    try {
      reformatted = JSON.stringify(JSON.parse(trimmed), null, 2);
    } catch (err) {
      jsonValidationError = `${err}`;
    }
    content = (
      <>
        {jsonValidationError && (
          <Alert severity="warning">
            Value is not valid JSON: {jsonValidationError}
          </Alert>
        )}
        <CodeEditor value={reformatted} language="json" readOnly />
      </>
    );
  } else if (format === 'Markdown') {
    content = <Markdown content={trimmed} />;
  } else if (format === 'Code') {
    content = <CodeEditor value={trimmed} readOnly />;
  } else if (isUrl(trimmed)) {
    content = <TargetBlank href={trimmed}>{trimmed}</TargetBlank>;
  } else if (mode !== 0) {
    content = <PreserveWrapping>{content}</PreserveWrapping>;
  } else {
    content = value;
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
      {content}
    </Collapsed>
  );
};
