import _ from 'lodash';

import {GlobalCGEventTracker} from '../analytics/tracker';
import {Cache, MapCache} from '../cache';
import {mapNodes} from '../callers';
import * as HL from '../hl';
import {constNode, union, unwrapTaggedValues} from '../model';
import * as GraphTypes from '../model/graph/types';
import * as Model from '../model/types';
import {StaticOpStore} from '../opStore/static';
import {OpStore} from '../opStore/types';
import {ResolverContext} from '../resolverContext';
import {opDefIsLowLevel} from '../runtimeHelpers';
import {ServerAPI} from '../serverApi';
import type {Tracer} from '../traceTypes';
import {
  ForwardGraph,
  ForwardOp,
  newForwardGraph,
  newRefForwardGraph,
} from './forwardGraph';
import {Engine} from './types';

export type {Engine} from './types';

async function mapValuesAsync(
  obj: object,
  asyncFn: (value: any, key: string) => Promise<any>
) {
  const promises = Object.entries(obj).map(([key, value]) => {
    return asyncFn(value, key).then(newValue => ({[key]: newValue}));
  });

  const resolvedProms = await Promise.all(promises);
  return resolvedProms.reduce((m, e) => Object.assign(m, e), {});
}

export interface Span {
  addTags(keyValueMap: Record<string, any>): Span;
}
export type BasicEngineTracer = <T>(
  label: string,
  doFn: (span?: Span) => T
) => T;

export interface BasicEngineOpts {
  // By default, we use a hashing forward graph
  fgFactory: () => ForwardGraph;
  engineFactory: () => Engine;

  // Compatible w/ Tracer.trace() from dd-trace
  trace: Tracer;
}

const forwardOpDependents = (
  op: ForwardOp
): Array<GraphTypes.OutputNode<Model.Type>> => {
  return [...op.outputNode.inputTo.values()].map(n => n.outputNode.node);
};

const forwardOpDependencies = (
  op: ForwardOp
): Array<GraphTypes.OutputNode<Model.Type>> => {
  return Object.values(op.op.inputs)
    .map(i => (i.nodeType === 'output' ? i : null))
    .filter(n => n !== null) as Array<GraphTypes.OutputNode<Model.Type>>;
};
export class BasicEngine implements Engine {
  public readonly opStore: OpStore;
  private readonly opts: BasicEngineOpts;

  constructor(
    private readonly cache: Cache,
    private readonly backend: ServerAPI,
    optsIn?: Partial<BasicEngineOpts>
  ) {
    this.opts = _.defaults({}, optsIn, {
      fgFactory: newForwardGraph,
      engineFactory: this.defaultCreateSubEngine.bind(this),
      trace: (s: string, fn: () => any) => fn(),
    });
    this.opStore = StaticOpStore.getInstance();
  }

  public async executeNodes(
    targetNodes: GraphTypes.NodeOrVoidNode[],
    stripTags = true,
    resetBackendExecutionCache = false
  ): Promise<any[]> {
    const fg = this.opts.fgFactory();
    for (const node of targetNodes) {
      if (node.nodeType !== 'void' && HL.nodeIsExecutable(node)) {
        fg.update(node);
      }
    }
    if (resetBackendExecutionCache) {
      await this.backend.resetExecutionCache();
    }
    GlobalCGEventTracker.engineForwardGraphNodes += fg.size();
    await this.invalidateRoots(fg);
    await this.executeForward(fg);
    return await this.getNodeResults(fg, targetNodes, stripTags);
  }

  public async mapNode(
    fnNode: GraphTypes.Node,
    inputs: any[],
    stripTags?: boolean
  ): Promise<any[]> {
    // First, we replace all the var nodes with const node placeholders.
    // This is very similar to what happens when we call `callFunction`.
    // The reason we do this instead of directly setting the value of the
    // var node is that some ops (eg. joinedTable) which are in the fnNode
    // may continue to chain ops and further execute. In such circumstances,
    // we need those var nodes to be fully resolved.
    let rowConstNode: GraphTypes.ConstNode | null = null;
    const indexConstNode = constNode('number', 0);
    fnNode = mapNodes(
      fnNode,
      n => {
        if (n.nodeType === 'var') {
          if (n.varName === 'row') {
            if (rowConstNode == null) {
              rowConstNode = constNode(n.type, null);
            } else {
              rowConstNode.type = union([rowConstNode.type, n.type]);
            }
            return rowConstNode;
          } else if (n.varName === 'index') {
            return indexConstNode;
          } else {
            throw new Error('mapNode fnNode has extra var node: ' + n.varName);
          }
        }
        return n;
      },
      true
    ) as GraphTypes.Node;

    const forwardGraph = this.opts.fgFactory();
    forwardGraph.update(fnNode);
    const context = {
      forwardGraph,
      backend: this.backend,
      frame: {},
      trace: this.opts.trace,
    };

    const result: any[] = [];
    for (let i = 0; i < inputs.length; i++) {
      const input = inputs[i];
      const nodeResults: Map<GraphTypes.Node, any> = new Map();
      if (rowConstNode != null) {
        (rowConstNode as GraphTypes.ConstNode).val = input;
        nodeResults.set(rowConstNode, input);
      }
      indexConstNode.val = i;
      nodeResults.set(indexConstNode, i);
      await this.executeForwardFast(fnNode, nodeResults, forwardGraph, context);
      result.push(nodeResults.get(fnNode));
    }
    if (stripTags) {
      return unwrapTaggedValues(result);
    }
    return result;
  }

  private async getNodeResults(
    fg: ForwardGraph,
    targetNodes: GraphTypes.NodeOrVoidNode[],
    stripTags = true
  ): Promise<any[]> {
    return await Promise.all(
      targetNodes.map(async node => {
        if (node.nodeType === 'void') {
          return undefined;
        } else if (node.nodeType === 'output') {
          if (stripTags) {
            return unwrapTaggedValues(
              await this.cache.get(fg.getOp(node.fromOp)!.outputNode.node)
            );
          }
          return await this.cache.get(fg.getOp(node.fromOp)!.outputNode.node);
        } else if (node.nodeType === 'const') {
          return node.val;
        }
        throw new Error('invalid targetNode');
      })
    );
  }

  private async invalidateRoots(fg: ForwardGraph): Promise<void> {
    const rootForwardOps = Array.from(fg.getRoots());
    const rootProms = rootForwardOps.map(forwardOp =>
      this.resolveForwardOp(fg, forwardOp)
    );
    const results = await Promise.all(rootProms);
    for (let i = 0; i < results.length; i++) {
      const result = results[i];
      const forwardOp = rootForwardOps[i];
      const cachedResult = await this.cache.get(forwardOp.outputNode.node);
      // Possibly expensive isEqual check, but only on roots so probably
      // not too bad. apollo-client (which handles all of our root ops as of
      // now) doesn't return reference-equal results even in the cache of an
      // apollo cache hit.
      if (
        typeof cachedResult === 'undefined' ||
        !_.isEqual(cachedResult, result)
      ) {
        // Breaking the pattern and tracing outside of this fn because it's not
        // that interesting.
        await this.clearForwardResults(forwardOp);
        const key = forwardOp.outputNode.node;
        // We make sure to add the dependencies and dependents so future
        // invalidations will clear nodes outside of the current FG
        await this.cache.set(
          key,
          result,
          undefined,
          forwardOpDependencies(forwardOp),
          forwardOpDependents(forwardOp)
        );
      }
    }
  }

  private async clearForwardResults(current: ForwardOp): Promise<void> {
    // Invalidate all nodes that depend on the current node.
    await this.cache.invalidate(current.outputNode.node);
  }

  private async executeForwardFast(
    node: GraphTypes.Node,
    nodeResults: Map<GraphTypes.Node, any>,
    fg: ForwardGraph,
    context: ResolverContext
  ): Promise<any> {
    // Traced by caller (needs to be fast!)
    let result = nodeResults.get(node);
    if (result !== undefined) {
      return result;
    }
    if (node.nodeType === 'output') {
      const op = node.fromOp;
      const inputs: {[key: string]: any} = {};
      for (const key of Object.keys(node.fromOp.inputs)) {
        inputs[key] = await this.executeForwardFast(
          node.fromOp.inputs[key],
          nodeResults,
          fg,
          context
        );
      }
      const opDef = this.opStore.getOpDef(op.name);
      if (opDefIsLowLevel(opDef)) {
        result = await opDef.resolver(
          inputs,
          fg,
          fg.getOp(op)!,
          context,
          () => this
        );
      }
    } else if (node.nodeType === 'const') {
      result = node.val;
    } else {
      throw new Error('invalid node');
    }
    nodeResults.set(node, result);
    return result;
  }

  private async executeForward(fg: ForwardGraph): Promise<void> {
    // Breadth first search.
    // Only enqueue nodes whose inputs have been resolved.
    const toExecuteOps = new Set(fg.getRoots());
    while (toExecuteOps.size > 0) {
      const executeNowOps = Array.from(toExecuteOps);
      toExecuteOps.clear();

      // Compute set of ops that need a result (those that don't
      // already have a result)
      const needResultIndexes: number[] = [];
      for (let i = 0; i < executeNowOps.length; i++) {
        const forwardOp = executeNowOps[i];
        if (!(await this.cache.has(forwardOp.outputNode.node))) {
          needResultIndexes.push(i);
        }
      }

      const results = await Promise.all(
        needResultIndexes.map(i => this.resolveForwardOp(fg, executeNowOps[i]))
      );

      // Update cache with results
      try {
        await this.cache.setMulti(
          results.map((r, i) => {
            const forwardOp = executeNowOps[needResultIndexes[i]];
            return {
              key: forwardOp.outputNode.node,
              value: r,
              dependsOn: forwardOpDependencies(forwardOp),
              dependencies: forwardOpDependents(forwardOp),
            };
          })
        );
      } catch (err) {
        // NOOP
      }

      // Schedule any nodes that now have all of their inputs ready
      for (const forwardOp of executeNowOps) {
        for (const nextForwardOp of forwardOp.outputNode.inputTo) {
          let inputsFilled = true;
          for (const nextForwardOpInputNode of Object.values(
            nextForwardOp.op.inputs
          )) {
            if (nextForwardOpInputNode.nodeType === 'output') {
              const producingForwardOp = fg.getOp(
                nextForwardOpInputNode.fromOp
              );
              if (producingForwardOp == null) {
                throw new Error('Invalid forward op');
              }
              if (!(await this.cache.has(producingForwardOp.outputNode.node))) {
                inputsFilled = false;
                break;
              }
            }
          }

          if (!toExecuteOps.has(nextForwardOp) && inputsFilled) {
            toExecuteOps.add(nextForwardOp);
          }
        }
      }
    }
  }

  private async resolveForwardOp(
    fg: ForwardGraph,
    forwardOp: ForwardOp
  ): Promise<any> {
    const op = forwardOp.op;
    const opDef = this.opStore.getOpDef(op.name);
    const resolver = opDefIsLowLevel(opDef) ? opDef.resolver : null;
    if (resolver == null) {
      throw new Error('no resolver for ' + op.name);
    }
    const opInputs = await mapValuesAsync(op.inputs, inputNode => {
      if (inputNode.nodeType === 'output') {
        const inputForwardOp = fg.getOp(inputNode.fromOp)!;
        return Promise.resolve(this.cache.get(inputForwardOp.outputNode.node));
      } else if (inputNode.nodeType === 'const') {
        return Promise.resolve(inputNode.val);
      } else {
        console.warn('INVALID INPUT IN FORWARD OP', inputNode, forwardOp);
        throw new Error('invalid input in forwardOp');
        // return Promise.resolve(null);
      }
    });

    try {
      const context = {
        forwardGraph: fg,
        backend: this.backend,
        frame: {},
        trace: this.opts.trace,
      };
      const result = await this.opts.trace(
        `resolver/${op.name}`,
        async () =>
          await resolver(
            opInputs,
            fg,
            forwardOp,
            context,
            this.opts.engineFactory
          )
      );
      GlobalCGEventTracker.engineResolves++;
      // TODO(np): Only need this so forwardOpInputs can read values for
      // output node inputs.
      forwardOp.outputNode.result = result;
      return result;
    } catch (err) {
      const nodeStr = JSON.stringify(forwardOp.outputNode.node, null, 2);
      console.error('Couldnt resolve node: ', nodeStr);
      console.error('Exception from resolver: ', err, (err as Error).stack);
      return Promise.reject(err);
    }
  }

  private defaultCreateSubEngine(): Engine {
    // Sub-engine uses fast in-memory LRU, not main cache
    return new BasicEngine(new MapCache(), this.backend, {
      fgFactory: newRefForwardGraph,
      trace: this.opts.trace,
    });
  }
}
