import React from 'react';
import * as Panel2 from './panel';
import * as CGReact from '@wandb/common/cgreact';
import {TargetBlank} from '@wandb/common/util/links';
import {Panel2Loader} from './PanelComp';
import * as S from './PanelString.styles';

const inputType = {
  type: 'union' as const,
  members: [
    'none' as const,
    'string' as const,
    'number' as const,
    'boolean' as const,
    'id' as const,
  ],
};
type PanelStringProps = Panel2.PanelProps<typeof inputType>;

const MAX_DISPLAY_LENGTH = 100;

function isURL(text: string): boolean {
  try {
    const url = new URL(text);
    if (url && (url.protocol === 'http:' || url.protocol === 'https:')) {
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

export const PanelString: React.FC<PanelStringProps> = props => {
  const nodeValueQuery = CGReact.useNodeValue(props.input);
  if (nodeValueQuery.loading) {
    return <Panel2Loader />;
  }
  const fullStr = String(
    nodeValueQuery.result == null ? '-' : nodeValueQuery.result
  );

  const displayElement = (
    <S.StringContainer>
      <S.StringItem>{fullStr}</S.StringItem>
    </S.StringContainer>
  );
  const textIsURL = isURL(fullStr);

  if (textIsURL) {
    const truncateText = fullStr.length > MAX_DISPLAY_LENGTH;
    const displayText =
      '' +
      (truncateText ? fullStr.slice(0, MAX_DISPLAY_LENGTH) + '...' : fullStr);
    return <TargetBlank href={fullStr}>{displayText}</TargetBlank>;
  } else {
    return displayElement;
  }
};

export const Spec: Panel2.PanelSpec = {
  id: 'string',
  Component: PanelString,
  inputType,
};
