import {usePanelSettings} from '@wandb/weave/context';
import AU from 'ansi_up';
import classnames from 'classnames';
import * as Prism from 'prismjs';
import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';

import {File} from '../state/graphql/runFilesQuery';
import * as NBTypes from '../types/libs/ipynb';
import {ID} from '../util/id';
import {generateHTML} from '../util/markdown';
import BasicNoMatchComponent from './BasicNoMatchComponent';
import {UseLoadFile} from './FileBrowser';
import MonacoEditor from './Monaco/Editor';
import WandbLoader from './WandbLoader';

interface JupyterProps {
  file: File;
  useLoadFile: UseLoadFile;
}

export type JupyterViewPanelSettings = {
  allowScopedStyles?: boolean;
};

function sourceAsArray(source: string | string[]): string[] {
  if (typeof source === 'string') {
    return [source];
  }
  return source;
}

function renderableImageType(
  output: NBTypes.DisplayData | NBTypes.ExecuteResult
) {
  return ['image/png', 'image/jpeg', 'image/gif', 'image/bmp'].find(
    type => output.data[type]
  );
}

function processMediaString(mediaString: string | string[]): string {
  if (Array.isArray(mediaString)) {
    return mediaString.join('');
  }
  return mediaString;
}
function renderedImage(output: any, type: string, key: string) {
  return (
    <img
      key={key}
      alt={output.data['text/plain'] || key}
      src={`data:${type};base64,` + output.data[type]}
    />
  );
}

// This normalizes the styles within the iframe and communicates
// the height of the document
const wrapHTML = (html: string, id: string) => {
  return `<html>
  <head>
    <link rel="stylesheet" type="text/css" href="/normalize.css" />
    <script>
    let height;
    const sendPostMessage = () => {
      if (height !== document.body.offsetHeight) {
        height = document.body.offsetHeight;
        window.parent.postMessage({frameHeight: height, id: "${id}"}, '*');
      }
    }
    window.onload = () => sendPostMessage();
    window.onresize = () => sendPostMessage();
    </script>
  </head>${html}</html>`;
};

function processOutputs(
  cell: NBTypes.Cell,
  id: string,
  iframeRef: React.MutableRefObject<HTMLIFrameElement | null>
) {
  // TODO: Handle other cell types
  if (cell.cell_type !== 'code') {
    return [];
  }
  const ansiUp = new AU();
  if (cell.outputs == null) {
    console.warn('Empty cell', cell);
    return [];
  }
  let iframeHTML = '';
  const outputs: JSX.Element[] = [];
  cell.outputs.forEach((output, i): void => {
    const key = `${id}-output-${i}`;
    if (output.output_type === 'stream') {
      outputs.push(
        <div
          className={`${output.name} stream`}
          key={key}
          dangerouslySetInnerHTML={{
            __html: ansiUp.ansi_to_html(
              sourceAsArray(output.text)
                .filter((t: string) => !t.startsWith('wandb:'))
                .join('')
            ),
          }}
        />
      );
    } else if (output.output_type === 'error') {
      outputs.push(
        <div
          className="error"
          key={key}
          dangerouslySetInnerHTML={{
            __html: ansiUp.ansi_to_html(output.traceback.join('\n')),
          }}
        />
      );
    }
    if (
      output.output_type !== 'display_data' &&
      output.output_type !== 'execute_result'
    ) {
      console.warn('Skipping rendering of ', output.output_type);
      return undefined;
    }
    const imageType = renderableImageType(output);
    if (output.data['text/html']) {
      const html = processMediaString(output.data['text/html']);
      if (html.includes('<iframe')) {
        console.warn('Not rendering nested iframe');
        return undefined;
      }
      iframeHTML += html;
    } else if (imageType) {
      outputs.push(renderedImage(output, imageType, key));
      // TODO: image/svg+xml, plotly?
    } else if (output.data['text/markdown']) {
      outputs.push(
        <div
          className="markdown"
          key={key}
          dangerouslySetInnerHTML={{
            __html:
              generateHTML(processMediaString(output.data['text/markdown']))
                ?.value || '',
          }}
        />
      );
    } else if (output.data['text/json']) {
      outputs.push(
        <div className="json" key={key}>
          {processMediaString(output.data['text/json'])}
        </div>
      );
    } else if (output.data['text/plain']) {
      outputs.push(
        <div className="text" key={key}>
          {processMediaString(output.data['text/plain'])}
        </div>
      );
    }
  });
  // To keep things simple we always add the HTML at the start of the outputs
  // TODO: this could make some notebooks render funky
  if (iframeHTML !== '') {
    const key = `${id}-iframe`;
    outputs.unshift(
      <iframe
        ref={iframeRef}
        id={key}
        title={key}
        className="html"
        sandbox="allow-scripts allow-popups allow-downloads"
        key={key}
        style={{border: 'none', width: '100%'}}
        srcDoc={wrapHTML(iframeHTML, key)}
      />
    );
  }
  return outputs;
}

const JupyterViewerFromRun: React.FC<JupyterProps> = props => {
  const {useLoadFile, file} = props;
  const [raw, setRaw] = useState<any>();
  const [error, setErrorVal] = useState(false);
  const setError = useCallback(() => setErrorVal(true), [setErrorVal]);
  const NoMatch = BasicNoMatchComponent;

  useLoadFile(file, {
    onSuccess: setRaw,
    onFailure: setError,
    fallback: setError,
  });

  if (error) {
    return <NoMatch />;
  }

  if (raw == null) {
    return <WandbLoader name="jupyter-vewier" />;
  }

  return <JupyterViewer raw={raw} />;
};

export const JupyterCell: React.FC<{
  cell: NBTypes.Cell;
  runCode?: (code?: string) => void;
  saveCode?: (code: string) => void;
  id: string;
  readonly: boolean;
}> = ({cell, id, runCode, saveCode, readonly}) => {
  const panelSettings = usePanelSettings(
    'JupyterViewer'
  ) as JupyterViewPanelSettings;
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // This effect resizes the iframe so we don't have extra space / scrollbars
  useEffect(() => {
    const updateHeight = (e: any) => {
      if (
        iframeRef.current &&
        e.data.hasOwnProperty('frameHeight') &&
        e.data.id === iframeRef.current.id
      ) {
        const iframeHeight = Math.min(500, e.data.frameHeight);
        iframeRef.current.style.height = iframeHeight + 'px';
      }
    };
    if (iframeRef.current) {
      window.addEventListener('message', updateHeight);
      return () => {
        window.removeEventListener('message', updateHeight);
      };
    }
    return undefined;
  }, [iframeRef]);

  const outputs = useMemo(() => {
    return processOutputs(cell, id, iframeRef);
  }, [cell, id, iframeRef]);

  return (
    <div className={classnames({cell: true, readonly})}>
      {cell.cell_type === 'code' && (
        <div className="input">
          <div className="gutter">
            <span>{`[${cell.execution_count}]: `}</span>
          </div>
          <div className="source">
            <MonacoEditor
              value={sourceAsArray(cell.source).join('')}
              height={sourceAsArray(cell.source).length * 24}
              options={{
                readOnly: readonly,
                hideCursorInOverviewRuler: true,
                renderLineHighlight: 'none',
                lineNumbers: 'off',
                contextmenu: !readonly,
                occurrencesHighlight: false,
                folding: false,
                fontSize: 16,
                lineDecorationsWidth: 0,
                scrollbar: {
                  vertical: 'hidden',
                  handleMouseWheel: false,
                  useShadows: false,
                },
              }}
              theme={'wandb'}
              onChange={value => saveCode && saveCode(value || '')}
              onMount={(editor, monaco) => {
                monaco.editor.defineTheme('wandb', {
                  base: 'vs',
                  inherit: true,
                  rules: [],
                  colors: {
                    'editor.foreground': '#000000',
                    'editor.background': '#f5f5f5',
                  },
                });
                editor.addCommand(
                  // tslint:disable-next-line:no-bitwise
                  monaco.KeyMod.Shift | monaco.KeyCode.Enter,
                  _ => runCode && runCode(sourceAsArray(cell.source).join(''))
                );
              }}
              language="python"
            />
          </div>
        </div>
      )}
      {cell.cell_type === 'markdown' ? (
        <div
          className="output"
          dangerouslySetInnerHTML={{
            __html: generateHTML(sourceAsArray(cell.source).join(''), {
              allowScopedStyles: panelSettings?.allowScopedStyles ?? false,
            }).toString(),
          }}
        />
      ) : (
        <div className="output">{outputs}</div>
      )}
    </div>
  );
};

export const JupyterViewer: React.FC<{
  raw: string;
}> = ({raw}) => {
  const idRef = useRef(ID());
  useEffect(() => {
    Prism.highlightAll();
  });

  const notebook = useMemo(() => {
    try {
      const parsed = JSON.parse(raw) as NBTypes.NbformatSchema;
      parsed.cells.forEach(cell => {
        // Kaggle returns cell source as strings instead of arrays
        if (typeof cell.source === 'string') {
          cell.source = (cell.source as string).split('\n').map(s => s + '\n');
          // The final line shouldn't have a newline :(
          cell.source[cell.source.length - 1] =
            cell.source[cell.source.length - 1].trim();
        }
      });
      return parsed;
    } catch {
      return null;
    }
  }, [raw]);
  if (notebook == null) {
    return <div>Error</div>;
  }
  return (
    <div className="notebook" style={{position: 'relative'}}>
      {notebook.cells.map((cell, i) => (
        <JupyterCell
          readonly={true}
          cell={cell}
          id={`${idRef.current}-cell-${i}`}
          key={`${idRef.current}-cell-${i}`}
        />
      ))}
    </div>
  );
};

export default JupyterViewerFromRun;
