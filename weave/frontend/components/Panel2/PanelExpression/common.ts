import {EditingNode} from '@wandb/cg/browser/types';
import * as Types from '@wandb/cg/browser/model/types';
import * as CG from '@wandb/cg/browser/graph';
export const inputType = 'any' as const;

export interface PanelExpressionConfig {
  exp: EditingNode;
  panelId: string | undefined;
  panelConfig: any;
  panelInputType: Types.Type;
}

export const EMPTY_EXPRESSION_PANEL: PanelExpressionConfig = {
  exp: CG.voidNode(),
  panelId: undefined,
  panelConfig: null,
  panelInputType: 'invalid',
};
