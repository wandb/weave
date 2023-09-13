import {Node} from '@wandb/weave/core';

export type NavigateToExpressionType = (expression: Node) => void;
export type SetPreviewNodeType = (node: React.ReactNode, requestedWidth?: string) => void;
