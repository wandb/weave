import React from 'react';
import * as CGReact from '@wandb/common/cgreact';
import {Panel2Loader} from '../PanelComp';
import * as S from '../PanelString.styles';
import * as Panel2 from '../panel';
import {inputType} from './common';

type PanelBooleanProps = Panel2.PanelProps<typeof inputType>;

const PanelBoolean: React.FC<PanelBooleanProps> = props => {
  const nodeValueQuery = CGReact.useNodeValue(props.input);
  if (nodeValueQuery.loading) {
    return <Panel2Loader />;
  }
  if (nodeValueQuery.result == null) {
    return (
      <S.StringContainer>
        <S.StringItem>-</S.StringItem>
      </S.StringContainer>
    );
  }
  return (
    <S.StringContainer
      style={{
        backgroundColor: nodeValueQuery.result
          ? 'rgba(100, 255, 100, 0.4)'
          : 'rgba(255, 100, 100, 0.4)',
      }}>
      <S.StringItem>{nodeValueQuery.result ? 'True' : 'False'}</S.StringItem>
    </S.StringContainer>
  );
};

export default PanelBoolean;
