import {Node, NodeOrVoidNode, Type} from '@wandb/weave/core';

import {PanelStack} from '../availablePanels';
import * as Panel2 from '../panel';
import {StackInfo} from '../panellib/stackinfo';

export type PanelStepperConfigType = {
  currentStep: number;
  steps: number[];
  workingPanelId: string | undefined;
  workingKeyAndType: {key: string; type: Type};
  workingSliderKey: string | null;
};

export const LIST_ANY_TYPE: Type = {
  type: 'list' as const,
  objectType: 'any' as const,
};

export type PanelStepperProps = Panel2.PanelProps<
  typeof LIST_ANY_TYPE,
  PanelStepperConfigType
>;

export type additionalProps = {
  safeUpdateConfig: (updates: Partial<PanelStepperConfigType>) => void;
  convertedInputNode: Node;
  filteredNode: Node;
  outputNode: NodeOrVoidNode;
  propertyKeysAndTypes: {[key: string]: Type};
  childPanelStackIds: StackInfo[];
  childPanelHandler: PanelStack | undefined;
};

export type PanelStepperEntryProps = PanelStepperProps & {
  isConfigMode: boolean;
};
