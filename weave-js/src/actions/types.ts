import {Node, Stack} from '@wandb/weave/core';
import {SemanticICONS} from 'semantic-ui-react';

export interface NodeAction {
  // The name of the action, or a function that returns the name.
  // Displayed in bold in the Actions menu
  name: string | ((n: Node, stack: Stack) => string | Promise<string>);

  // An optional detail string, or a function that returns the detail string.
  // Displayed in normal weight in the Actions menu
  detail?: string | ((n: Node, stack: Stack) => string | Promise<string>);

  icon?: SemanticICONS;

  // A function that returns true if the action is available for the given node
  isAvailable: (n: Node, stack: Stack) => boolean | Promise<boolean>;

  // A function that performs the action
  doAction: (n: Node, stack: Stack) => void;

  onHoverStart?: (n: Node, stack: Stack) => void;
  onHoverEnd?: (n: Node, stack: Stack) => void;
}

export interface WeaveActionsContextState {
  readonly actions: NodeAction[];
  withNewActions(actions: NodeAction[]): WeaveActionsContextState;
}

export type WeaveActionsContextProviderProps = React.PropsWithChildren<{
  newActions: NodeAction[];
}>;
