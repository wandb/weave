import * as Op from '@wandb/weave/core';
import {isFile, taggableValue} from '@wandb/weave/core';
import numeral from 'numeral';
import Prism from 'prismjs';
import React, {useEffect, useMemo, useRef} from 'react';
import {Segment} from 'semantic-ui-react';

import * as CGReact from '../../../react';
import * as Panel2 from '../panel';
import {EXTENSION_INFO, inputType, processTextForDisplay} from './common';

type PanelFileTextProps = Panel2.PanelProps<typeof inputType>;

const FILE_SIZE_LIMIT = 25 * 1024 * 1024;
const LINE_LENGTH_LIMIT = 1000;
const TOTAL_LINES_LIMIT = 10000;

const PanelFileTextRenderInner: React.FC<PanelFileTextProps> = props => {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (ref.current != null) {
      Prism.highlightElement(ref.current);
    }
  });

  const fileNode = props.input;
  const unwrappedType = taggableValue(fileNode.type);
  const fileExtension =
    isFile(unwrappedType) && unwrappedType.extension
      ? unwrappedType.extension
      : '';

  const contentsNode = useMemo(
    () => Op.opFileContents({file: props.input}),
    [props.input]
  );
  const contentsValueQuery = CGReact.useNodeValue(contentsNode);
  const loading = contentsValueQuery.loading;

  const processedResults = useMemo(() => {
    if (loading) {
      return null;
    }
    return processTextForDisplay(
      fileExtension,
      contentsValueQuery.result,
      LINE_LENGTH_LIMIT,
      TOTAL_LINES_LIMIT
    );
  }, [loading, fileExtension, contentsValueQuery.result]);

  if (loading) {
    return <div></div>;
  }

  const truncatedTotalLines = processedResults?.truncatedTotalLines;
  const truncatedLineLength = processedResults?.truncatedLineLength;
  const text = processedResults?.text;
  const language = languageFromFileName(fileExtension);

  return (
    <div style={{height: '100%', display: 'flex', flexDirection: 'column'}}>
      {truncatedLineLength && (
        <Segment textAlign="center">
          Warning: some lines truncated to {LINE_LENGTH_LIMIT} characters for
          display
        </Segment>
      )}
      {truncatedTotalLines && (
        <Segment textAlign="center">
          Warning: truncated to {TOTAL_LINES_LIMIT} lines for display
        </Segment>
      )}
      <div
        style={{
          background: 'white',
          border: '1px solid #eee',
          padding: 16,
          flexGrow: 1,
          overflow: 'auto',
        }}>
        <pre
          style={{
            maxWidth: '100%',
            overflowX: 'hidden',
            textOverflow: 'ellipsis',
          }}>
          <code
            ref={ref}
            className={language != null ? `language-${language}` : undefined}>
            {text}
          </code>
        </pre>
      </div>
    </div>
  );
};

const PanelFileText: React.FC<PanelFileTextProps> = props => {
  const fileNode = props.input;
  const fileSizeNode = Op.opFileSize({file: fileNode});
  const fileSizeQuery = CGReact.useNodeValue(fileSizeNode);
  if (fileSizeQuery.loading) {
    return <div></div>;
  }

  if ((fileSizeQuery.result ?? 0) > FILE_SIZE_LIMIT) {
    return (
      <Segment textAlign="center">
        Text view limited to files less than{' '}
        {numeral(FILE_SIZE_LIMIT).format('0.0b')}
      </Segment>
    );
  }

  return <PanelFileTextRenderInner {...props} />;
};

export default PanelFileText;

// TODO: we can have better types here
function languageFromFileName(fileExtension: string): string | null {
  return EXTENSION_INFO[fileExtension] ?? null;
}
