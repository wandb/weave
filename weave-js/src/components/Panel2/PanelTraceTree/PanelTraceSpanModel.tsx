import {constString, opPick} from '@wandb/weave/core';
import {useNodeValue} from '@wandb/weave/react';
import React from 'react';

import * as Panel2 from '../panel';
import * as S from './lct.style';
import {GeneralObjectRenderer} from './PanelTraceTreeModel';
import {SpanWeaveType} from './util';

const inputType = SpanWeaveType;

type PanelTraceSpanModelProps = Panel2.PanelProps<typeof inputType, {}>;

const PanelTraceSpanModel: React.FC<PanelTraceSpanModelProps> = props => {
  const modelValue = useNodeValue(
    opPick({
      obj: props.input,
      key: constString('attributes.model.obj'),
    })
  );

  const modelObj = React.useMemo(() => {
    let modelVal = modelValue?.result;
    if (typeof modelVal === 'string') {
      try {
        modelVal = JSON.parse(modelVal);
      } catch (e) {
        console.log(e);
        modelVal = null;
      }
    }
    return modelVal;
  }, [modelValue]);

  if (modelValue.loading) {
    return <></>;
  } else if (modelObj == null) {
    return <>The selected span does not contain a model definition</>;
  }
  return (
    <S.ModelWrapper>
      <GeneralObjectRenderer data={modelObj} />
    </S.ModelWrapper>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'traceSpanModelPanel',
  canFullscreen: true,
  Component: PanelTraceSpanModel,
  inputType,
};
