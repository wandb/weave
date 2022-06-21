import React from 'react';
import {useEffect, useMemo, useRef} from 'react';
import {Segment} from 'semantic-ui-react';
import Prism from 'prismjs';
import numeral from 'numeral';

import * as Panel2 from './panel';
import makeComp from '@wandb/common/util/profiler';
import * as CGReact from '@wandb/common/cgreact';
import * as Op from '@wandb/cg/browser/ops';

export const EXTENSION_INFO: {[key: string]: string} = {
  log: 'text',
  text: 'text',
  txt: 'text',
  markdown: 'markdown',
  md: 'markdown',
  patch: 'diff',
  ipynb: 'python',
  py: 'python',
  yml: 'yaml',
  yaml: 'yaml',
  xml: 'xml',
  html: 'html',
  htm: 'html',
  json: 'json',
  css: 'css',
  js: 'js',
  sh: 'sh',
};

const inputType = {
  type: 'union' as const,
  members: Object.keys(EXTENSION_INFO).map(ext => ({
    type: 'file' as const,
    extension: ext,
    wbObjectType: 'none' as const,
  })),
};

type PanelFileTextProps = Panel2.PanelProps<typeof inputType>;

const FILE_SIZE_LIMIT = 25 * 1024 * 1024;
const LINE_LENGTH_LIMIT = 1000;
const TOTAL_LINES_LIMIT = 10000;

export const processTextForDisplay = (
  fileExtension: string,
  text: string,
  lineLengthLimit: number,
  totalLinesLimit: number
) => {
  let lines = text?.split?.('\n');
  let truncatedLineLength = false;
  let truncatedTotalLines = false;

  // Pretty-print JSON
  if (
    (fileExtension === 'json' && lines.length === 1) ||
    (lines.length === 2 && lines[1] === '')
  ) {
    try {
      const parsed = JSON.parse(lines[0]);
      lines = JSON.stringify(parsed, undefined, 2)?.split?.('\n');
    } catch {
      // ok
    }
  }

  if (fileExtension === 'ipynb') {
    try {
      const parsed = JSON.parse(text);
      let normalized = '';
      parsed.cells.forEach((cell: any) => {
        normalized += '# %%\n';
        normalized += cell.source.join('') + '\n';
      });
      lines = normalized.split('\n');
    } catch {
      // ok
    }
  }

  // Truncate long lines
  lines = lines.map(line => {
    if (line.length > lineLengthLimit) {
      truncatedLineLength = true;
      return (
        line.slice(0, lineLengthLimit) +
        ` ... (line truncated to ${lineLengthLimit} characters)`
      );
    } else {
      return line;
    }
  });

  if (lines.length > totalLinesLimit) {
    truncatedTotalLines = true;
    lines = [
      ...lines.slice(0, totalLinesLimit),
      '...',
      `(truncated to ${totalLinesLimit} lines)`,
    ];
  }

  return {
    text: lines.join('\n'),
    truncatedLineLength,
    truncatedTotalLines,
  };
};

const PanelFileTextRenderInner: React.FC<PanelFileTextProps> = makeComp(
  props => {
    const ref = useRef<HTMLDivElement>(null);
    useEffect(() => {
      if (ref.current != null) {
        Prism.highlightElement(ref.current);
      }
    });

    const fileNode = props.input;
    const fileExtension = fileNode.type.extension;

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

    const truncatedTotalLines = processedResults?.truncatedLineLength;
    const truncatedLineLength = processedResults?.truncatedTotalLines;
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
  },
  {id: 'PanelFileTextRenderInner'}
);

export const PanelFileText: React.FC<PanelFileTextProps> = props => {
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

// TODO: we can have better types here
function languageFromFileName(fileExtension: string): string | null {
  return EXTENSION_INFO[fileExtension] ?? null;
}

export const Spec: Panel2.PanelSpec = {
  id: 'text',
  Component: PanelFileText,
  inputType,
};
