import _ from 'lodash';

import callFunction, {callOpVeryUnsafe, dereferenceAllVars} from './callers';
import {Client} from './client';
import {
  expandAll,
  expandGeneratedWeaveOp,
  nodeIsExecutable,
  refineEditingNode,
  refineNode,
  shouldSkipOpFirstInput,
} from './hl';
import {ExpressionResult, JSLanguageBinding, LanguageBinding} from './language';
import {
  EditingNode,
  EditingOp,
  EditingOpInputs,
  Frame,
  isAssignableTo,
  isConstNodeWithObjectType,
  Node,
  NodeOrVoidNode,
  OutputNode,
  Stack,
  Type,
  voidNode,
} from './model';
import {OpDefGeneratedWeave} from './opStore';
import {autosuggest} from './suggest';
import {WeaveInterface} from './weaveInterface';

// TODO (ts): move this implementation should be in the cg package
export class Weave implements WeaveInterface {
  private readonly languageBinding: LanguageBinding;

  constructor(readonly client: Client) {
    this.languageBinding = new JSLanguageBinding(this);
  }

  // Type-related
  typeIsAssignableTo(source: Type, target: Type): boolean {
    return isAssignableTo(source, target);
  }

  typeToString(type: Type, simple?: boolean): string {
    return this.languageBinding.printType(type, simple);
  }

  // Op-related
  op(id: string) {
    const op = this.client.opStore.getOpDef(id);
    if (op == null) {
      throw new Error(`Cannot find op with id "${id}"`);
    }
    return op;
  }

  callOp(opName: string, inputs: EditingOpInputs) {
    return callOpVeryUnsafe(opName, inputs);
  }

  // Language/expression-related
  // Convert an expression from expression language to actual CG
  // TODO(np): May contain voids?
  async expression(
    input: string,
    stack: Stack = []
  ): Promise<ExpressionResult> {
    const result = await this.languageBinding.parse(input, stack);
    return {
      ...result,
      // TODO(np): May not be necessary here, consolidate this error handling
      expr: result.expr ?? voidNode(),
    };
  }

  forwardExpression(expr: EditingNode): EditingNode[] {
    const result: EditingNode[] = [];
    let cursor: EditingNode | null = expr;
    while (cursor != null) {
      result.push(cursor);
      switch (cursor.nodeType) {
        case 'void':
        case 'const':
        case 'var':
          cursor = null;
          break;
        case 'output':
          const opDef = this.op(cursor.fromOp.name);
          if (!shouldSkipOpFirstInput(opDef)) {
            cursor = null;
          } else {
            cursor = Object.values(cursor.fromOp.inputs)[0];
          }
          break;
      }
    }

    return result.reverse();
  }

  expToString(node: EditingNode, indent: number | null = 0): string {
    return this.languageBinding.printGraph(node, indent);
  }

  /**
   * Determines whether the expressions represented by two nodes are logically
   * equivalent. This is used on panel updates to check if the input expression
   * has actually changed.
   */
  isExpLogicallyEqual(node1: NodeOrVoidNode, node2: NodeOrVoidNode): boolean {
    // If string representations don't match, the values are definitely different
    if (this.expToString(node1) !== this.expToString(node2)) {
      return false;
    }

    // Even if the string representations *do* match, the nodes may be objects that
    // aren't actually equal. For const nodes with `_is_object: true`, `expToString`
    // obfuscates the actual node value and returns a simple string based on the node
    // type, e.g. "<Group>" or "<Object>". In this case, we need a deep equality check.
    if (isConstNodeWithObjectType(node1) && isConstNodeWithObjectType(node2)) {
      return _.isEqual(node1.val, node2.val);
    }

    return true;
  }

  nodeIsExecutable(node: EditingNode): node is NodeOrVoidNode {
    return nodeIsExecutable(node);
  }

  dereferenceAllVars(node: Node, stack: Stack): Node {
    return dereferenceAllVars(node, stack).node as Node;
  }

  callFunction(functionNode: NodeOrVoidNode, frame: Frame): Node {
    return callFunction(functionNode, frame);
  }

  expandAll(node: EditingNode, stack: Stack) {
    return expandAll(this.client, node, stack);
  }

  expandGeneratedWeaveOp(
    opDef: OpDefGeneratedWeave,
    node: OutputNode,
    stack: Stack
  ) {
    return expandGeneratedWeaveOp(this.client, opDef, node, stack);
  }

  refineEditingNode(
    node: EditingNode,
    stack: Stack,
    cache?: Map<EditingNode, EditingNode>
  ) {
    return refineEditingNode(this.client, node, stack, cache);
  }

  refineNode<N extends NodeOrVoidNode>(node: N, stack: Stack): Promise<N> {
    return refineNode(this.client, node as Node, stack) as any;
  }

  // Suggestions
  suggestions(
    nodeOrOp: EditingNode | EditingOp,
    graph: EditingNode,
    stack: Stack,
    query?: string
  ) {
    return autosuggest(this.client, nodeOrOp, graph, stack, query);
  }
}
