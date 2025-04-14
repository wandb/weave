import copyToClipboard from 'copy-to-clipboard';
import React, {ReactNode, useCallback, useEffect, useState} from 'react';
import styled from 'styled-components';

import {toast} from '../../../../../../common/components/elements/Toast';
import Markdown from '../../../../../../common/components/Markdown';
import {MOON_150} from '../../../../../../common/css/color.styles';
import {Button} from '../../../../../Button';
import {CodeEditor} from '../../../../../CodeEditor';
import {
  Format,
  ValueViewMarkdownFormatMenu,
} from './ValueViewMarkdownFormatMenu';

type ValueViewMarkdownProps = {
  value: string;
};

const Column = styled.div`
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  overflow: auto;
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

const Full = styled.div``;
Full.displayName = 'S.Full';

const PreserveWrapping = styled.div`
  white-space: break-spaces;
`;
PreserveWrapping.displayName = 'S.PreserveWrapping';

export const ValueViewMarkdown = ({value}: ValueViewMarkdownProps) => {
  const trimmed = value.trim();

  const [format, setFormat] = useState<Format>('Markdown');
  useEffect(() => {
    setFormat('Markdown');
  }, [value]);

  const copy = useCallback(() => {
    copyToClipboard(value);
    toast('Copied to clipboard');
  }, [value]);

  const onSetFormat = useCallback((newFormat: Format) => {
    setFormat(newFormat);
  }, []);

  const toolbar = (
    <Toolbar>
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
      <ValueViewMarkdownFormatMenu format={format} onSetFormat={onSetFormat} />
    </Toolbar>
  );

  let content: ReactNode = trimmed;
  if (format === 'Markdown') {
    content = <Markdown content={trimmed} />;
  } else if (format === 'Code') {
    content = <CodeEditor value={trimmed} language="markdown" readOnly />;
  } else {
    content = <PreserveWrapping>{content}</PreserveWrapping>;
  }

  return (
    <Column>
      {toolbar}
      <Full>{content}</Full>
    </Column>
  );
};
