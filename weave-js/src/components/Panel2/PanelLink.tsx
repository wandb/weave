import {Link} from '@wandb/weave/common/util/links';
import React from 'react';

import * as CGReact from '../../react';
import * as Panel2 from './panel';

const inputType = {
  type: 'union' as const,
  members: ['none' as const, 'link' as const],
};
type PanelLinkProps = Panel2.PanelProps<typeof inputType>;

const MAX_DISPLAY_LENGTH = 100;

export const PanelLink: React.FC<PanelLinkProps> = props => {
  const nodeValueQuery = CGReact.useNodeValue(props.input);
  if (nodeValueQuery.loading) {
    return <div>-</div>;
  }
  const fullStr = nodeValueQuery.result?.name ?? '-';
  const url = nodeValueQuery.result?.url ?? '/';
  const truncateText = fullStr.length > MAX_DISPLAY_LENGTH;
  const displayText =
    '' +
    (truncateText ? fullStr.slice(0, MAX_DISPLAY_LENGTH) + '...' : fullStr);
  return <Link to={url}>{displayText}</Link>;
};

export const Spec: Panel2.PanelSpec = {
  id: 'link',
  Component: PanelLink,
  inputType,
};
