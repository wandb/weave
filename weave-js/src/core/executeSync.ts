/**
 * This file contains methods to execute Weave Nodes in a synchronous manner.
 * The primary method is `executeSync`. It's primary purpose is to allow
 * quick execution of small graphs - like the ones used in returnType opDefs.
 * Most callers will access this function via the `executeNodeSync` method
 * available in graph.ts.
 */

import {Query} from './_external/util/vega3';
import {ForwardGraph} from './engine/forwardGraph';
import type {Node} from './model/graph/types';
import type {
  ArtifactFileContent,
  ArtifactFileDirectUrl,
  DirMetadata,
  FileMetadata,
  RunFileContent,
} from './model/types';
import type {OpStore} from './opStore/types';
import {ResolverContext} from './resolverContext';
import {opDefIsLowLevel} from './runtimeHelpers';
import {ServerAPI} from './serverApi';

const isPromise = (object: any): object is Promise<any> =>
  object instanceof Promise ||
  (typeof object === 'object' &&
    object !== null &&
    typeof (object as any).then === 'function');

export const executeSync = (
  node: Node,
  nodeResults: Map<Node, any>,
  fg: ForwardGraph,
  opStore: OpStore
): any => {
  let result = nodeResults.get(node);
  if (result !== undefined) {
    return result;
  }
  if (node.nodeType === 'output') {
    const op = node.fromOp;
    const inputs: {[key: string]: any} = {};
    for (const key of Object.keys(node.fromOp.inputs)) {
      inputs[key] = executeSync(
        node.fromOp.inputs[key],
        nodeResults,
        fg,
        opStore
      );
    }
    const opDef = opStore.getOpDef(op.name);
    if (opDefIsLowLevel(opDef)) {
      const resolverResult = opDef.resolver(
        inputs,
        fg,
        fg.getOp(op)!,
        syncResolverContext,
        engineFactory
      );
      if (isPromise(resolverResult)) {
        throw new Error(
          `Cannot execute executeSync on async node: ${opDef.name}`
        );
      }
      result = resolverResult;
    } else {
      throw new Error(
        `Cannot execute executeSync on non-low level op: ${opDef.name}`
      );
    }
  } else if (node.nodeType === 'const') {
    result = node.val;
  } else {
    throw new Error('invalid node');
  }
  nodeResults.set(node, result);
  return result;
};

class ThrowingPlaceholderServer implements ServerAPI {
  async execute(query: Query): Promise<any> {
    throw new Error(`Cannot query`);
  }

  async resetExecutionCache(): Promise<void> {
    throw new Error(`Cannot resetExecutionCache`);
  }

  getArtifactFileContents(
    artifactId: string,
    assetPath: string
  ): Promise<ArtifactFileContent> {
    throw new Error(`Cannot getArtifactFileContents`);
  }

  getRunFileContents(
    projectName: string,
    runName: string,
    fileName: string,
    entityName?: string
  ): Promise<RunFileContent> {
    throw new Error(`Cannot getRunFileContents`);
  }

  getArtifactFileDirectUrl(
    artifactId: string,
    assetPath: string
  ): Promise<ArtifactFileDirectUrl> {
    throw new Error(`Cannot getArtifactFileDirectUrl`);
  }

  // TODO: NOT DONE
  getArtifactFileMetadata(
    artifactId: string,
    assetPath: string
  ): Promise<DirMetadata | FileMetadata | null> {
    throw new Error(`Cannot getArtifactFileMetadata`);
  }
}

const syncResolverContext: ResolverContext = {
  backend: new ThrowingPlaceholderServer(),
  frame: {},
  trace: (label, fn) => {
    return fn();
  },
};

const engineFactory = () => {
  throw new Error('Cannot use sub engine with synchronous execution');
};
