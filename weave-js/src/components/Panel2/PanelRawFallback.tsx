import {constNone, isAssignableTo} from '@wandb/weave/core';
import React, {useMemo} from 'react';

import * as CGReact from '../../react';
import * as Panel2 from './panel';
import {Panel2Loader} from './PanelComp';
import * as S from './PanelString.styles';
import {TooltipTrigger} from './Tooltip';

const inputType = 'any' as const;

type PanelRawFallbackProps = Panel2.PanelProps<typeof inputType>;

export const PanelRawFallback: React.FC<PanelRawFallbackProps> = props => {
  const safeInput = useMemo(() => {
    if (isAssignableTo(props.input.type, 'invalid')) {
      return constNone();
    }
    return props.input;
  }, [props.input]);

  const inputValue = CGReact.useNodeValue(safeInput);
  const loading = inputValue.loading;

  const fullStr = useMemo(() => {
    try {
      const val = inputValue?.result ?? '';
      if (typeof val === 'string') {
        return val;
      }
      if (typeof val === 'object') {
        return JSON.stringify(val, undefined, 2);
      }
      return String(val);
    } catch (e) {
      console.error(e);
      return '';
    }
  }, [inputValue?.result]);

  if (loading) {
    return <Panel2Loader />;
  }

  const contentPlaintext = (
    <S.PreformattedProportionalString>
      {fullStr}
    </S.PreformattedProportionalString>
  );

  return (
    <S.StringContainer>
      <S.StringItem>
        <TooltipTrigger copyableContent={fullStr} content={contentPlaintext}>
          {contentPlaintext}
        </TooltipTrigger>
      </S.StringItem>
    </S.StringContainer>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'raw',
  canFullscreen: true,
  Component: PanelRawFallback,
  inputType,
};
