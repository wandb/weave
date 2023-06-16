// tslint:disable-next-line:no-circular-imports
import type {Client} from '../client/types';
import type {ForwardGraph, ForwardOp} from '../engine/forwardGraph/types';
// tslint:disable-next-line:no-circular-imports
import type {Engine} from '../engine/types';
import type {
  ExpansionRefineNodeCallback,
  InputTypes,
  Node,
  NodeOrVoidNode,
  OpCachePolicy,
  OpDefBase,
  OpFn,
  OpInputNodes,
  OpInputs,
  OpRenderInfo,
  OpResolverInputTypes,
  OutputNode,
  OutputTypeGeneric,
  Stack,
  SupportedEnginesType,
} from '../model/graph/types';
import type {Type} from '../model/types';
import type {ResolverContext} from '../resolverContext';

export type MakeOpDefOpts<RT extends Type, I extends InputTypes> = {
  name: string;
  argTypes: I;
  returnType: OutputTypeGeneric<I, RT>;
  renderInfo?: OpRenderInfo;
  resolver?: OpResolverFn;
  resolveOutputType?: RefineNodeFn;
  hidden?: boolean;
  kind?: string;
  cachePolicy?: OpCachePolicy;
  description?: string;
  argDescriptions?: {
    [key: string]: string;
  };
  returnValueDescription?: string;
  supportedEngines?: SupportedEnginesType;
};

export interface OpStore {
  allOps(): {
    [name: string]: OpDef;
  };
  getOpDef(name: string): OpDef;
  registerOp(op: OpDef): void;
  makeOp<RT extends Type, I extends InputTypes>(
    opts: MakeOpDefOpts<RT, I>
  ): (inputs: OpInputNodes<I>) => OutputNode<RT>;
  debugMeta(): {id: string} & {[prop: string]: any};
}

/** An op constructed only from other ops */
export interface OpDefWeave extends OpDefBase {
  body: NodeOrVoidNode;
}

export type OpDef = OpDefLowLevel | OpDefWeave | OpDefGeneratedWeave;

export interface OpDefLowLevel extends OpDefBase {
  // Function that can actually be called on some nodes,
  // producing an output node. This doesn't execute anything, it
  // just builds the graph.
  op: OpFn;

  // Function that actually executes the op
  resolver: OpResolverFn;

  // Optional function that gets a stronger type, or new node, potentially by
  // making a query.
  refineNode?: RefineNodeFn;
}

export type OpResolverFn = (
  inputs: OpResolverInputTypes<any>,
  forwardGraph: ForwardGraph,
  forwardOp: ForwardOp,
  context: ResolverContext,
  // TODO(np): Remove context or replace it with its constituents.
  engine: () => Engine
) => any;

// An optional function that can be provided for any op, to produce a more specific
// type (usually a value dependent type based on querying the server), or to
// return an entirely new node.
export type RefineNodeFn = (
  // The actual node to refine. This may include variables and isn't guaranteed
  // to be executable. If returning a whole new node, ensure the result is based
  // off of this node, so that ancestor variables are preserved.
  node: OutputNode,
  // An executable version of node (all variables have been derefferenced)
  executableNode: OutputNode,
  client: Client,
  stack: Stack
) => Promise<OutputNode<Type>>;

/** An op whose body can be generated via a javascript function */
export interface OpDefGeneratedWeave extends OpDefBase {
  expansion: ExpansionFunction;
}

export type ExpansionFunction = (
  inputs: OpInputs,
  refineNode: ExpansionRefineNodeCallback,
  client: Client
) => Promise<Node>;
