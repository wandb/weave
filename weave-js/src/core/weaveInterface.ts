import type {Client} from './client';
import type {ExpressionResult} from './language/types';
import type {
  EditingNode,
  EditingOp,
  EditingOpInputs,
  EditingOutputNode,
  Frame,
  Node,
  NodeOrVoidNode,
  OutputNode,
  Stack,
  Type,
} from './model';
import type {OpDef, OpDefGeneratedWeave} from './opStore';
import type {AutosuggestResult} from './suggest';

export type {Frame} from './model/graph/types';

// TODO(np): Collect all refs to HL, proxy them through this class
// Consolidated access to all weave-related functions
export interface WeaveInterface {
  readonly client: Client;
  typeIsAssignableTo(source: Type, target: Type): boolean;

  typeToString(type: Type): string;
  op(name: string): OpDef;

  callOp(opName: string, inputs: EditingOpInputs): EditingOutputNode;

  // Export parts of weave API, providing client automatically as needed
  // TODO(np): API docs go here
  // TODO(np): Entire HL interface should be re-exported here
  // TODO(np): HL fn's not requiring context, non-async should also be here

  // (tim): This is not part of the core WeaveInterface as it relies on
  // a lot of parser logic from weave. The `Weave` class that implements
  // this interface (and is used by EE) exposes this method manually.
  expression(input: string, stack?: Stack): Promise<ExpressionResult>;

  forwardExpression(expr: EditingNode): EditingNode[];

  expToString(node: EditingNode, indent?: number | null): string;

  nodeIsExecutable(node: EditingNode): node is NodeOrVoidNode;

  dereferenceAllVars(node: Node, stack: Stack): Node;

  callFunction(functionNode: NodeOrVoidNode, inputs: Frame): Node;

  expandAll(node: EditingNode, stack: Stack): Promise<EditingNode>;

  expandGeneratedWeaveOp(
    opDef: OpDefGeneratedWeave,
    node: OutputNode,
    stack: Stack
  ): Promise<Node>;

  refineEditingNode(
    node: EditingNode,
    stack: Stack,
    cache?: Map<EditingNode, EditingNode>
  ): Promise<EditingNode>;

  refineNode(node: NodeOrVoidNode, stack: Stack): Promise<NodeOrVoidNode>;

  suggestions(
    nodeOrOp: EditingNode | EditingOp,
    graph: EditingNode,
    stack: Stack,
    query?: string
  ): Promise<
    Array<AutosuggestResult<EditingNode>> | Array<AutosuggestResult<EditingOp>>
  >;
}
