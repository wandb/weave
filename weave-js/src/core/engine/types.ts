import type {NodeOrVoidNode} from '../model/graph/types';
import type {OpStore} from '../opStore/types';

export interface Engine {
  readonly opStore: OpStore;
  // Pass an array of executable nodes (any var nodes dereffed into consts)
  // and asynchronously resolve them for result
  executeNodes(
    targetNodes: NodeOrVoidNode[],
    stripTags?: boolean,
    resetBackendExecutionCache?: boolean
  ): Promise<any[]>;

  // Given a function node and an array of inputs, call function node
  // over each element in input and return an array of results
  mapNode(
    node: NodeOrVoidNode,
    inputs: any[],
    stripTags?: boolean
  ): Promise<any[]>;
}
