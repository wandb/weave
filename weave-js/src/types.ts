import {EditingNode, Parser, Type} from '@wandb/weave/core';
import {UpdateConfig2} from './components/Panel2/panellib/libpanel';

export interface ExpressionResult {
  expr: EditingNode;
  parseTree?: Parser.SyntaxNode;
  nodeMap?: Map<number, EditingNode>;
  extraText?: string;
}

export interface PanelSpec<I extends Type = Type, C = any> {
  id: string;
  displayName?: string;
  Component: React.ComponentType<PanelProps<I, C>>;

  inputType: I;

  outputType?: (inputType: I) => Type;

  /**
   * Panels with `canFullscreen` will expand or shrink to fill the available vertical
   * space in their parent, and then restrict content from overflowing.
   * Otherwise, panels will expand vertically based on the size of their content.
   */
  canFullscreen?: boolean;

  defaultFixedSize?: Dimensions | ((config: C) => Dimensions);
}

export interface Dimensions {
  width: number | undefined;
  height: number | undefined;
}

export interface PanelProps<I, C> {
  input: I;
  config: C;
  updateInput?(newInput: Partial<I>): void;
  updateConfig2: UpdateConfig2<C>;
}
