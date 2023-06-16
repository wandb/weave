import * as _ from 'lodash';

import type {Client} from '../client';
import type {ForwardGraph, ForwardOp} from '../engine/forwardGraph/types';
import type {Engine} from '../engine/types';
import {
  findNamedTagInType,
  findNamedTagInVal,
  getValueFromTaggedValue,
  InputTypes,
  ListType,
  mappableNullableTaggableVal,
  mntValueApply,
  nullableTaggableVal,
  OpInputNodes,
  OpRenderInfo,
  OpResolverInputTypes,
  OutputNode,
  Stack,
  Type,
  TypeProcessingConfig,
} from '../model';
import {
  concreteTaggedValue,
  isConcreteTaggedValue,
  isListLike,
  isTaggedValueLike,
  mappableNullable,
  mappableNullableTaggable,
  mappableNullableTaggableAsync,
  mappableNullableTaggableStrip,
  mappableNullableTaggableValAsync,
  mappableNullableVal,
  mappableStrip,
  mappableTaggableVal,
  maybe,
  mntTypeApply,
  mntTypeApplyAsync,
  mntTypeStrip,
  mntValueApplyAsync,
  nullable,
  nullableOneOrMany,
  nullableTaggable,
  nullableTaggableAsync,
  nullableTaggableStrip,
  nullableTaggableValAsync,
  nullableVal,
  taggableStrip,
  taggedValue,
  taggedValueTagType,
  taggedValueValueType,
  typedDict,
} from '../model';
import {makeOp} from '../opStore';
import type {ResolverContext} from '../resolverContext';

type ReturnTypeFn<InputType extends InputTypes> = (
  argTypes: InputType,
  inputs: OpInputNodes<InputTypes>
) => Type;

type ResolverFn<InputType extends InputTypes> = (
  inputs: OpResolverInputTypes<InputType>,
  inputTypes: InputType,
  rawInputs: OpResolverInputTypes<InputType>,
  forwardGraph: ForwardGraph,
  forwardOp: ForwardOp,
  context: ResolverContext,
  engine: () => Engine
) => Promise<any> | any;

type ResolveOutputTypeFn<InputType extends InputTypes> = (
  inputTypes: InputType,
  node: OutputNode,
  executableNode: OutputNode,
  client: Client,
  stack: Stack
) => Promise<Type>;

type MakeOpInputType<InputType extends InputTypes> = {
  [key in keyof InputType]: Type;
};

interface OpFnOpts<InputType extends InputTypes> {
  name: string;
  argTypes: InputType;
  returnType: ReturnTypeFn<InputType>;
  resolver: ResolverFn<InputType>;
  renderInfo?: OpRenderInfo;
  resolveOutputType?: ResolveOutputTypeFn<InputType>;
  hidden?: boolean;
  description?: string;
  argDescriptions?: {
    [key: string]: string;
  };
  returnValueDescription?: string;
  resolverIsSync?: boolean;
}

interface TagGetterOpFnOpts {
  name: string;
  tagName: string;
  tagType: Type;
  hidden?: boolean;
  description?: string;
  argDescriptions?: {obj: string};
  returnValueDescription?: string;
}

export type MakeOpFn<InputType extends InputTypes> = (
  opts: OpFnOpts<InputType>
) => (inputs: OpInputNodes<MakeOpInputType<InputType>>) => OutputNode<Type>;

export type MakeTaggingOpFn<InputType extends InputTypes> = (
  opts: OpFnOpts<InputType> & {
    // tagType: Type;
    // resolveTag: ResolveTagFn<InputType>;
  }
) => (inputs: OpInputNodes<MakeOpInputType<InputType>>) => OutputNode<Type>;

/// // Basic op: nullable, taggable

const makeBasicOpReturnType = <InputType extends InputTypes>(
  returnType: OpFnOpts<InputType>['returnType']
) => {
  return (inputNodes: OpInputNodes<InputTypes>) => {
    const arg0Name = Object.keys(inputNodes)[0];
    return nullableTaggable(inputNodes[arg0Name].type, t =>
      returnType(
        {
          // Note, specify first argument first to preserve ordering, since
          // we rely on object ordering sometimes.
          [arg0Name]: t,
          ..._.omit(
            _.mapValues(inputNodes, node => node.type),
            [arg0Name]
          ),
        } as any,
        inputNodes
      )
    );
  };
};

const makeBasicOpResolver =
  <InputType extends InputTypes>(
    resolver: ResolverFn<InputType>,
    resolverIsSync?: boolean
  ) =>
  (
    inputs: {[name: string]: any},
    forwardGraph: ForwardGraph,
    forwardOp: ForwardOp,
    context: ResolverContext,
    engine: () => Engine
  ) => {
    const arg0Name = Object.keys(inputs)[0];
    const inputTypes = _.mapValues(forwardOp.op.inputs, node => node.type);
    const mapper = resolverIsSync
      ? nullableTaggableVal
      : nullableTaggableValAsync;
    return mapper(inputs[arg0Name], (v: any) =>
      resolver(
        {
          [arg0Name]: v,
          ..._.mapValues(_.omit(inputs, [arg0Name]), getValueFromTaggedValue),
        } as any,
        {
          [arg0Name]: nullableTaggableStrip(inputTypes[arg0Name]),
          ..._.omit(inputTypes, [arg0Name]),
        } as any,
        inputs as any,
        forwardGraph,
        forwardOp,
        context,
        engine
      )
    );
  };

const makeBasicOpResolveOutputType =
  <InputType extends InputTypes>(refine: ResolveOutputTypeFn<InputType>) =>
  async (
    node: OutputNode,
    executableNode: OutputNode,
    client: Client,
    stack: Stack
  ) => {
    const inputNodes = node.fromOp.inputs;
    const arg0Name = Object.keys(inputNodes)[0];
    return {
      ...node,
      type: await nullableTaggableAsync(inputNodes[arg0Name].type, v =>
        refine(
          {
            // Note, specify first argument first to preserve ordering, since
            // we rely on object ordering sometimes.
            [arg0Name]: v,
            ..._.omit(
              _.mapValues(inputNodes, n => n.type),
              [arg0Name]
            ),
          } as any,
          node,
          executableNode,
          client,
          stack
        )
      ),
    };
  };

/// // Standard op: nullable, taggable, mappable

export const makeStandardOpReturnType = <InputType extends InputTypes>(
  returnType: OpFnOpts<InputType>['returnType']
) => {
  return (inputNodes: OpInputNodes<InputTypes>) => {
    const arg0Name = Object.keys(inputNodes)[0];
    return mappableNullableTaggable(inputNodes[arg0Name].type, t =>
      returnType(
        {
          // Note, specify first argument first to preserve ordering, since
          // we rely on object ordering sometimes.
          [arg0Name]: t,
          ..._.omit(
            _.mapValues(inputNodes, node => node.type),
            [arg0Name]
          ),
        } as any,
        inputNodes
      )
    );
  };
};

const makeStandardOpResolver =
  <InputType extends InputTypes>(
    resolver: ResolverFn<InputType>,
    resolverIsSync?: boolean
  ) =>
  (
    inputs: {[name: string]: any},
    forwardGraph: ForwardGraph,
    forwardOp: ForwardOp,
    context: ResolverContext,
    engine: () => Engine
  ) => {
    const inputKeys = Object.keys(inputs);
    const arg0Name = inputKeys[0];

    // Note we do it in this order, rather than using spread, because
    // we must preserve object key ordering!
    const newInputTypes: {[name: string]: Type} = {
      [arg0Name]: mappableNullableTaggableStrip(
        forwardOp.op.inputs[arg0Name].type
      ),
    };
    for (const key of inputKeys.slice(1)) {
      newInputTypes[key] = forwardOp.op.inputs[key].type;
    }

    // We must preserve object key order. The first key will be replaced
    // inside the callback below.
    const newInputs: {[name: string]: any} = {[arg0Name]: null};
    for (const key of inputKeys.slice(1)) {
      newInputs[key] = getValueFromTaggedValue(inputs[key]);
    }

    const mapper = resolverIsSync
      ? mappableNullableTaggableVal
      : mappableNullableTaggableValAsync;

    return mapper(inputs[arg0Name], v => {
      newInputs[arg0Name] = v;
      return resolver(
        newInputs as any,
        newInputTypes as any,
        inputs as any,
        forwardGraph,
        forwardOp,
        context,
        engine
      );
    });
  };

const makeStandardOpResolveOutputType =
  <InputType extends InputTypes>(refine: ResolveOutputTypeFn<InputType>) =>
  async (
    node: OutputNode,
    executableNode: OutputNode,
    client: Client,
    stack: Stack
  ) => {
    const inputNodes = node.fromOp.inputs;
    const arg0Name = Object.keys(inputNodes)[0];
    return {
      ...node,
      type: await mappableNullableTaggableAsync(inputNodes[arg0Name].type, v =>
        refine(
          {
            // Note, specify first argument first to preserve ordering, since
            // we rely on object ordering sometimes.
            [arg0Name]: v,
            ..._.omit(
              _.mapValues(inputNodes, n => n.type),
              [arg0Name]
            ),
          } as any,
          node,
          executableNode,
          client,
          stack
        )
      ),
    };
  };

/// // Configurable Standard Op

const makeConfigurableStandardOpReturnType = <InputType extends InputTypes>(
  returnType: OpFnOpts<InputType>['returnType'],
  typeConfig?: TypeProcessingConfig
) => {
  return (inputNodes: OpInputNodes<InputTypes>) => {
    const arg0Name = Object.keys(inputNodes)[0];
    return mntTypeApply(
      inputNodes[arg0Name].type,
      t =>
        returnType(
          {
            // Note, specify first argument first to preserve ordering, since
            // we rely on object ordering sometimes.
            [arg0Name]: t,
            ..._.omit(
              _.mapValues(inputNodes, node => node.type),
              [arg0Name]
            ),
          } as any,
          inputNodes
        ),
      typeConfig
    );
  };
};

const makeTagConsumingStandardOpReturnType = <InputType extends InputTypes>(
  returnType: OpFnOpts<InputType>['returnType']
) => makeConfigurableStandardOpReturnType(returnType, {tags: true});

const makeConfigurableStandardOpResolver =
  <InputType extends InputTypes>(
    resolver: ResolverFn<InputType>,
    typeConfig?: TypeProcessingConfig,
    resolverIsSync?: boolean
  ) =>
  (
    inputs: {[name: string]: any},
    forwardGraph: ForwardGraph,
    forwardOp: ForwardOp,
    context: ResolverContext,
    engine: () => Engine
  ) => {
    const inputKeys = Object.keys(inputs);
    const arg0Name = inputKeys[0];

    // Note we do it in this order, rather than using spread, because
    // we must preserve object key ordering!
    const newInputTypes: {[name: string]: Type} = {
      [arg0Name]: mntTypeStrip(forwardOp.op.inputs[arg0Name].type, typeConfig),
    };
    for (const key of inputKeys.slice(1)) {
      newInputTypes[key] = forwardOp.op.inputs[key].type;
    }

    // We must preserve object key order. The first key will be replaced
    // inside the callback below.
    const newInputs: {[name: string]: any} = {[arg0Name]: null};
    for (const key of inputKeys.slice(1)) {
      newInputs[key] = getValueFromTaggedValue(inputs[key]);
    }
    const mapper = resolverIsSync ? mntValueApply : mntValueApplyAsync;
    return mapper(
      inputs[arg0Name],
      v => {
        newInputs[arg0Name] = v;
        return resolver(
          newInputs as any,
          newInputTypes as any,
          inputs as any,
          forwardGraph,
          forwardOp,
          context,
          engine
        );
      },
      typeConfig
    );
  };

const makeTagConsumingStandardOpResolver = <InputType extends InputTypes>(
  resolver: ResolverFn<InputType>,
  resolverIsSync?: boolean
) => makeConfigurableStandardOpResolver(resolver, {tags: true}, resolverIsSync);

const makeConfigurableStandardOpResolveOutputType =
  <InputType extends InputTypes>(
    refine: ResolveOutputTypeFn<InputType>,
    typeConfig?: TypeProcessingConfig
  ) =>
  async (
    node: OutputNode,
    executableNode: OutputNode,
    client: Client,
    stack: Stack
  ) => {
    const inputNodes = node.fromOp.inputs;
    const arg0Name = Object.keys(inputNodes)[0];
    return {
      ...node,
      type: await mntTypeApplyAsync(
        inputNodes[arg0Name].type,
        v =>
          refine(
            {
              // Note, specify first argument first to preserve ordering, since
              // we rely on object ordering sometimes.
              [arg0Name]: v,
              ..._.omit(
                _.mapValues(inputNodes, n => n.type),
                [arg0Name]
              ),
            } as any,
            node,
            executableNode,
            client,
            stack
          ),
        typeConfig
      ),
    };
  };

const makeTagConsumingStandardOpResolveOutputType = <
  InputType extends InputTypes
>(
  refine: ResolveOutputTypeFn<InputType>
) => makeConfigurableStandardOpResolveOutputType(refine, {tags: true});

export const makeBasicOp = <I extends InputTypes>({
  name,
  argTypes,
  returnType,
  resolver,
  resolveOutputType,
  hidden,
  renderInfo,
  description,
  argDescriptions,
  returnValueDescription,
  resolverIsSync,
}: Parameters<MakeOpFn<I>>[0]) => {
  const arg0Name = Object.keys(argTypes)[0];
  const fullArgTypes = {
    [arg0Name]: maybe(argTypes[arg0Name]),
    ..._.omit(argTypes, [arg0Name]),
  } as {[key: string]: Type};
  return makeOp({
    name,
    argTypes: fullArgTypes,
    returnType: makeBasicOpReturnType(returnType),
    resolver: makeBasicOpResolver(resolver, resolverIsSync),
    resolveOutputType:
      resolveOutputType != null
        ? makeBasicOpResolveOutputType(resolveOutputType)
        : undefined,
    hidden,
    renderInfo,
    kind: 'basic',
    description,
    argDescriptions,
    returnValueDescription,
  });
};

// A basic op: nullable, taggable, that accepts a list as its first
// argument and returns a single item in response. Handles removing
// tags from the list elements.
export const makeBasicDimDownOp = <I extends InputTypes>({
  name,
  argTypes,
  returnType,
  resolver,
  resolveOutputType,
  hidden,
  description,
  argDescriptions,
  returnValueDescription,
  resolverIsSync,
}: Parameters<MakeOpFn<I>>[0]) => {
  const arg0Name = Object.keys(argTypes)[0];
  const fullArgTypes = {
    [arg0Name]: maybe(argTypes[arg0Name]),
    ..._.omit(argTypes, [arg0Name]),
  } as {[key: string]: Type};
  return makeOp({
    name,
    argTypes: fullArgTypes,
    returnType: makeBasicOpReturnType(returnType),
    resolver: makeBasicOpResolver<I>(
      (
        inputs,
        inputTypes,
        rawInputs,
        forwardGraph,
        forwardOp,
        context,
        engine
      ) => {
        const argName0 = Object.keys(inputs)[0];
        // Remove tags from objects in list
        const untaggedInputs = {
          [argName0]: inputs[argName0].map((v: any) =>
            getValueFromTaggedValue(v)
          ),
          ..._.omit(inputs, [argName0]),
        };
        const untaggedTypes = {
          [argName0]: mappableStrip(taggableStrip(inputTypes[argName0])),
          ..._.omit(inputTypes, [argName0]),
        };
        return resolver(
          untaggedInputs as any,
          untaggedTypes as any,
          rawInputs,
          forwardGraph,
          forwardOp,
          context,
          engine
        );
      },
      resolverIsSync
    ),
    resolveOutputType:
      resolveOutputType != null
        ? makeBasicOpResolveOutputType(resolveOutputType)
        : undefined,
    hidden,
    kind: 'basic-dim-down',
    description,
    argDescriptions,
    returnValueDescription,
  });
};

export const makeEqualOp = ({
  name,
  argType,
  hidden,
}: {
  name: string;
  argType: Type;
  hidden?: boolean;
}) => {
  return makeOp({
    name,
    renderInfo: {
      type: 'binary',
      repr: '==',
    },
    argTypes: {
      lhs: nullableOneOrMany(argType),
      rhs: maybe(argType),
    },
    description: 'Determines equality of two values.',
    argDescriptions: {
      lhs: 'The first value to compare.',
      rhs: 'The second value to compare.',
    },
    returnValueDescription: 'Whether the two values are equal.',
    returnType: inputTypes =>
      // Note we use mappableNullTaggable for type but not for resolver!
      // We definitely don't want to use it in resolver, since we're trying
      // to actually compare nulls.
      // But our >=, <= etc ops return mappableNullableTaggable, we need to return
      // the same thing here to be able to suggest =/!= as replacement ops for
      // >=.

      mappableNullableTaggable(inputTypes.lhs.type, t => 'boolean'),
    resolver: ({lhs, rhs}) =>
      mappableTaggableVal(lhs, v => v === getValueFromTaggedValue(rhs)),
    hidden,
    kind: 'equal',
  });
};

export const makeNotEqualOp = ({
  name,
  argType,
  hidden,
}: {
  name: string;
  argType: Type;
  hidden?: boolean;
}) => {
  return makeOp({
    name,
    renderInfo: {
      type: 'binary',
      repr: '!=',
    },
    argTypes: {
      lhs: nullableOneOrMany(argType),
      rhs: maybe(argType),
    },
    description: 'Determines inequality of two values.',
    argDescriptions: {
      lhs: 'The first value to compare.',
      rhs: 'The second value to compare.',
    },
    returnValueDescription: 'Whether the two values are not equal.',
    returnType: inputTypes =>
      // See note in makeEqualOp
      mappableNullableTaggable(inputTypes.lhs.type, t => 'boolean'),
    resolver: ({lhs, rhs}) =>
      mappableTaggableVal(lhs, v => v !== getValueFromTaggedValue(rhs)),
    hidden,
    kind: 'not-equal',
  });
};

export const makeStandardOp = <I extends InputTypes>({
  name,
  argTypes,
  returnType,
  renderInfo,
  resolver,
  resolveOutputType,
  hidden,
  description,
  argDescriptions,
  returnValueDescription,
  resolverIsSync,
}: Parameters<MakeOpFn<I>>[0]) => {
  const arg0Name = Object.keys(argTypes)[0];
  const fullArgTypes = {
    [arg0Name]: nullableOneOrMany(argTypes[arg0Name]),
    ..._.omit(argTypes, [arg0Name]),
  } as {[key: string]: Type};
  return makeOp({
    name,
    argTypes: fullArgTypes,
    renderInfo,
    returnType: makeStandardOpReturnType(returnType),
    resolver: makeStandardOpResolver(resolver, resolverIsSync),
    resolveOutputType:
      resolveOutputType != null
        ? makeStandardOpResolveOutputType(resolveOutputType)
        : undefined,
    hidden,
    kind: 'standard',
    description,
    argDescriptions,
    returnValueDescription,
  });
};

// Warning -- only use if you are sure this is the correct thing to use.
export const makeConfigurableStandardOp = <I extends InputTypes>({
  name,
  argTypes,
  returnType,
  renderInfo,
  resolver,
  resolveOutputType,
  hidden,
  typeConfig,
  description,
  argDescriptions,
  returnValueDescription,
  resolverIsSync,
}: Parameters<MakeOpFn<I>>[0] & {
  typeConfig?: TypeProcessingConfig;
}) => {
  const arg0Name = Object.keys(argTypes)[0];
  const fullArgTypes = {
    [arg0Name]: nullableOneOrMany(argTypes[arg0Name]),
    ..._.omit(argTypes, [arg0Name]),
  } as {[key: string]: Type};
  return makeOp({
    name,
    argTypes: fullArgTypes,
    renderInfo,
    returnType: makeConfigurableStandardOpReturnType(returnType, typeConfig),
    resolver: makeConfigurableStandardOpResolver(
      resolver,
      typeConfig,
      resolverIsSync
    ),
    resolveOutputType:
      resolveOutputType != null
        ? makeConfigurableStandardOpResolveOutputType(
            resolveOutputType,
            typeConfig
          )
        : undefined,
    hidden,
    kind: 'standard-tag-consuming',
    description,
    argDescriptions,
    returnValueDescription,
  });
};

export const makeTagConsumingStandardOp = <I extends InputTypes>({
  name,
  argTypes,
  returnType,
  renderInfo,
  resolver,
  resolveOutputType,
  hidden,
  description,
  argDescriptions,
  returnValueDescription,
  resolverIsSync,
}: Parameters<MakeOpFn<I>>[0]) => {
  const arg0Name = Object.keys(argTypes)[0];
  const fullArgTypes = {
    [arg0Name]: nullableOneOrMany(argTypes[arg0Name]),
    ..._.omit(argTypes, [arg0Name]),
  } as {[key: string]: Type};
  return makeOp({
    name,
    argTypes: fullArgTypes,
    renderInfo,
    returnType: makeTagConsumingStandardOpReturnType(returnType),
    resolver: makeTagConsumingStandardOpResolver(resolver, resolverIsSync),
    resolveOutputType:
      resolveOutputType != null
        ? makeTagConsumingStandardOpResolveOutputType(resolveOutputType)
        : undefined,
    hidden,
    kind: 'standard-tag-consuming',
    description,
    argDescriptions,
    returnValueDescription,
  });
};

export const makeBinaryStandardOp = (
  repr: string,
  opts: Omit<Parameters<typeof makeStandardOp>[0], 'renderInfo'>
) => {
  return makeStandardOp({
    ...opts,
    renderInfo: {type: 'binary', repr},
  });
};

const isPromise = (object: any): object is Promise<any> =>
  object instanceof Promise ||
  (typeof object === 'object' &&
    object !== null &&
    typeof (object as any).then === 'function');

// Tags the result with its own inputs!
export const makeTaggingStandardOp = <I extends InputTypes>({
  name,
  argTypes,
  returnType,
  resolver,
  resolveOutputType,
  renderInfo,
  hidden,
  description,
  argDescriptions,
  returnValueDescription,
  resolverIsSync,
}: Parameters<MakeTaggingOpFn<I>>[0]) => {
  const arg0Name = Object.keys(argTypes)[0];
  const fullArgTypes = {
    [arg0Name]: nullableOneOrMany(argTypes[arg0Name]),
    ..._.omit(argTypes, [arg0Name]),
  };
  return makeOp({
    name,
    argTypes: fullArgTypes,
    returnType: makeStandardOpReturnType<I>((inputTypes, inputs) =>
      taggedValue(typedDict(inputTypes), returnType(inputTypes, inputs))
    ),
    renderInfo,
    resolver: makeStandardOpResolver<I>(
      (
        inputs,
        inputTypes,
        rawInputs,
        forwardGraph,
        forwardOp,
        context,
        engine
      ) => {
        const resultValue = resolver(
          inputs as any,
          inputTypes,
          rawInputs,
          forwardGraph,
          forwardOp,
          context,
          engine
        );
        // if (isConcreteTaggedValue(resultValue)) {
        //   // TODO: Do we need this?
        //   // If the resolver adds a tag then we don't call
        //   // resolveTag. This allows the resolver to override with a tag
        //   // based on the resolved value.
        //   return resultValue;
        // }
        if (resolverIsSync || !isPromise(resultValue)) {
          return concreteTaggedValue({_opName: name, ...inputs}, resultValue);
        } else {
          return resultValue.then((val: any) =>
            concreteTaggedValue({_opName: name, ...inputs}, val)
          );
        }
        // return concreteTaggedValue(resolveTag(inputs), resultValue);
      },
      resolverIsSync
    ),
    resolveOutputType:
      resolveOutputType != null
        ? makeStandardOpResolveOutputType<I>(
            async (inputTypes, node, executableNode, context, stack) =>
              taggedValue(
                typedDict(inputTypes),
                await resolveOutputType(
                  inputTypes,
                  node,
                  executableNode,
                  context,
                  stack
                )
              )
          )
        : undefined,
    hidden,
    kind: 'standard-tag',
    description,
    argDescriptions,
    returnValueDescription,
  });
};

// Handles union cases, and retains a tag's own tags
export const makeTagGetterOp = ({
  name,
  tagName,
  tagType,
  hidden,
  description,
  argDescriptions,
  returnValueDescription,
}: TagGetterOpFnOpts) => {
  return makeOp({
    name,
    argTypes: {
      obj: nullableOneOrMany(
        taggedValue(typedDict({[tagName]: tagType}), 'any')
      ),
    },
    returnType: inputs => {
      return nullable(inputs.obj.type, objTypeNonNull => {
        let outerTag: Type | null = null;
        let objType = objTypeNonNull;

        if (isTaggedValueLike(objTypeNonNull)) {
          outerTag = taggedValueTagType(objTypeNonNull);
          objType = taggedValueValueType(objTypeNonNull);
        }

        if (isListLike(objType)) {
          const itemResult = mappableNullable(objType, t => {
            const res = findNamedTagInType(t, tagName, tagType);
            if (res !== 'none' && outerTag != null) {
              return taggedValue(outerTag, res);
            }
            return res;
          });
          const innerResult = (itemResult as ListType).objectType;
          if (innerResult !== 'none') {
            return itemResult;
          }
        }

        const outerResult = findNamedTagInType(
          objTypeNonNull,
          tagName,
          tagType
        );
        if (outerResult !== 'none') {
          return outerResult;
        }

        return 'none';
      });
    },
    resolver: inputs => {
      // TODO: make this properly respect types. When we get a tag's value from
      // a concrete tagged value, we do not enforce that it matches the requested type.

      return nullableVal(inputs.obj, objNonNull => {
        let outerTag: any = null;
        let obj = objNonNull;

        if (isConcreteTaggedValue(objNonNull)) {
          outerTag = objNonNull._tag;
          obj = objNonNull._value;
        }

        if (_.isArray(obj)) {
          const itemResult = mappableNullableVal(obj, v => {
            const res = findNamedTagInVal(v, tagName);
            if (res != null && outerTag != null) {
              return concreteTaggedValue(outerTag, res);
            }
            return res;
          });
          const itemResultValid = itemResult.some((item: any) => item != null);
          if (itemResultValid) {
            return itemResult;
          }
        }

        const tag = findNamedTagInVal(objNonNull, tagName);
        if (tag != null) {
          return tag;
        }

        return null;
      });
    },
    hidden,
    kind: 'tag-getter',
    description:
      description ??
      `Returns the first ${tagName} tag of type ${tagType} found in the given object.`,
    argDescriptions: argDescriptions ?? {
      obj: 'The object to get the tag value from.',
    },
    returnValueDescription:
      returnValueDescription ??
      `The first ${tagName} tag of type ${tagType} found in the given object.`,
  });
};
