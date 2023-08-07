import React from 'react';

import * as CGReact from '../../../react';
import * as Panel2 from '../panel';
import {Panel2Loader} from '../PanelComp';
import * as S from '../PanelString.styles';
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
        <S.StringItem></S.StringItem>
      </S.StringContainer>
    );
  }
  // return a pill that is centered in the panel
  return (
    <div
      data-test-weave-id="boolean"
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100%',
        width: '100%',
        textAlign: 'center',
      }}>
      <div
        style={{
          lineHeight: '1em',
          padding: '0.3em 0.5em',
          borderRadius: '0.5em',
          backgroundColor: nodeValueQuery.result ? '#00A36815' : '#FF667016',
          color: nodeValueQuery.result ? '#008F5D' : '#EB1C45',
        }}>
        {nodeValueQuery.result ? 'True' : 'False'}
      </div>
    </div>
  );
};

export default PanelBoolean;
