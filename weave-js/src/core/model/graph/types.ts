import type {
  MediaTable,
  Molecule,
  Object3D,
  WBAudio,
  WBBokeh,
  WBHtml,
  WBImage,
  WBVideo,
} from '../media';
import {WBTraceTree} from '../media/traceTree';
import type {
  AudioType,
  BokehType,
  ConstType,
  Dict,
  Dir,
  DirMetadata,
  File,
  FunctionType,
  FunctionTypeSpecific,
  Histogram,
  HtmlType,
  ImageType,
  Link,
  ListType,
  MoleculeType,
  NewRun,
  NewRunType,
  Object3DType,
  TableType,
  TimestampType,
  Type,
  TypedDictType,
  Union,
  VideoType,
  WandbArtifactRef,
  WBTraceTreeType,
} from '../types';

// All nodes have a type (using our run-time type system).
export interface BaseNode<T extends Type> {
  type: T;
}

// Ops always produce a single output-node.
export interface OutputNode<T extends Type = Type> extends BaseNode<T> {
  nodeType: 'output';
  fromOp: Op;

  // Server-side only
  id?: string;
}

// A variable node just has a name
export interface VarNode<T extends Type = Type> extends BaseNode<T> {
  nodeType: 'var';
  varName: string;
}

// A variable node stores its value
export interface ConstNode<T extends Type = Type> extends BaseNode<T> {
  nodeType: 'const';
  val: TypeToTSTypeInner<T>;
}

export type Node<T extends Type = Type> =
  | OutputNode<T>
  | ConstNode<T>
  | VarNode<T>;

// A void node represents nothing. It's just used to indicate the lack
// of any node in certain UI circumstances.
export interface VoidNode extends BaseNode<'invalid'> {
  nodeType: 'void';
}

export type NodeOrVoidNode<T extends Type = Type> = Node<T> | VoidNode;
export type OpInputs = {[key: string]: Node};

export interface Op {
  name: string;
  inputs: OpInputs;
}
// Note, we just use anys here, because these are just stored in the registry
// which is used at runtime. Its not very helpful to have compile-time type
// info here.
export type OpFn = (inputs: OpInputNodes<any>) => OutputNode<Type>;

export type OpInputNodes<I extends InputTypes> = {
  [K in keyof I]: Node<I[K]>;
};

export type OpResolverInputTypes<I extends InputTypes> = {
  [K in keyof I]: TypeToTSTypeInner<I[K]>;
};

export type TypeFn<IT extends InputTypes, RT extends Type> = (
  op: OpInputNodes<IT>
) => RT;

export type ReturnTypeFn = (inputs: OpInputNodes<InputTypes>) => Type;

export type InputTypes = {[key: string]: Type};

export type OutputTypeAsNode<IT extends InputTypes> = ConstNode<
  FunctionTypeSpecific<IT, 'type'>
>;
export type OutputTypeGeneric<IT extends InputTypes, RT extends Type> =
  | RT
  | TypeFn<IT, RT>
  | OutputTypeAsNode<IT>;
export type OutputType = OutputTypeGeneric<InputTypes, Type>;

/**
 * How we'll represent the op visually.
 *
 * function: opName(arg0Value, arg1Value, ...)
 * chain: arg0Value.opName(arg1Value, arg2Value, ...)
 * getAttr: arg0Value.arg1Value
 * brackets: arg0Value[arg1Value]
 * binary: arg0Value repr arg1Value
 * boolean comb: arg0Value opName arg1Value opName arg2Value ...
 * dictionary literal: {arg1Name: arg1Value, arg2Name: arg2Value, ...}
 * array literal: [val1, val2, ...]
 */
export type OpRenderInfo =
  | {
      type:
        | 'function'
        | 'chain'
        | 'getAttr'
        | 'brackets'
        | 'dictionaryLiteral'
        | 'arrayLiteral';
    }
  | {
      type: 'binary';
      repr: string;
    }
  | {
      type: 'unary';
      repr: string;
    };

/**
 * Define cacheability of op results
 */
export interface OpCachePolicy {
  // 0 = Don't cache; -1 = cache default/"forever"
  ttlSeconds: number;
}

export type SupportedEnginesType = Set<'ts' | 'py'>;

/// // Op registration.
//
// The following types are used to represent available
// ops, their resolvers, and other information we need to execute them.

// A fully defined op, that we can call on input nodes and execute.
// Think of it like a function definition.
export interface OpDefBase {
  name: string;

  // argument specification
  inputTypes: InputTypes;

  // return type (may be a function of arguments)
  outputType: OutputType;

  /**
   * what type of visual representation is used for this op (is it binary,
   * a function call, etc.)
   *
   * the default is {type: "chain"}
   */
  renderInfo: OpRenderInfo;

  // Is the op available to users?
  hidden?: boolean;

  // Internal kind, we should not switch on this, its just used for
  // understanding ops when looking at the __registry
  kind?: string;

  cachePolicy?: OpCachePolicy;

  /**
   * An optional high-level, user-facing description of the op in markdown.
   */
  description: string;

  /**
   * Takes in concrete input types and returns an object mapping argument names to their
   * descriptions in markdown
   *
   * This function will *usually* just return a literal, but making it dynamic puts us
   * in a good position when/if we overhaul the argument system to better understand generics.
   */
  argDescriptions: {
    [argName: string]: string;
  };

  /**
   * A function that takes in a concrete output type and returns a description of the output
   * in markdown.
   */
  returnValueDescription: string;

  /**
   * Denotes the list of supported engines. For now, `ts` or `py`. However, we
   * may want to make this more robust once we support different module
   * providers. We should probably have the backend report its engine type and
   * version, then use these to determine control flow for downstream logic
   */
  supportedEngines: SupportedEnginesType;
}

export type ExpansionRefineNodeCallback = (node: Node) => Promise<Node>;

export interface Frame {
  [varName: string]: NodeOrVoidNode;
}

export type Expression = NodeOrVoidNode;

export interface Definition {
  name: string;
  value: Expression;
}

export type Stack = Definition[];

export interface Closure {
  stack: Stack;
  value: Expression;
}

// Convert a Type.Type to an actual Typescript type that matches it!
export type TypeToTSTypeInner<T> = T extends 'any'
  ? any
  : T extends WandbArtifactRef
  ? any // TODO
  : T extends 'user'
  ? any // TODO
  : T extends 'project'
  ? any // TODO
  : T extends 'entity'
  ? any // TODO
  : T extends 'run'
  ? any // TODO
  : T extends 'artifactType'
  ? any // TODO
  : T extends 'artifact'
  ? any // TODO
  : T extends 'artifactVersion'
  ? any // TODO
  : T extends 'artifactAlias'
  ? any
  : T extends 'artifactMembership'
  ? any // TODO
  : T extends 'filter'
  ? any // TODO
  : T extends 'runQueue'
  ? any // TODO
  : T extends 'histogram'
  ? Histogram // TODO
  : T extends 'link'
  ? Link
  : T extends 'id'
  ? string
  : T extends 'string'
  ? string
  : T extends 'number'
  ? number
  : T extends 'boolean'
  ? boolean
  : T extends 'none'
  ? null
  : T extends 'date'
  ? Date
  : T extends 'unknown'
  ? unknown
  : T extends 'type'
  ? Type
  : T extends ConstType
  ? T['val']
  : T extends FunctionTypeSpecific<any, infer RT>
  ? Node<RT> | VoidNode
  : T extends FunctionType
  ? Node<T['outputType']>
  : T extends ImageType
  ? WBImage
  : T extends VideoType
  ? WBVideo
  : T extends AudioType
  ? WBAudio
  : T extends HtmlType
  ? WBHtml
  : T extends BokehType
  ? WBBokeh
  : T extends Object3DType
  ? Object3D
  : T extends MoleculeType
  ? Molecule
  : T extends TableType
  ? MediaTable
  : T extends WBTraceTreeType
  ? WBTraceTree
  : T extends File
  ? {artifact?: {id: string}; path: string}
  : T extends Dir
  ? DirMetadata
  : T extends TimestampType
  ? number
  : T extends TypedDictType
  ? {
      [K in keyof T['propertyTypes']]: TypeToTSTypeInner<T['propertyTypes'][K]>;
    }
  : T extends NewRunType
  ? NewRun
  : T extends Dict
  ? DictTSType<T['objectType']>
  : T extends ListType
  ? ListTSType<T['objectType']>
  : T extends Union // Use a mapped type to distribute TypeToTSType over the members array, // then use [number] lookup on the array to get a union, which produces // a union of the array's members. (this basically says "give me the type // that would result from indexing the array with any number").
  ? {
      [K in keyof T['members']]: TypeToTSTypeInner<T['members'][K]>;
    }[number]
  : never;

export type DictTSType<T> = {[key: string]: TypeToTSTypeInner<T>};

export type ListTSType<T> = Array<TypeToTSTypeInner<T>>;
