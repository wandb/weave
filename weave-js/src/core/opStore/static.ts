// Compute graph representation and execution
//
// Contains low-level functions for constructing & executing a compute graph.
//

import {mapValues} from 'lodash';

import callFunction from '../callers';
import {newRefForwardGraph} from '../engine/forwardGraph';
import {executeSync} from '../executeSync';
import {constNode, constType} from '../model/graph/construction';
import {
  isConstNode,
  outputTypeIsExecutable,
  outputTypeIsFunctionNode,
  outputTypeIsType,
} from '../model/graph/typeHelpers';
import type {
  InputTypes,
  Node,
  NodeOrVoidNode,
  OpCachePolicy,
  OpInputNodes,
  OpInputs,
  OutputNode,
  TypeFn,
} from '../model/graph/types';
import {dict, isConstType} from '../model/helpers';
import type {Type} from '../model/types';
import {ExpansionFunction, MakeOpDefOpts, OpDef, OpStore} from './types';
import {validateOpStore} from './validation';

const defaultCachePolicy: OpCachePolicy = {
  ttlSeconds: 30,
};

const replaceConstTypeWithNode = (inputs: OpInputs): OpInputs => {
  return mapValues(inputs, input => {
    if (isConstType(input.type)) {
      return constNode(input.type.valType, input.type.val);
    }
    return input;
  });
};

/**
 * OpDefs can have 3 different flavors of return type (a static type, a type
 * that is a typescript function of it's inputs, or a type that is a weave
 * function of it's inputs). This function determines the correct type based on
 * the opDef and the inputs.
 */

export const determineOutputType = (opDef: OpDef, inputs: OpInputs): Type => {
  let type: Type = 'any';
  if (outputTypeIsExecutable(opDef.outputType)) {
    // If we have a ConstType, replace the input node with a const node
    // as weave js doesn't support ConstType as an input type, but treats
    // const nodes like const types.
    inputs = replaceConstTypeWithNode(inputs);
    type = opDef.outputType(inputs);
  } else if (outputTypeIsFunctionNode(opDef.outputType)) {
    type = executeNodeSync(
      callFunction(opDef.outputType.val, {
        // @ts-ignore
        input_types: constNode(
          dict('type'),
          mapValues(inputs, inputNodeToType)
        ),
      })
    );
    if (type == null) {
      return 'unknown';
    }
    if (isConstType(type)) {
      if (type.valType === 'type') {
        type = type.val;
      } else {
        type = type.valType;
      }
    }
  } else if (outputTypeIsType(opDef.outputType)) {
    type = opDef.outputType;
  } else {
    throw new Error('Invalid output type');
  }
  return type;
};

const inputNodeToType = (node: Node): Type => {
  // TODO: TS: This is a delta between PY and TS
  // Sometimes the input node itself is a const node,
  // And that const node could be a type itself, or a value
  // so we need to handle each case
  if (isConstNode(node)) {
    if (isConstType(node.type)) {
      return node.type;
    } else {
      // @ts-ignore
      return constType(node.val, node.type);
    }
  }
  return constType(node.type, 'type');
};

/**
 * `executeNodeSync` allows users to quickly execute Weave Nodes in a
 * synchronous manner. It is limited to ops defined in TS and must only consist
 * of synchronous resolvers. The cache is not shared between calls
 */

export const executeNodeSync = (node: NodeOrVoidNode): any => {
  if (node.nodeType === 'void') {
    return null;
  }
  const forwardGraph = newRefForwardGraph();
  forwardGraph.update(node);
  return executeSync(
    node,
    new Map(),
    forwardGraph,
    StaticOpStore.getInstance()
  );
};

export class BaseOpStore implements OpStore {
  protected registeredOps: {
    [name: string]: OpDef;
  };

  constructor() {
    this.registeredOps = {};
  }

  allOps = () => this.registeredOps;

  getOpDef(name: string): OpDef {
    const opDef = this.registeredOps[name];
    if (opDef == null) {
      console.log(`not found`, name, this.registeredOps);
      throw new Error('op not registered: ' + name);
    }
    return opDef;
  }

  registerOp(op: OpDef): void {
    if (this.registeredOps[op.name] != null) {
      console.warn(
        `programming error: double registered op ${op.name} (is this a duplicate?)`
      );
    }
    this.registeredOps[op.name] = {
      ...op,
      cachePolicy: op.cachePolicy != null ? op.cachePolicy : defaultCachePolicy,
    };
    validateOpStore(this, op);
  }

  makeOp<RT extends Type, I extends InputTypes>(
    opts: MakeOpDefOpts<RT, I>
  ): (inputs: OpInputNodes<I>) => OutputNode<RT> {
    const {
      name: opName,
      argTypes: inputTypes,
      returnType,
      renderInfo,
      resolver,
      resolveOutputType,
      hidden,
      kind,
      cachePolicy,
    } = opts;
    if (!opName.startsWith('local-artifact') && opName.split('-').length > 2) {
      throw new Error(`Op name ${opName} cannot contain more than 1 dash`);
    }
    let {
      description,
      argDescriptions,
      returnValueDescription,
      supportedEngines,
    } = opts;

    if (description == null) {
      if (!hidden) {
        throw new Error('op description is required for non-hidden ops');
      } else {
        description = 'HIDDEN OP';
      }
    }

    if (argDescriptions == null) {
      if (!hidden) {
        throw new Error('op argDescriptions is required for non-hidden ops');
      } else {
        argDescriptions = mapValues(inputTypes, () => 'HIDDEN OP');
      }
    }

    if (returnValueDescription == null) {
      if (!hidden) {
        throw new Error(
          'op returnValueDescription is required for non-hidden ops'
        );
      } else {
        returnValueDescription = 'HIDDEN OP';
      }
    }

    if (supportedEngines == null) {
      // Assume only ts
      supportedEngines = new Set(['ts']);
    }

    const opDefInternal: Partial<OpDef> = {
      name: opName,
      inputTypes,
      outputType: returnType as any,
      renderInfo: renderInfo || {type: 'chain'},
      description,
      argDescriptions,
      returnValueDescription,
      supportedEngines,
      refineNode: resolveOutputType,
      hidden,
      kind,
      cachePolicy,
    };

    const opFn = (inputs: OpInputNodes<I>): OutputNode<RT> => {
      const type = determineOutputType(opDefInternal as OpDef, inputs) as RT;
      const result = {
        nodeType: 'output' as const,
        type,
        fromOp: {
          name: opName,
          inputs,
        },
      };
      return result;
    };
    const res =
      resolver ??
      ((inputs: any) => {
        throw new Error('resolver not implemented for ' + opName);
      });
    opDefInternal.op = opFn;
    opDefInternal.resolver = res;
    this.registerOp(opDefInternal as OpDef);

    return opFn;
  }

  debugMeta(): {id: string} & {[prop: string]: any} {
    return {id: 'BaseOpStore'};
  }
}

/**
 * In most cases, the OpStore instance does not need to be used directly.
 * Instead most functions are proxied by the weave interface in react components
 * using `useWeaveContext`. However, for lower-level use cases, you will want to
 * use the appropriate opStore based on the circumstance. In the case that you
 * specifically want to use the hard-coded Typescript ops, you can use this
 * class directly. To get the OpStore, use StaticOpStore.getInstance().
 */
export class StaticOpStore extends BaseOpStore {
  public static getInstance() {
    return this.instance || (this.instance = new this());
  }
  private static instance: StaticOpStore;

  private constructor() {
    super();
    if (StaticOpStore.instance) {
      throw new Error(
        'Error: Instantiation failed: Use SingletonClass.getInstance() instead of new.'
      );
    }
    this.registeredOps = {};
    StaticOpStore.instance = this;
  }
  registerOp(op: OpDef): void {
    super.registerOp(op);
    // HACK: This op was supposed to be inaccessible/unused inside of user expressions
    // but some people managed to find a way.  To tolerate the old name, we map it
    // to boolean-not.  Since the opDef itself uses the new name, upon serialization it should
    // be updated to the new name.
    if (op.name === 'boolean-not') {
      this.registeredOps.not = this.registeredOps['boolean-not'];
    }
  }
  debugMeta(): {id: string} & {[prop: string]: any} {
    return {id: 'StaticOpStore'};
  }
}

// WARNING: Ops registered with this function are not guaranteed to be available
// by the time downstream clients request such op. In practice this is fine, since
// it is only used by the PanelOps code which is feature flagged and likely to change
// in terms of design.
export function registerGeneratedWeaveOp<IT extends InputTypes>(opts: {
  name: string;
  inputTypes: InputTypes;
  outputType: Type | TypeFn<IT, Type>;
  expansionFn: ExpansionFunction;
}) {
  const {name, inputTypes, outputType, expansionFn} = opts;
  StaticOpStore.getInstance().registerOp({
    name,
    inputTypes,
    outputType: outputType as Type | TypeFn<InputTypes, Type>,
    renderInfo: {
      type: 'chain',
    },
    expansion: expansionFn,
    // TODO: allow these to be passed in by panels. Note:
    // keeping this excluded for now as panel ops will likely
    // change this soon.
    description: '',
    argDescriptions: {},
    returnValueDescription: '',
    cachePolicy: defaultCachePolicy,
    // Assume only ts
    supportedEngines: new Set(['ts']),
  });
}

// This is just a proxy function to reduce refactor costs. Note: this should ONLY be used
// in the `/ops` directory since it is known to be pre-loaded.
export function makeOp<RT extends Type, I extends InputTypes>(
  opts: MakeOpDefOpts<RT, I>
): (inputs: OpInputNodes<I>) => OutputNode<RT> {
  return StaticOpStore.getInstance().makeOp(opts);
}
