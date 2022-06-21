import React from 'react';
import {useMemo} from 'react';
import * as Panel2 from './panel';
import * as CGReact from '@wandb/common/cgreact';
import {Panel2Loader} from './PanelComp';
import MonacoEditor from '@wandb/common/components/Monaco/Editor';
import * as S from './PanelString.styles';
import * as Op from '@wandb/cg/browser/ops';

// TODO: This pulls MonacoEditor into the bundle. We need to lazy load
// it like JupyterViewer does!

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
type PanelStringEditorProps = Panel2.PanelProps<typeof inputType>;

export const PanelTextEditor: React.FC<PanelStringEditorProps> = props => {
  const fileNode = props.input;
  const contentsNode = useMemo(
    () => Op.opFileContents({file: props.input}),
    [props.input]
  );
  const contentsValueQuery = CGReact.useNodeValue(contentsNode);
  const loading = contentsValueQuery.loading;
  const contents = contentsValueQuery.result;
  const updateVal = CGReact.useAction(contentsNode, 'string-set');
  const nodeValueQuery = CGReact.useNodeValue(props.input);
  if (nodeValueQuery.loading) {
    return <Panel2Loader />;
  }
  console.log('FULL STR', nodeValueQuery.result);

  return (
    <MonacoEditor
      language="python"
      value={contents}
      onChange={value => {
        console.log('onChange', value);
        updateVal({val: Op.constString(value)});
      }}
    />
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'text-editor',
  Component: PanelTextEditor,
  inputType,
};
