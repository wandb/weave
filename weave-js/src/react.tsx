import {
  callOpVeryUnsafe,
  Client,
  ConstNode,
  constNodeUnsafe,
  constNumber,
  constString,
  dereferenceAllVars,
  EditingNode,
  expandAll,
  Frame,
  GlobalCGEventTracker,
  isAssignableTo,
  isConstNode,
  isFunction,
  isFunctionLiteral,
  isFunctionType,
  isList,
  isNodeOrVoidNode,
  isTimestamp,
  isVoidNode,
  isWeaveDebugEnabled,
  Node,
  NodeOrVoidNode,
  opCount,
  opIndex,
  OpInputs,
  opList,
  opTimestamp,
  pushFrame,
  resolveVar,
  simplify,
  Stack,
  Type,
  TypeToTSTypeInner,
  varNode,
  voidNode,
  WeaveInterface,
} from '@wandb/weave/core';
import _ from 'lodash';
import {
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import {PanelCompContext} from './components/Panel2/PanelComp';
import {usePanelContext} from './components/Panel2/PanelContext';
import {toWeaveType} from './components/Panel2/toWeaveType';
import {
  ClientContext,
  useWeaveClientEvalInUseNodeValueEnabled,
  useWeaveContext,
  useWeaveRefinementInReactHooksDisabled,
} from './context';
import {getUnresolvedVarNodes} from './core/callers';
import {
  callResolverSimple,
  clientSet,
  getChainRootConstructor,
  getChainRootVar,
  isConstructor,
} from './core/mutate';
import {trimStartChar} from './core/util/string';
import {UseNodeValueServerExecutionError} from './errors';
import {useDeepMemo} from './hookUtils';
import {consoleLog} from './util';
// import {useTraceUpdate} from './common/util/hooks';

/**
 * React hook-style function to get the
 * @param node the Weave CG node for which to evaluate
 * @param memoCacheId a unique id to use for memoization. If provided,
 * the caller can effectively clear the cache and force a re-evaluation.
 * Note: this will not clear the backend compute graph cache, so only
 * root nodes will be re-evaluated - recursively re-evaluating child
 * nodes only if the output changes.
 */

class ReactCGEventTracker {
  // Number of calls to useNodeValue
  useNodeValue: number = 0;
  private cgEventTracker: typeof GlobalCGEventTracker;

  constructor() {
    this.cgEventTracker = GlobalCGEventTracker;
  }

  public reset() {
    this.useNodeValue = 0;
    this.cgEventTracker.reset();
  }

  summary() {
    const cgSummary = this.cgEventTracker.summary();
    const toNodeSubscriptions =
      cgSummary._1_nodeSubscriptions.toRouted.toRemoteCache +
      cgSummary._1_nodeSubscriptions.toRouted.toBasicClientLocal +
      cgSummary._1_nodeSubscriptions.toEcosystem.toRemoteCache +
      cgSummary._1_nodeSubscriptions.toProduction.toBasicClientLocal;
    return {
      _0_useNodeValue: {
        resolvedWithCache: this.useNodeValue - toNodeSubscriptions,
        toNodeSubscriptions,
      },
      ...cgSummary,
    };
  }
}

export const GlobalCGReactTracker = new ReactCGEventTracker();

export const useClientContext = () => {
  return useContext(ClientContext);
};

// Thrown by useNodeValue if we're inside PanelMaybe and we get
// a null result.
export class NullResult {
  constructor(public node: NodeOrVoidNode) {}
}

// Thrown by useNodeValue if it attempts to evaluate an invalid graph,
// such as one that references a non-existent variable.
export class InvalidGraph {
  constructor(public message: string, public node: NodeOrVoidNode) {}
}

const clientEval = (node: NodeOrVoidNode, env: Stack): NodeOrVoidNode => {
  if (node.nodeType === 'var') {
    const resolved = resolveVar(env, node.varName);
    if (
      (resolved?.closure.value.nodeType === 'var' &&
        resolved.closure.value.varName === '__boundVar__') ||
      !resolved
    ) {
      // throw new Error('variable not defined ' + node.varName);
      return node;
    }
    const {closure} = resolved;
    return clientEval(closure.value, closure.stack);
  } else if (node.nodeType === 'const' && isFunctionType(node.type)) {
    let newStack = env;
    for (const [inputName, type] of Object.entries(node.type.inputTypes)) {
      newStack = pushFrame(newStack, {
        [inputName]: varNode(type, '__boundVar__'),
      });
    }
    const newVal = clientEval(node.val, newStack);
    return {
      ...node,
      val: newVal,
    };
  } else if (node.nodeType !== 'output') {
    return node;
  }

  const {name} = node.fromOp;
  const nodeInputs = _.mapValues(node.fromOp.inputs, n => clientEval(n, env));
  if (
    _.map(nodeInputs, n => isConstNode(n) && !isFunction(n.type)).every(x => x)
  ) {
    const inputs = _.mapValues(nodeInputs, n => (n as ConstNode).val);
    if (name === 'execute') {
      const result = clientEval(inputs.node, env);
      if (isConstNode(result)) {
        return result;
      }
      return {
        ...node,
        fromOp: {
          name: node.fromOp.name,
          inputs: {
            node: constNodeUnsafe(
              {type: 'function', inputTypes: {}, outputType: result.type},
              result
            ),
          },
        },
      };
    } else if (
      name === 'Object-__getattr__' ||
      name === 'pick' ||
      name === 'index' ||
      name === 'dict' ||
      name === 'list' ||
      name === 'timestamp'
    ) {
      let resolvedVal = callResolverSimple(name, inputs, node.fromOp);
      if (resolvedVal != null && resolvedVal.nodeType != null) {
        resolvedVal = clientEval(resolvedVal, env);
      }
      return constNodeUnsafe(node.type, resolvedVal);
    }
  }
  return {...node, fromOp: {...node.fromOp, inputs: nodeInputs as any}};
};

type ErrorStateType = {message: string; traceback: string[]};

const errorToText = (e: any) => {
  if (e instanceof Error) {
    return e.message + '\n\nStack:\n' + e.stack;
  } else if (typeof e === 'string') {
    return e;
  } else if (
    typeof e === 'object' &&
    e != null &&
    e.message != null &&
    e.traceback != null &&
    _.isArray(e.traceback)
  ) {
    return e.message + '\n\nTraceback:\n' + e.traceback.join('\n');
  } else if (
    typeof e === 'object' &&
    e != null &&
    e.message != null &&
    e.stack != null
  ) {
    return e.message + '\n\nStack:\n' + e.stack;
  } else {
    return '';
  }
};

let useNodeValueId = 0;

// Construct an id, once per mounted component. Use this to help in
// debugging.
export const useId = () => {
  const callSiteId = useRef(useNodeValueId++);
  return callSiteId.current;
};

export const useNodeValue = <T extends Type>(
  node: NodeOrVoidNode<T>,
  options?: {
    memoCacheId?: number;
    callSite?: string;
    skip?: boolean;
  }
): {loading: boolean; result: TypeToTSTypeInner<T>} => {
  const memoCacheId = options?.memoCacheId ?? 0;
  const callSite = options?.callSite;
  const skip = options?.skip;
  const enableClientEval = useWeaveClientEvalInUseNodeValueEnabled();
  const weave = useWeaveContext();
  const panelCompCtx = useContext(PanelCompContext);
  const context = useClientContext();
  const client = context.client;
  const {stack, panelMaybeNode} = usePanelContext();

  // consoleLog('USE NODE VALUE PRE CLIENT EVAL', weave.expToString(node), stack);

  const origNode = node;

  node = useMemo(() => {
    return dereferenceAllVars(node, stack).node as NodeOrVoidNode<T>;
  }, [node, stack]);

  node = useRefEqualWithoutTypes(node) as NodeOrVoidNode<T>;

  node = useMemo(
    () => (enableClientEval ? clientEval(node, stack) : node),
    [enableClientEval, node, stack]
  ) as NodeOrVoidNode<T>;

  GlobalCGReactTracker.useNodeValue++;
  node = useDeepMemo({node, memoCacheId}).node;
  const [error, setError] = useState<ErrorStateType | undefined>();
  const [result, setResult] = useState<{
    node: NodeOrVoidNode;
    value: any;
  }>({node: voidNode(), value: undefined});

  useEffect(() => {
    if (!isWeaveDebugEnabled()) {
      return;
    }

    let expr = weave.expToString(node);
    if (expr.length > 100) {
      expr = expr.slice(0, 40) + '...' + expr.slice(-40);
    }
    console.debug(
      `[Weave] [${(performance.now() / 1000).toFixed(
        3
      )}s] ${panelCompCtx.panelPath.join('.')}.useNodeValue: ${expr}`
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (skip) {
      return;
    }
    if (isConstNode(node)) {
      // See the "Mixing functions and expression" comment above.
      if (isFunction(node.type)) {
        setResult({node, value: node});
      } else {
        setResult({node, value: node.val});
      }
      return;
    }

    const unresolvedVarNodes = getUnresolvedVarNodes(node);
    if (unresolvedVarNodes.length > 0) {
      // Unresolved variables, cannot evaluate this graph.
      // Intended to be caught by PanelCompErrorBoundary.
      throw new InvalidGraph(
        `Unknown variable${
          unresolvedVarNodes.length > 1 ? 's' : ''
        } ${unresolvedVarNodes.join(', ')}.`,
        node
      );
    } else if (!isVoidNode(node)) {
      if (client == null) {
        throw new Error('client not initialized!');
      }
      // if (callSite != null) {
      //   console.log('useNodeValue subscribe', callSite, node);
      // }
      const obs = client.subscribe(node);
      const sub = obs.subscribe(
        nodeRes => {
          // if (callSite != null) {
          //   console.log('useNodeValue resolve', callSite, node);
          // }
          setResult({node, value: nodeRes});
        },
        caughtError => {
          setError(caughtError);
        }
      );
      return () => sub.unsubscribe();
    } else {
      return;
    }
  }, [client, node, memoCacheId, callSite, skip]);
  // useTraceUpdate('useNodeValue' + callSite, {
  //   client,
  //   node,
  //   memoCacheId,
  //   callSite,
  // });
  const finalResult = useMemo(() => {
    // Just rethrow the error in the render thread so it can be caught
    // by an error boundary.
    if (error != null) {
      const message =
        'Node execution failed (useNodeValue): ' + errorToText(error);
      // console.error(message);

      throw new UseNodeValueServerExecutionError(message);
    }
    if (isConstNode(node)) {
      if (isFunction(node.type)) {
        return {loading: false, result: node};
      } else {
        return {loading: false, result: node.val};
      }
    }
    const loading = result.node.nodeType === 'void' || node !== result.node;
    return {
      loading,
      result: result.value,
    };
  }, [error, node, result.node, result.value]);
  if (
    !finalResult.loading &&
    panelMaybeNode === origNode &&
    finalResult.result == null
  ) {
    // Throw NullResult for PanelMaybe to catch.
    throw new NullResult(result.node);
  }

  return finalResult;
};

/**
 * The useNodeValueExecutor hook allows the user
 * to retrieve the value of a node as a promise. This
 * is more of an edge case - please consider using useNodeValue
 * instead. However, if you need to get the value of a node conditionally
 * - for example, only after some user behavior - then this hook can be used.
 * After constructing the executor, the caller should be inside of a useEffect
 * or useCallback.
 */
export const useNodeValueExecutor = () => {
  const context = useClientContext();
  const client = context.client;
  if (client == null) {
    throw new Error('client not initialized!');
  }
  return useCallback(
    async (node: NodeOrVoidNode): Promise<any> => {
      return new Promise((resolve, reject) => {
        if (!isVoidNode(node)) {
          const obs = client!.subscribe(node);
          const sub = obs.subscribe(
            res => {
              sub.unsubscribe();
              resolve(res);
            },
            err => {
              sub.unsubscribe();
              reject(err);
            }
          );
        } else {
          return resolve(null);
        }
      });
    },
    [client]
  );
};

/**
 * useValue is a hook that wraps useNodeValue, but also the returned object
 * contains a `refresh` method which can be used to force
 * a re-evaluation of the node even if it is referentially equal. This would
 * be useful if the node's graph has a remote data fetch that is not a root op.
 * @param node the node to evaluate
 * @param defaultValue the default value to return while the node is loading
 */
export const useValue = <T extends Type>(
  node: NodeOrVoidNode<T>
): {
  loading: boolean;
  result: TypeToTSTypeInner<T>;
  refresh: () => void;
} => {
  // Would be better to support refreshing a single node
  // or maybe more particularly, refreshing all nodes in
  // the listening graph which depend on an ancestor of this node.
  const refreshAllNodes = useRefreshAllNodes();
  const [memoTrigger, setMemoTrigger] = useState(0);
  const refresh = useCallback(() => {
    refreshAllNodes();
    setMemoTrigger(t => t + 1);
  }, [refreshAllNodes, setMemoTrigger]);

  const res = useNodeValue(node, {memoCacheId: memoTrigger});

  return useMemo(
    () => ({
      ...res,
      refresh,
    }),
    [res, refresh]
  );
};

interface LocalArtifactRef {
  scheme: 'local-artifact';
  artifactName: string;
  artifactVersion: string;
  artifactPath: string;
}

export interface WandbArtifactRef {
  scheme: 'wandb-artifact';
  entityName: string;
  projectName: string;
  artifactName: string;
  artifactVersion: string;
  artifactPath: string;
  artifactRefExtra?: string;
}

export type WeaveKind = 'object' | 'op' | 'table' | 'call';
export interface WeaveObjectRef {
  scheme: 'weave';
  entityName: string;
  projectName: string;
  weaveKind: WeaveKind;
  artifactName: string;
  artifactVersion: string;
  artifactRefExtra?: string;
}

export type ArtifactRef = LocalArtifactRef | WandbArtifactRef;

type ArtifactObjectRef = ArtifactRef & {
  artifactRefExtra?: string;
};

export type ObjectRef = ArtifactObjectRef | WeaveObjectRef;

export const isWandbArtifactRef = (ref: ObjectRef): ref is WandbArtifactRef => {
  return ref.scheme === 'wandb-artifact';
};

export const isWeaveObjectRef = (ref: ObjectRef): ref is WeaveObjectRef => {
  return ref.scheme === 'weave';
};

// Entity name should be lowercase, digits, dash, underscore
// Unfortunately many teams have been created that violate this.
const PATTERN_ENTITY = '([^/]+)';
const PATTERN_PROJECT = '([^\\#?%:]{1,128})'; // Project name
const RE_WEAVE_OBJECT_REF_PATHNAME = new RegExp(
  [
    '^', // Start of the string
    PATTERN_ENTITY,
    '/',
    PATTERN_PROJECT,
    '/',
    '(object|op)', // Weave kind
    '/',
    '([a-zA-Z0-9-_/. ]{1,128})', // Artifact name
    ':',
    '([*]|[a-zA-Z0-9]+)', // Artifact version, allowing '*' for any version
    '/?', // Ref extra portion is optional
    '([a-zA-Z0-9_/]*)', // Optional ref extra
    '$', // End of the string
  ].join('')
);
const RE_WEAVE_TABLE_REF_PATHNAME = new RegExp(
  [
    '^', // Start of the string
    PATTERN_ENTITY,
    '/',
    PATTERN_PROJECT,
    '/table/',
    '([a-f0-9]+)', // Digest
    '/?', // Ref extra portion is optional
    '([a-zA-Z0-9_/]*)', // Optional ref extra
    '$', // End of the string
  ].join('')
);
const RE_WEAVE_CALL_REF_PATHNAME = new RegExp(
  [
    '^', // Start of the string
    PATTERN_ENTITY,
    '/',
    PATTERN_PROJECT,
    '/call/',
    '([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})', // Call UUID
    '/?', // Ref extra portion is optional
    '([a-zA-Z0-9_/]*)', // Optional ref extra
    '$', // End of the string
  ].join('')
);

export const parseRef = (ref: string): ObjectRef => {
  const url = new URL(ref);
  let splitLimit: number;

  const isWandbArtifact = url.protocol.startsWith('wandb-artifact');
  const isLocalArtifact = url.protocol.startsWith('local-artifact');
  const isWeaveRef = url.protocol.startsWith('weave');
  if (isWandbArtifact) {
    splitLimit = 4;
  } else if (isLocalArtifact) {
    splitLimit = 2;
  } else if (isWeaveRef) {
    splitLimit = 4;
  } else {
    throw new Error(`Unknown protocol: ${url.protocol}`);
  }

  // Decode the URI pathname to handle URL-encoded characters, required
  // in some browsers (safari)
  const decodedUri = decodeURIComponent(url.pathname);
  const splitUri = decodedUri.replace(/^\/+/, '').split('/', splitLimit);

  if (splitUri.length !== splitLimit) {
    throw new Error(`Invalid Artifact URI: ${url}`);
  }

  if (isWandbArtifact) {
    const [entityName, projectName, artifactId, artifactPathPart] = splitUri;
    const [artifactNamePart, artifactVersion] = artifactId.split(':', 2);
    return {
      scheme: 'wandb-artifact',
      entityName,
      projectName,
      artifactName: artifactNamePart,
      artifactVersion,
      artifactPath: artifactPathPart,
      artifactRefExtra: url.hash ? url.hash.slice(1) : undefined,
    };
  }

  if (isLocalArtifact) {
    const [artifactName, artifactPath] = splitUri;
    return {
      scheme: 'local-artifact',
      artifactName,
      artifactVersion: 'latest',
      artifactPath,
    };
  }

  if (isWeaveRef) {
    const trimmed = trimStartChar(decodedUri, '/');
    const tableMatch = trimmed.match(RE_WEAVE_TABLE_REF_PATHNAME);
    if (tableMatch !== null) {
      const [entity, project, digest] = tableMatch.slice(1);
      return {
        scheme: 'weave',
        entityName: entity,
        projectName: project,
        weaveKind: 'table' as WeaveKind,
        artifactName: '',
        artifactVersion: digest,
        artifactRefExtra: '',
      };
    }
    const callMatch = trimmed.match(RE_WEAVE_CALL_REF_PATHNAME);
    if (callMatch !== null) {
      const [entity, project, callId] = callMatch.slice(1);
      return {
        scheme: 'weave',
        entityName: entity,
        projectName: project,
        weaveKind: 'call' as WeaveKind,
        artifactName: callId,
        artifactVersion: '',
        artifactRefExtra: '',
      };
    }
    const match = trimmed.match(RE_WEAVE_OBJECT_REF_PATHNAME);
    if (match === null) {
      throw new Error('Invalid weave ref uri: ' + ref);
    }
    const [
      entityName,
      projectName,
      weaveKind,
      artifactName,
      artifactVersion,
      artifactRefExtra,
    ] = match.slice(1);
    return {
      scheme: 'weave',
      entityName,
      projectName,
      weaveKind: weaveKind as WeaveKind,
      artifactName,
      artifactVersion,
      artifactRefExtra: artifactRefExtra ?? '',
    };
  }
  throw new Error(`Unknown protocol: ${url.protocol}`);
};

export const objectRefWithExtra = (
  objRef: ObjectRef,
  extra: string
): ObjectRef => {
  let newExtra = '';
  if (objRef.artifactRefExtra != null && objRef.artifactRefExtra !== '') {
    newExtra = objRef.artifactRefExtra + '/';
  }
  newExtra += extra;
  return {
    ...objRef,
    artifactRefExtra: newExtra,
  };
};

export const refUri = (ref: ObjectRef): string => {
  if (isWandbArtifactRef(ref)) {
    let uri = `wandb-artifact:///${ref.entityName}/${ref.projectName}/${ref.artifactName}:${ref.artifactVersion}`;
    if (ref.artifactPath) {
      uri = `${uri}/${ref.artifactPath}`;
      if (ref.artifactRefExtra) {
        uri = `${uri}#${ref.artifactRefExtra}`;
      }
    }
    return uri;
  } else if (isWeaveObjectRef(ref)) {
    let name = `${ref.artifactName}:${ref.artifactVersion}`;
    if (ref.artifactName === '' && ref.weaveKind === 'table') {
      name = ref.artifactVersion;
    }
    let uri = `weave:///${ref.entityName}/${ref.projectName}/${ref.weaveKind}/${name}`;
    if (ref.artifactRefExtra != null && ref.artifactRefExtra !== '') {
      if (ref.artifactRefExtra.startsWith('/')) {
        // UGG Why does this happen???
        uri = `${uri}${ref.artifactRefExtra}`;
      } else {
        uri = `${uri}/${ref.artifactRefExtra}`;
      }
    }
    if (uri.endsWith('/')) {
      uri = uri.slice(0, -1);
    }
    return uri;
  } else {
    return `local-artifact:///${ref.artifactName}/${ref.artifactPath}`;
  }
};

export const absoluteTargetMutation = (absoluteTarget: NodeOrVoidNode) => {
  const rootConstructorNode = getChainRootConstructor(absoluteTarget);
  const rootArgsInner: {[key: string]: any} = {};
  if (
    rootConstructorNode != null &&
    rootConstructorNode.nodeType === 'output' &&
    rootConstructorNode.fromOp.name === 'get' &&
    isConstNode(rootConstructorNode.fromOp.inputs.uri)
  ) {
    return {
      rootArgs: rootArgsInner,
      mutationStyle: 'serverRef' as const,
      // TODO: we rely on the original root type here for the new type!
      // This is not quite right. The mutation resolver could return the actual
      // new type.
      rootType: rootConstructorNode.type,
    };
  }
  return {
    rootArgs: rootArgsInner,
    mutationStyle: 'clientRef' as const,
    rootType: absoluteTarget.type,
  };
};

export const makeCallAction = (
  actionName: string,
  absoluteTarget: NodeOrVoidNode,
  target: NodeOrVoidNode,
  stack: Stack,
  triggerExpressionEvent: ReturnType<
    typeof usePanelContext
  >['triggerExpressionEvent'],
  mutationStyle: string,
  rootArgs: {[key: string]: any},
  rootType: Type,
  refreshAll: () => Promise<void>,
  handleRootUpdate?: (newRoot: Node) => void,
  ignoreNullResult: boolean = true
) => {
  return (client: Client, inputs: OpInputs) => {
    consoleLog('MUTATION', actionName, absoluteTarget, target, stack, inputs);

    if (mutationStyle === 'invalid') {
      console.warn('Mutation attempted for invalid target', absoluteTarget);
      return;
    }

    const onDone = (final: any) => {
      if (final == null && ignoreNullResult) {
        // pass
      } else if (mutationStyle === 'clientRef') {
        consoleLog('clientRef useAction result', final);
        let newRootNode: Node;
        if (isNodeOrVoidNode(final)) {
          if (final.nodeType !== 'const') {
            throw new Error('Unexpected mutation result');
          }
          newRootNode = final;
        } else {
          newRootNode = constNodeUnsafe(toWeaveType(final), final);
        }

        // This is a gnarly hack. final is a json value, we don't know its True
        // Weave type. This generally works for basic json types, but in particular
        // it doesn't work for timestamps. This special cases when we have a simple
        // set that sets a const node target to a list of timestamps, as is the
        // case for PanelPlot zoom domain syncing. We set the result to
        // a list of timestamp constructor ops instead.
        // TODO: fix this generally. This issue is certainly broader than just the
        //   hack here. We need to know the correct type of mutation results, and we
        //   need a general way of converting objects to constructors op calls.
        if (
          actionName === 'set' &&
          isConstructor(absoluteTarget) &&
          isList(inputs.val.type) &&
          isTimestamp(inputs.val.type.objectType)
        ) {
          newRootNode = opList({
            a: opTimestamp({
              timestampISO: constString(
                new Date(newRootNode.val[0]).toISOString()
              ),
            }),
            b: opTimestamp({
              timestampISO: constString(
                new Date(newRootNode.val[1]).toISOString()
              ),
            }),
          } as any);
        }

        if (getChainRootVar(target) != null) {
          consoleLog('CLIENT REF VAR CHAIN ROOT STARTING');
          triggerExpressionEvent(
            target,
            {
              id: 'mutate',
              newRootNode,
            },
            'chain',
            'root'
          );
        } else {
          if (handleRootUpdate != null) {
            handleRootUpdate(newRootNode);
          }
        }
      } else if (mutationStyle === 'serverRef') {
        consoleLog('FINAL', final);
        if (typeof final !== 'string' || !final.includes('://')) {
          throw new Error('Unexpected mutation result');
        }
        const newRootNode = {
          nodeType: 'output' as const,
          type: rootType,
          fromOp: {name: 'get' as const, inputs: {uri: constString(final)}},
        };
        if (getChainRootVar(target) != null) {
          triggerExpressionEvent(
            target,
            {
              id: 'mutate',
              newRootNode,
            },
            'chain',
            'root'
          );
        } else {
          if (handleRootUpdate != null) {
            handleRootUpdate(newRootNode);
          }
        }
      }

      // refreshAll so that queries rerun.
      //
      // Actually, don't do this! UI changes should already by in the DOM,
      // mutations just persist them back to the original object.
      //
      // If we find we need something like this, it needs to be more selective.
      // It should definitely not happen when we use a mutation to update a panel
      // document.
      //
      // refreshAll();

      // We actually get the mutated object back right now.
      // But don't send this to the user! For one reason, we shouldn't
      // keep the behavior of sending the mutated object back. That could
      // be very expensive if it was a large object. But also, this would
      // encourage bad usage patterns by users! They don't need to know
      // The result of the mutation. They'll already be subscribed to viewing
      // the node or a parent of the node that we mutated somewhere up the
      // tree. That node will be notified of the change, and everything
      // will rerender automatically. The user does not need to worry about
      // how to apply the mutation results back to some user-held state
      // (unlike in graphql).
      return true;
    };

    if (
      actionName === 'set' &&
      mutationStyle === 'clientRef' &&
      inputs.val.nodeType === 'const'
    ) {
      const clientSetResult = clientSet(absoluteTarget, inputs.val.val);
      if (clientSetResult.ok) {
        return onDone(clientSetResult.value);
      }
    }

    // The first argument to any mutation is the target node. We need
    // to put it inside a const node so that it doesn't get
    // execute by the engine.
    const constTarget = constNodeUnsafe(
      toWeaveType(absoluteTarget),
      absoluteTarget
    );
    const rootArgsNode = constNodeUnsafe(toWeaveType(rootArgs), rootArgs);
    const calledNode = callOpVeryUnsafe(actionName, {
      self: constTarget,
      ...inputs,
      root_args: rootArgsNode,
    });

    return client.action(calledNode as any).then(onDone);
  };
};

export const makeMutation = (
  target: NodeOrVoidNode,
  actionName: string,
  refreshAll: () => Promise<void>,
  stack: Stack,
  triggerExpressionEvent: ReturnType<
    typeof usePanelContext
  >['triggerExpressionEvent'],
  absoluteTarget: NodeOrVoidNode,
  mutationStyle: string,
  rootArgs: {[key: string]: any},
  rootType: Type,
  client: Client,
  handleRootUpdate?: (newRoot: Node) => void
) => {
  const action = makeCallAction(
    actionName,
    absoluteTarget,
    target,
    stack,
    triggerExpressionEvent,
    mutationStyle,
    rootArgs,
    rootType,
    refreshAll,
    handleRootUpdate
  );
  return (inputs: OpInputs) => action(client, inputs);
};

export const useMakeMutation = () => {
  const refreshAll = useRefreshAllNodes();
  const {stack, triggerExpressionEvent} = usePanelContext();
  const {client} = useClientContext();
  return useCallback(
    async (
      target: NodeOrVoidNode,
      actionName: string,
      inputs: OpInputs,
      handleRootUpdate?: (newRoot: Node) => void
    ) => {
      if (client) {
        const absoluteTarget = dereferenceAllVars(target, stack).node;
        const {rootArgs, mutationStyle, rootType} =
          absoluteTargetMutation(absoluteTarget);
        const newDashMutation = makeMutation(
          target,
          actionName,
          refreshAll,
          stack,
          triggerExpressionEvent,
          absoluteTarget,
          mutationStyle,
          rootArgs,
          rootType,
          client,
          handleRootUpdate
        );
        await newDashMutation(inputs);
      }
    },
    [client, refreshAll, stack, triggerExpressionEvent]
  );
};

export const useMutation = (
  target: NodeOrVoidNode,
  actionName: string,
  handleRootUpdate?: (newRoot: Node) => void,
  ignoreNullResult: boolean = true
) => {
  const refreshAll = useRefreshAllNodes();
  const {stack, triggerExpressionEvent} = usePanelContext();
  const absoluteTarget = useMemo(
    () => dereferenceAllVars(target, stack).node,
    [target, stack]
  );

  const {rootArgs, mutationStyle, rootType} = useMemo(
    () => absoluteTargetMutation(absoluteTarget),
    [absoluteTarget]
  );

  const callAction = useMemo(
    () =>
      makeCallAction(
        actionName,
        absoluteTarget,
        target,
        stack,
        triggerExpressionEvent,
        mutationStyle,
        rootArgs,
        rootType,
        refreshAll,
        handleRootUpdate,
        ignoreNullResult
      ),
    [
      absoluteTarget,
      actionName,
      stack,
      handleRootUpdate,
      mutationStyle,
      refreshAll,
      rootArgs,
      rootType,
      target,
      triggerExpressionEvent,
      ignoreNullResult,
    ]
  );
  return useClientBound(callAction);
};

export const useRefreshAllNodes = () => {
  const context = useClientContext();
  const client = context.client;
  return useCallback(async () => {
    if (client != null) {
      await client.refreshAll();
    }
  }, [client]);
};

export const useClientBound = <T extends any[], R>(
  fn: (client: Client, ...rest: T) => R
): ((...args: T) => R) => {
  const client = useClientContext().client;
  if (client == null) {
    throw new Error('CG context not initialized');
  }
  return useCallback((...args: T) => fn(client, ...args), [client, fn]);
};

// Given an array node, return a set of nodes, one for
// each item in the array.  To avoid N+1 queries, we
// pre-fetch some default amount and then update with the
// actual count eventually.
// TODO: in the future it would be cool to move this logic down,
//   it doesn't need to depend on react hooks.
export const useEach = (
  node: Node<{type: 'list'; objectType: 'any'}>,
  defaultCount = 10
) => {
  const countNode = useMemo(() => opCount({arr: node}), [node]);
  const {result: countValue} = useNodeValue(countNode);
  const result = useMemo(
    () => ({
      loading: false,
      result: _.range(countValue ?? defaultCount).map(i =>
        opIndex({arr: node, index: constNumber(i)})
      ),
    }),
    [countValue, defaultCount, node]
  );

  return result;
};

export const useSimplifiedNode = (node: Node) => {
  node = useDeepMemo(node);
  const context = useClientContext();
  const [result, setResult] = useState<
    {loading: true} | {loading: false; result: Node}
  >({loading: true});
  useEffect(() => {
    setResult({loading: true});
    const doSimplify = async () => {
      const simpler = await simplify(context.client!, node);
      setResult({loading: false, result: simpler});
    };
    doSimplify();
  }, [context.client, node]);
  return result;
};

// This returns the node original node, and subset of the stack needed by
// Node. Results will be reference equal to the prior call if there are no changes.
export const useRefEqualExpr = (node: NodeOrVoidNode, stack: Stack) => {
  const {node: dereffedNode, usedStack: minimalStack} = dereferenceAllVars(
    node,
    stack
  );
  const memoedNode = useDeepMemo(node);
  const memoedDereffedNode = useDeepMemo(dereffedNode);
  const memoedStack = useDeepMemo(minimalStack);
  return useMemo(
    () => ({
      node: memoedNode,
      dereffedNode: memoedDereffedNode,
      stack: memoedStack,
    }),
    [memoedDereffedNode, memoedNode, memoedStack]
  );
};

export const useRefEqualWithoutTypes = (node: NodeOrVoidNode) => {
  const compareNodesWithoutTypes = (
    a: NodeOrVoidNode,
    b: NodeOrVoidNode | undefined
  ): boolean => {
    if (b == null) {
      return false;
    }
    if (a.nodeType === 'void' && b.nodeType === 'void') {
      return true;
    } else if (a.nodeType === 'var' && b.nodeType === 'var') {
      if (a.varName !== b.varName) {
        return false;
      }
      return true;
    } else if (a.nodeType === 'const' && b.nodeType === 'const') {
      if (isNodeOrVoidNode(a.val) && isNodeOrVoidNode(b.val)) {
        return compareNodesWithoutTypes(a.val, b.val);
      }
      if (a.val !== b.val) {
        return false;
      }
      return true;
    } else if (a.nodeType === 'output' && b.nodeType === 'output') {
      if (a.fromOp.name !== b.fromOp.name) {
        return false;
      }
      const aKeys = Object.keys(a.fromOp.inputs);
      const bKeys = Object.keys(b.fromOp.inputs);
      if (aKeys.length !== bKeys.length) {
        return false;
      }
      for (const key of aKeys) {
        if (
          !compareNodesWithoutTypes(a.fromOp.inputs[key], b.fromOp.inputs[key])
        ) {
          return false;
        }
      }
      return true;
    }
    return false;
  };
  return useDeepMemo(node, compareNodesWithoutTypes);
};

// This is exported because we need it in one place: PagePanel
// needs to load the type of it's input expression before it can render
// a child. We can remove that callsite too once we ensure PagePanel
// always has the initial type information it needs to continue loading.
export const useNodeWithServerTypeDoNotCallMeDirectly = (
  node: NodeOrVoidNode,
  paramFrame?: Frame
): {loading: boolean; result: NodeOrVoidNode} => {
  const stack = usePanelContext().stack;
  if (paramFrame != null) {
    for (const [name, value] of Object.entries(paramFrame)) {
      stack.splice(0, 0, {name, value});
    }
  }
  const [error, setError] = useState();
  let dereffedNode: NodeOrVoidNode;
  ({node, dereffedNode} = useRefEqualExpr(node, stack));

  node = useRefEqualWithoutTypes(node);
  dereffedNode = useRefEqualWithoutTypes(dereffedNode);

  const [result, setResult] = useState<{
    node: NodeOrVoidNode;
    value: any;
  }>({node: voidNode(), value: undefined});
  const weave = useWeaveContext();

  const promiseRef = useRef<Promise<any> | null>(null);
  useEffect(() => {
    let isMounted = true;
    if (node.nodeType === 'const') {
      setResult({node, value: node});
    }
    if (node.nodeType === 'void') {
      return;
    }
    const p = weave
      .refineNode(dereffedNode as any, [])
      .then(newNode => {
        if (promiseRef.current !== p) {
          // Stale, discard
          return;
        }
        if (isMounted) {
          setResult({node, value: {...node, type: newNode.type}});
        }
      })
      .catch(e => setError(e));
    promiseRef.current = p;
    return () => {
      isMounted = false;
    };
  }, [weave, node, dereffedNode]);

  const finalResult = useMemo(() => {
    if (error != null) {
      // rethrow in render thread
      const message =
        'Node execution failed (useNodeWithServerType): ' + errorToText(error);
      // console.error(message);
      throw new Error(message);
    }
    return {
      loading: node !== result.node,
      result: node === result.node ? result.value : node,
    };
  }, [result, node, error]);
  return finalResult;
};

// Non-dashUI Weave use this during the render cycle in some panels, to get
// up to date type information. That is a problem because it blocks loading
// and causes sequences of data loading requests instead of rolling them all up into
// one shot. In dashUi, we refine as needed upon panel construction or user action
// instead of during rendering.
export const useNodeWithServerType: typeof useNodeWithServerTypeDoNotCallMeDirectly =
  (node, paramFrame) => {
    const disableRefinement = useWeaveRefinementInReactHooksDisabled();
    // In dashUI, no-op. We manage document refinement in panelTree
    if (disableRefinement) {
      return {
        initialLoading: false,
        loading: false,
        result: node,
      };
    }

    // We can ignore this, dashUi is a feature flag that doesn't change during a session
    // eslint-disable-next-line react-hooks/rules-of-hooks
    return useNodeWithServerTypeDoNotCallMeDirectly(node, paramFrame);
  };

export const useExpandedNode = (
  node: NodeOrVoidNode
): {loading: boolean; result: NodeOrVoidNode} => {
  const [error, setError] = useState();
  const {stack} = usePanelContext();

  let dereffedNode: NodeOrVoidNode;
  ({node, dereffedNode} = useRefEqualExpr(node, stack));

  node = useDeepMemo(node);
  const [result, setResult] = useState<{
    node: NodeOrVoidNode;
    value: any;
  }>({node: voidNode(), value: undefined});
  const context = useClientContext();
  useEffect(() => {
    let isMounted = true;
    if (node.nodeType !== 'output') {
      return;
    }
    // TODO: This is a race if we have multiple loading in parallel!
    expandAll(context.client!, dereffedNode, [])
      .then(newNode => {
        if (isMounted) {
          setResult({node, value: newNode});
        }
      })
      .catch(e => setError(e));
    return () => {
      isMounted = false;
    };
  }, [context, node, dereffedNode]);
  const finalResult = useMemo(() => {
    if (error != null) {
      // rethrow in render thread
      console.error('useExpanded error', error);
      throw new Error(error);
    }
    return {
      loading: node.nodeType !== 'output' ? false : node !== result.node,
      result:
        node.nodeType !== 'output'
          ? node
          : node === result.node
          ? result.value
          : node,
    };
  }, [result, node, error]);
  return finalResult;
};
type NodeDebugInfoInputType = {[name: string]: NodeDebugInfoType | null};
type NodeDebugInfoType = {
  node?: NodeOrVoidNode;
  nodeString?: string;
  refinedNode?: NodeOrVoidNode;
  refineError?: any;
  nodeValue?: any;
  valueError?: any;
  inputs?: NodeDebugInfoInputType;
  invalidators?: ReturnType<typeof getInvalidatorNodesWithInfo>;
};

function getInvalidatorNodesWithInfo(node: EditingNode, weave: WeaveInterface) {
  const invalidators = getInvalidators(node);

  if (!invalidators) {
    return undefined;
  }

  return invalidators.map(invalidatorNode => {
    let invalidatedBy:
      | {
          [inputName: string]: {
            expectedType: Type;
            actualValue: EditingNode;
          };
        }
      | undefined;
    if (invalidatorNode.nodeType === 'output') {
      const opDef = weave.client.opStore.getOpDef(invalidatorNode.fromOp.name);
      invalidatedBy = Object.fromEntries(
        Object.entries(invalidatorNode.fromOp.inputs)
          .filter(
            ([inputName, value]) =>
              !isAssignableTo(value.type, opDef.inputTypes[inputName])
          )
          .map(([inputName, value]) => [
            inputName,
            {
              expectedType: opDef.inputTypes[inputName],
              actualValue: value,
            },
          ])
      );
    }

    return {
      node: invalidatorNode,
      invalidatedBy,
    };
  });
}
function getInvalidators(node: EditingNode): null | EditingNode[] {
  if (node.type !== 'invalid') {
    return null;
  }

  if (isFunctionLiteral(node)) {
    return getInvalidators(node.val);
  }
  if (node.nodeType !== 'output') {
    return [node];
  }

  const invalidInputs = Object.values(node.fromOp.inputs).filter(
    input => input.type === 'invalid'
  );

  if (invalidInputs.length === 0) {
    // if we have no invalid inputs, then this is an invalidating node
    return [node];
  }

  return _.compact(invalidInputs.flatMap(getInvalidators));
}

async function makeDebugNode(
  weave: WeaveInterface,
  node: NodeOrVoidNode
): Promise<NodeDebugInfoType> {
  const result = {
    node,
    nodeString: weave.expToString(node),
  };

  if (weave.client == null) {
    throw new Error('client not initialized!');
  }
  if (node.nodeType === 'void') {
    return Promise.resolve(result);
  } else {
    return new Promise(async resolve => {
      weave
        .refineNode(node, [])
        .then(async refinedNode => {
          const invalidators = getInvalidatorNodesWithInfo(refinedNode, weave);
          // From Shawn: I removed strip tags = false here. Sorry,
          // I want to make sure we never rely on strip tags in production
          // code, so the client doesn't even allow it anymore. To bring
          // it back, I think it'd be ok to have a client._queryDebug that
          // does it... this would need to be routed through to the server.
          const nodeValue = await weave.client.query(node);
          if (node.nodeType === 'output') {
            const keys = _.keys(node.fromOp.inputs);
            const inputNodes = await Promise.all(
              keys.map(key => makeDebugNode(weave, node.fromOp.inputs[key]))
            );
            const inputs = _.fromPairs(
              keys.map((key, ndx) => [key, inputNodes[ndx]])
            );

            resolve({
              ...result,
              refinedNode,
              nodeValue,
              inputs,
              invalidators,
            });
          } else {
            resolve({
              ...result,
              refinedNode,
              nodeValue,
              invalidators,
            });
          }
        })
        .catch(refineError => {
          resolve({
            ...result,
            refineError,
          });
        });
    });
  }
}

// Warning: Only use for debugging - costly and inefficient.
export function useNodeDebugInfo(node: NodeOrVoidNode): {
  loading: boolean;
  result: NodeDebugInfoType | null;
} {
  const weave = useWeaveContext();
  const [result, setResult] = useState<NodeDebugInfoType | null>();
  node = useDeepMemo(node);

  useEffect(() => {
    makeDebugNode(weave, node).then(setResult);
  }, [weave, node, setResult]);

  return useMemo(() => {
    if (result == null) {
      return {loading: true, result: null};
    } else {
      return {
        loading: false,
        result,
      };
    }
  }, [result]);
}
