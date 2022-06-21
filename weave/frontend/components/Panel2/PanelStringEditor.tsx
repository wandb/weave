import React from 'react';
import * as Panel2 from './panel';
import * as CGReact from '@wandb/common/cgreact';
import {Panel2Loader} from './PanelComp';
import EditableField from '@wandb/common/components/EditableField';
import * as S from './PanelString.styles';
import * as Op from '@wandb/cg/browser/ops';

const inputType = 'string' as const;
type PanelStringEditorProps = Panel2.PanelProps<typeof inputType>;

export const PanelStringEditor: React.FC<PanelStringEditorProps> = props => {
  const updateVal = CGReact.useAction(props.input, 'string-set');
  const nodeValueQuery = CGReact.useNodeValue(props.input);
  if (nodeValueQuery.loading) {
    return <Panel2Loader />;
  }
  const fullStr = String(
    nodeValueQuery.result == null ? '-' : nodeValueQuery.result
  );

  return (
    <S.StringContainer>
      <EditableField
        value={fullStr}
        placeholder="-"
        save={val => updateVal({val: Op.constString(val)})}
      />
    </S.StringContainer>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'string-editor',
  Component: PanelStringEditor,
  inputType,
};
