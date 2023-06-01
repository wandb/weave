import {SyntaxNode} from 'web-tree-sitter';

import type {EditingNode, Stack, Type} from '../model';

export interface ExpressionResult {
  expr: EditingNode;
  parseTree?: SyntaxNode;
  nodeMap?: Map<number, EditingNode>;
  extraText?: string;
}

export interface LanguageBinding {
  parse(input: string, stack?: Stack): Promise<ExpressionResult>;
  printGraph(input: EditingNode, indent?: number | null): string;
  printType(input: Type, simple?: boolean): string;
}
