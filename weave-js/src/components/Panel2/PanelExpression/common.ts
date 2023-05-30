import {EditingNode, NodeOrVoidNode, Type, voidNode} from '@wandb/weave/core';

import {PanelProps} from '../panel';
export const inputType = 'any' as const;

// Unlike other panels, this panel may receive a void node as input
export type PanelExpressionProps = Omit<
  PanelProps<typeof inputType, PanelExpressionConfig>,
  'input'
> & {
  input: NodeOrVoidNode<typeof inputType>;
  standalone?: boolean;
};

export interface PanelExpressionConfig {
  exp: EditingNode;
  panelId: string | undefined;
  panelConfig: any;
  panelInputType: Type;
  exprAndPanelLocked?: boolean;
  // Set to true on newly added panels then immediately unset after focusing
  autoFocus?: boolean;

  // Temporary state to determine if any updates were performed with
  // weave backend enabled. This should be removed once weave python
  // gets to TS parity
  __weaveBackendRequired__?: boolean;
}

export const EMPTY_EXPRESSION_PANEL: PanelExpressionConfig = {
  exp: voidNode(),
  panelId: undefined,
  panelConfig: null,
  panelInputType: 'invalid',
  autoFocus: true,
} as const;
