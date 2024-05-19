import EditableField from '@wandb/weave/common/components/EditableField';
import {constString} from '@wandb/weave/core';
import React, {useCallback, useMemo} from 'react';

import {useMutation, useNodeValue} from '../../react';
import * as Panel2 from './panel';
import {Panel2Loader} from './PanelComp';
import * as S from './PanelString.styles';

const inputType = 'string' as const;
type PanelStringEditorProps = Panel2.PanelProps<typeof inputType>;

export const PanelStringEditor: React.FC<PanelStringEditorProps> = props => {
  const valueNode = props.input;
  const valueQuery = useNodeValue(valueNode);
  const setVal = useMutation(valueNode, 'set');
  const updateVal = useCallback(
    (newVal: string) => setVal({val: constString(newVal)}),
    [setVal]
  );
  const fullStr = String(valueQuery.result == null ? '-' : valueQuery.result);
  const multiline = useMemo(() => fullStr.includes('\n'), [fullStr]);

  if (valueQuery.loading) {
    return <Panel2Loader />;
  }

  return (
    <S.StringContainer>
      <S.StringItem>
        <EditableField
          value={fullStr}
          placeholder="-"
          multiline={multiline}
          save={updateVal}
        />
      </S.StringItem>
    </S.StringContainer>
  );
};

export const Spec: Panel2.PanelSpec = {
  hidden: false,
  id: 'StringEditor',
  icon: 'pencil-edit',
  Component: PanelStringEditor,
  inputType,
};
