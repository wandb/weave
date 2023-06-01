import callFunction, {callOpVeryUnsafe} from '../../callers';
import {constNumber} from '../../model/graph/construction';
import type {Node, Op, OutputNode} from '../../model/graph/types';
import type {FunctionType, Type} from '../../model/types';
import type {ForwardGraph, ForwardGraphStorage, ForwardOp} from './types';

const opLambdaClosureArgBridge = (args: any) =>
  callOpVeryUnsafe('internal-lambdaClosureArgBridge', args);

function isRootOp(op: Op) {
  return Object.values(op.inputs).every(node => node.nodeType !== 'output');
}

function isTagConsumer(forwardOp: ForwardOp): boolean {
  // TODO (ts) - make this generic. For now we are hardcoding some
  // supported ops.
  //
  // Not supported: opTableRowTable, opGetJoinedJoinObj
  return (
    forwardOp.op.name === 'tag-run' ||
    forwardOp.op.name === 'tag-project' ||
    forwardOp.op.name === 'group-groupkey'
  );
}

function isTagCreator(sourceOp: ForwardOp, targetOpName: string): boolean {
  // TODO (ts) -  make this generic. For now we are hardcoding some
  // supported ops.
  //
  // Currently, this relies on the convention that ops which produce
  // run and project tags are always named run-* and project-* respectively.
  return (
    ((targetOpName === 'tag-run' || targetOpName === 'tag-project') &&
      sourceOp.op.name.startsWith(targetOpName.substring(4))) ||
    (targetOpName === 'group-groupkey' && sourceOp.op.name === 'groupby')
  );
}

function getTagProvidingInputNodes(
  taggingOp: ForwardOp,
  tagConsumingOp: ForwardOp
): OutputNode[] {
  // TODO (ts) -  make this generic. For now we are hardcoding some
  // supported ops.
  //
  // Currently, this relies on the convention that ops which produce
  // run and project tags are always named run-* and project-*, and
  // the inputs arguments to those ops are named `run` and `project` respectively.
  if (
    tagConsumingOp.op.name === 'tag-run' ||
    tagConsumingOp.op.name === 'tag-project'
  ) {
    const inputNode = taggingOp.op.inputs[tagConsumingOp.op.name.substring(4)];
    if (inputNode != null && inputNode.nodeType === 'output') {
      return [inputNode];
    }
  }

  if (
    tagConsumingOp.op.name === 'group-groupkey' &&
    taggingOp.op.name === 'groupby'
  ) {
    const nodes = getLambdaFunctionNodes(taggingOp);
    if (nodes != null) {
      return nodes;
    }
  }

  throw new Error(
    `No tag provided for ${tagConsumingOp.op.name} from ${taggingOp.op.name}`
  );
}

function getLambdaFunctionNodes(forwardOp: ForwardOp) {
  // TODO (ts) -  make this generic. For now we are hardcoding some
  // supported ops.
  //
  // We basically have to re-implement the way ops apply lambda functions
  // to their inputs. This is totally hidden right now.
  if (forwardOp.outputNode.lambdaFnNodes == null) {
    let node: OutputNode<Type> | null;
    if (forwardOp.op.name === 'groupby') {
      node = makeStandardArrLambdaFunctionNode(forwardOp, 'arr', 'groupByFn');
      if (node != null) {
        forwardOp.outputNode.lambdaFnNodes = [node];
      }
    } else if (forwardOp.op.name === 'filter') {
      node = makeStandardArrLambdaFunctionNode(forwardOp, 'arr', 'filterFn');
      if (node != null) {
        forwardOp.outputNode.lambdaFnNodes = [node];
      }
    } else if (forwardOp.op.name === 'sort') {
      node = makeStandardArrLambdaFunctionNode(forwardOp, 'arr', 'compFn');
      if (node != null) {
        forwardOp.outputNode.lambdaFnNodes = [node];
      }
    } else if (forwardOp.op.name === 'map') {
      const fnNode = getFnNode(forwardOp, 'mapFn');
      if (fnNode != null) {
        node = callFunction(fnNode, {
          row: callOpVeryUnsafe('index', {
            arr: opLambdaClosureArgBridge({
              arg: forwardOp.op.inputs.arr,
            }),
            index: constNumber(0),
          }),
          index: constNumber(0),
        }) as OutputNode;
        forwardOp.outputNode.lambdaFnNodes = [node];
      }
    } else if (forwardOp.op.name === 'join') {
      node = makeStandardArrLambdaFunctionNode(forwardOp, 'arr1', 'join1Fn');
      const node2 = makeStandardArrLambdaFunctionNode(
        forwardOp,
        'arr2',
        'join2Fn'
      );
      if (node != null && node2 != null) {
        forwardOp.outputNode.lambdaFnNodes = [node, node2];
      }
    } else if (forwardOp.op.name === 'joinAll') {
      const fnNode = getFnNode(forwardOp, 'joinFn');
      if (fnNode != null) {
        node = callFunction(fnNode, {
          row: callOpVeryUnsafe('index', {
            arr: callOpVeryUnsafe('index', {
              arr: opLambdaClosureArgBridge({
                arg: forwardOp.op.inputs.arrs,
              }),
              index: constNumber(0),
            }),
            index: constNumber(0),
          }),
        }) as OutputNode;
        forwardOp.outputNode.lambdaFnNodes = [node];
      }
    } else if (forwardOp.op.name === 'mapEach') {
      const fnNode = getFnNode(forwardOp, 'mapFn');
      if (fnNode != null) {
        node = callFunction(fnNode, {
          row: opLambdaClosureArgBridge({
            arg: forwardOp.op.inputs.obj,
          }),
        }) as OutputNode;
        forwardOp.outputNode.lambdaFnNodes = [node];
      }
    }
  }
  return forwardOp.outputNode.lambdaFnNodes;
}

function getFnNode(forwardOp: ForwardOp, fnArgKey: string) {
  const inputFnNode = forwardOp.op.inputs[fnArgKey];
  if (
    inputFnNode != null &&
    inputFnNode.nodeType === 'const' &&
    inputFnNode.type instanceof Object &&
    inputFnNode.type.type === 'function' &&
    inputFnNode.val.nodeType === 'output'
  ) {
    return inputFnNode.val as OutputNode<FunctionType>;
  }
  return null;
}

function makeStandardArrLambdaFunctionNode(
  forwardOp: ForwardOp,
  arrayArgKey: string,
  fnArgKey: string
) {
  const fnNode = getFnNode(forwardOp, fnArgKey);
  if (fnNode != null) {
    return callFunction(fnNode, {
      row: callOpVeryUnsafe('index', {
        arr: opLambdaClosureArgBridge({
          arg: forwardOp.op.inputs[arrayArgKey],
        }),
        index: constNumber(0),
      }),
    }) as OutputNode;
  }
  return null;
}

// Builds a new ForwardOp from a given node
function forwardOpFromNode(node: OutputNode): ForwardOp {
  return {
    op: node.fromOp,
    outputNode: {
      node,
      inputTo: new Set(),
      descendantTagConsumersWithAncestorProvider: {},
      consumedAsTagBy: new Set(),
      consumesTagFrom: new Set(),
    },
  };
}

// Returns a mapping from opName to a set of ForwardOps. This mapping represents all
// descendant tag consuming ops (possibly including the downstream op itself). Logically,
// this map contains all ForwardOps which are downstream and consume some tag upstream.
function getDescendantTagConsumersFromDownstreamOp(downstreamOp?: ForwardOp): {
  [opName: string]: Set<ForwardOp>;
} {
  let descendantTagConsumersWithAncestorProvider: {
    [opName: string]: Set<ForwardOp>;
  } = {};
  if (downstreamOp != null) {
    descendantTagConsumersWithAncestorProvider = {
      ...downstreamOp.outputNode.descendantTagConsumersWithAncestorProvider,
    };
    if (isTagConsumer(downstreamOp)) {
      const opName = downstreamOp.op.name;
      if (descendantTagConsumersWithAncestorProvider[opName] == null) {
        descendantTagConsumersWithAncestorProvider[opName] = new Set();
      } else {
        // A tag consumer should never have a descendant tag
        // consumer of the same type and would indicate an
        // error in the graph traversal algorithm / bookkeeping.
        throw new Error(`invalid`);
      }
      descendantTagConsumersWithAncestorProvider[opName].add(downstreamOp);
    }
  }
  return descendantTagConsumersWithAncestorProvider;
}

// Returns two objects:
// `createsTagFor`: the set of all ForwardOps which the `newForwardOp` creates a tag for.
// `remainingTagConsumers`: the mapping of tag consumers which are not met by this op.
function extractTagConsumers(
  newForwardOp: ForwardOp,
  downstreamOp?: ForwardOp
): {
  createsTagFor: Set<ForwardOp>;
  remainingTagConsumers: {[opName: string]: Set<ForwardOp>};
} {
  const createsTagFor: Set<ForwardOp> = new Set();
  const remainingTagConsumers: {[opName: string]: Set<ForwardOp>} = {};
  const descendantTagConsumers =
    getDescendantTagConsumersFromDownstreamOp(downstreamOp);
  Object.keys(descendantTagConsumers).forEach((opName: string) => {
    if (isTagCreator(newForwardOp, opName)) {
      descendantTagConsumers[opName].forEach(tagConsumerFOp => {
        createsTagFor.add(tagConsumerFOp);
      });
    } else {
      // Make a copy so future mutations do not affect the original
      remainingTagConsumers[opName] = new Set(descendantTagConsumers[opName]);
    }
  });
  return {createsTagFor, remainingTagConsumers};
}

// Strips away any tag consumer which has not been resolved upstream.
function removeUnresolvedDescendants(newForwardOp: ForwardOp) {
  const resolvedDescendantTagConsumers: {[opName: string]: Set<ForwardOp>} = {};
  Object.keys(
    newForwardOp.outputNode.descendantTagConsumersWithAncestorProvider
  ).forEach(opName => {
    const consumerSet =
      newForwardOp.outputNode.descendantTagConsumersWithAncestorProvider[
        opName
      ];
    if (consumerSet.size > 0) {
      const consumerOp = consumerSet.values().next().value as ForwardOp;
      // Here, we only need to look at the first instance of the op. If
      // any ops in this set have their consumesTagFrom set larger than 1
      // then they all will, and we add the entire collection to the final
      // resolved set.
      if (consumerOp.outputNode.consumesTagFrom.size > 0) {
        resolvedDescendantTagConsumers[opName] =
          newForwardOp.outputNode.descendantTagConsumersWithAncestorProvider[
            opName
          ];
      }
    }
  });
  newForwardOp.outputNode.descendantTagConsumersWithAncestorProvider =
    resolvedDescendantTagConsumers;
}

// Updates forward op with a new batch of incoming tag consumers.
// Any already known tag providers are automatically mapped, and
// the remaining list of unmatched tag consuming op names
// returned to the caller.
function updateForwardOpWithRemainingTagConsumers(
  forwardOp: ForwardOp,
  remainingTagConsumers: {
    [opName: string]: Set<ForwardOp>;
  }
): string[] {
  const unmatchedOpNames: string[] = [];
  Object.keys(remainingTagConsumers).forEach(opName => {
    if (forwardOp.op.name === opName) {
      // Tag consumers should never be the same as forward op. This
      // would indicate a bug in the graph traversal algorithm.
      throw new Error(
        'updateForwardOpWithRemainingTagConsumers: forwardOp is the same as consumerOp'
      );
    }
    if (
      forwardOp.outputNode.descendantTagConsumersWithAncestorProvider[opName] ==
      null
    ) {
      unmatchedOpNames.push(opName);
      forwardOp.outputNode.descendantTagConsumersWithAncestorProvider[opName] =
        remainingTagConsumers[opName];
    } else {
      const consumesTagFrom = (
        forwardOp.outputNode.descendantTagConsumersWithAncestorProvider[opName]
          .values()
          .next().value as ForwardOp
      ).outputNode.consumesTagFrom;
      if (consumesTagFrom.size > 0) {
        remainingTagConsumers[opName].forEach(consumerOp => {
          forwardOp.outputNode.descendantTagConsumersWithAncestorProvider[
            opName
          ].add(consumerOp);
          consumesTagFrom.forEach(tagProvider => {
            tagProvider.outputNode.consumedAsTagBy.add(consumerOp);
            consumerOp.outputNode.consumesTagFrom.add(tagProvider);
          });
        });
      } else {
        // `consumesTagFrom` should never be empty, this indicates
        // a bug in the graph traversal algorithm.
        throw new Error(
          'updateForwardOpWithRemainingTagConsumers: consumesTagFrom is empty'
        );
      }
    }
  });
  return unmatchedOpNames;
}

export class BaseForwardGraph implements ForwardGraph {
  public constructor(private readonly storage: ForwardGraphStorage) {}
  public getRoots(): Set<ForwardOp> {
    return this.storage.getRoots();
  }

  public getOp(op: Op): ForwardOp | undefined {
    return this.storage.getOp(op);
  }

  public setOp(op: ForwardOp): void {
    return this.storage.setOp(op);
  }

  public update(node: Node) {
    this.updateForwardGraphVisitNode(node);
  }

  public size() {
    return this.storage.size();
  }

  protected updateForwardGraphVisitOp(
    node: OutputNode,
    downstreamOp?: ForwardOp,
    tagsOnly?: boolean
  ) {
    const op = node.fromOp;
    const existingForwardOp = this.getOp(op);
    const isNewForwardOp = existingForwardOp == null;
    const forwardOp =
      existingForwardOp == null ? forwardOpFromNode(node) : existingForwardOp;
    const isLambdaBridge =
      forwardOp.op.name === 'internal-lambdaClosureArgBridge';
    if (!isLambdaBridge && isNewForwardOp && tagsOnly) {
      // The caller should not have tried to perform an update on a new op
      // with tags only. Tags only should only every be set called when calling
      // on an existing node.
      throw new Error(
        'updateForwardGraphVisitOp: tagsOnly should only be set on existing ops or lambda bridge ops'
      );
    }
    tagsOnly = tagsOnly || isLambdaBridge;
    if (!tagsOnly) {
      if (downstreamOp != null) {
        forwardOp.outputNode.inputTo.add(downstreamOp);
      }
      if (isNewForwardOp) {
        if (isRootOp(op)) {
          this.getRoots().add(forwardOp);
        }
        this.setOp(forwardOp);
      }
    }
    const {createsTagFor, remainingTagConsumers} = extractTagConsumers(
      forwardOp,
      downstreamOp
    );
    const unmatchedOpNames = updateForwardOpWithRemainingTagConsumers(
      forwardOp,
      remainingTagConsumers
    );
    const lambdaFunctionNodes = getLambdaFunctionNodes(forwardOp);

    // If it is an existing op, and there are unmatched tags coming, in...
    if (!isNewForwardOp && unmatchedOpNames.length > 0) {
      // First check it this op itself has vertical link(s). If so, follow it.
      if (forwardOp.outputNode.consumesTagFrom.size > 0) {
        forwardOp.outputNode.consumesTagFrom.forEach(tagProvider => {
          this.updateForwardGraphVisitNode(
            tagProvider.outputNode.node,
            forwardOp,
            true
          );
        });
      } else {
        // If not, then first pass up the tags to the lambda functions.
        if (lambdaFunctionNodes != null) {
          lambdaFunctionNodes.forEach(lambdaFunctionNode => {
            this.updateForwardGraphVisitNode(lambdaFunctionNode);
          });
        }
        // Followed by a tag-only pass to the inputs.
        for (const inputNode of Object.values(op.inputs)) {
          this.updateForwardGraphVisitNode(inputNode, forwardOp, true);
        }
      }
    } else if (isNewForwardOp) {
      // However, if this is a new op, then pass up the tags to the lambda functions.
      if (lambdaFunctionNodes != null) {
        lambdaFunctionNodes.forEach(lambdaFunctionNode => {
          this.updateForwardGraphVisitNode(lambdaFunctionNode);
        });
      }

      // Followed by visiting the inputs (this is the primary path).
      for (const inputNode of Object.values(op.inputs)) {
        this.updateForwardGraphVisitNode(inputNode, forwardOp);
      }
    }

    // Formally connect the tag providers & consumers, and erase any non-matched tag consumers.
    this.connectTagProviderToConsumers(forwardOp, createsTagFor);
    removeUnresolvedDescendants(forwardOp);
  }

  protected updateForwardGraphVisitNode(
    node: Node,
    inputToOp?: ForwardOp,
    tagsOnly?: boolean
  ) {
    if (node.nodeType === 'output') {
      this.updateForwardGraphVisitOp(node, inputToOp, tagsOnly);
    }
  }

  // Associates the tag consumers with the ops which create the tags.
  private connectTagProviderToConsumers(
    taggingFOp: ForwardOp,
    tagConsumerFOps: Set<ForwardOp>
  ) {
    tagConsumerFOps.forEach(tagConsumerFOp => {
      const tagProviderNodes = getTagProvidingInputNodes(
        taggingFOp,
        tagConsumerFOp
      );
      tagProviderNodes.forEach(tagProviderNode => {
        const tagProviderOp = this.getOp(tagProviderNode.fromOp);
        if (tagProviderOp != null) {
          tagProviderOp.outputNode.consumedAsTagBy.add(tagConsumerFOp);
          tagConsumerFOp.outputNode.consumesTagFrom.add(tagProviderOp);
        }
      });
    });
  }
}
