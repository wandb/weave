// These definitions are needed by Weave Python, do not delete them.
// The primary reason we still need these is for ops that have refineType
// methods that cannot be expressed as Weave DAGs yet. So we reimplement
// the refine logic in JS to make things work.

import * as _ from 'lodash';

import {
  ALL_DIR_TYPE,
  constNumber,
  dict,
  filePathToType,
  isConstType,
  isListLike,
  isSimpleTypeShape,
  isTaggedValue,
  isTypedDict,
  isTypedDictLike,
  isUnion,
  list,
  listObjectType,
  nonNullable,
  taggedValue,
  Type,
  typedDict,
  typedDictPropertyTypes,
  union,
  unionObjectTypeAttrTypes,
} from '../../model';
import {ALL_BASIC_TYPES, ListType} from '../../model/types';
import {makeOp} from '../../opStore';
import {makeBasicOp, makeEqualOp, makeStandardOp} from '../opKinds';
import {opIndex} from '../primitives';
import {splitEscapedString} from '../primitives/splitEscapedString';

// import * as TypeHelpers from '../model/typeHelpers';
// import * as Types from '../model/types';
// import {opIndex} from '../ops.primitives';

function valToTypeSimple(val: any): Type {
  if (typeof val === 'string' || val === null) {
    return 'string';
  } else if (typeof val === 'number') {
    return 'number';
  } else if (typeof val === 'boolean') {
    return 'boolean';
  } else {
    return 'any';
  }
}

export const opDirOpenReturnType = makeOp({
  hidden: true,
  name: 'dir-pathReturnType',
  description: 'hello',
  argDescriptions: {
    conf: 'hello',
    size: 'hello',
  },
  returnValueDescription: 'hello',
  argTypes: {
    dir: {type: 'dir'},
    path: 'string',
  },
  returnType: inputTypes => 'type',
  resolver: ({path}) => {
    throw new Error('not implemented');
  },
});

export const opDirOpen = makeOp({
  hidden: true,
  name: 'dir-path',
  description: 'hello',
  argDescriptions: {
    conf: 'hello',
    size: 'hello',
  },
  returnValueDescription: 'hello',
  argTypes: {
    dir: ALL_DIR_TYPE,
    path: 'string',
  },
  returnType: inputTypes => ({type: 'file'}),
  resolver: ({path}) => {
    throw new Error('not implemented');
  },
  resolveOutputType: async (node, executableNode, client) => {
    const typeNode = opDirOpenReturnType(executableNode.fromOp.inputs as any);
    let newType: Type = await client.query(typeNode);
    if (!isSimpleTypeShape(newType) && (newType as any).type === 'local_file') {
      newType = filePathToType(
        (executableNode.fromOp.inputs.path as any).val as any
      );
    }
    return {
      ...node,
      type: newType,
    };
  },
});

export const opLocalArtifact = makeOp({
  hidden: true,
  name: 'root-localArtifact',
  description: 'hello',
  argDescriptions: {
    conf: 'hello',
    size: 'hello',
  },
  returnValueDescription: 'hello',
  renderInfo: {type: 'function'},
  argTypes: {
    path: 'string',
  },
  returnType: inputTypes => 'artifactVersion',
  resolver: ({path}) => {
    throw new Error('not implemented');
  },
});

export const opRootString = makeOp({
  hidden: true,
  name: 'root-string',
  description: 'hello',
  argDescriptions: {
    conf: 'hello',
    size: 'hello',
  },
  returnValueDescription: 'hello',
  renderInfo: {type: 'function'},
  argTypes: {
    v: 'string',
  },
  returnType: inputTypes => 'string',
  resolver: ({path}) => {
    throw new Error('not implemented');
  },
});

export const opLocalArtifactGet = makeOp({
  hidden: true,
  name: 'localArtifact-get',
  description: 'hello',
  argDescriptions: {
    conf: 'hello',
    size: 'hello',
  },
  returnValueDescription: 'hello',
  argTypes: {
    artifact: 'artifactVersion',
    name: 'string',
  },
  returnType: inputTypes => ({
    type: 'file',
    extension: 'json',
    wbObjectType: {type: 'image-file'},
  }),
  resolver: ({path}) => {
    throw new Error('not implemented');
  },
});

export const opSnowflakeTable = makeOp({
  hidden: true,
  name: 'local-snowflaketable',
  description: 'hello',
  argDescriptions: {
    conf: 'hello',
    size: 'hello',
  },
  returnValueDescription: 'hello',
  renderInfo: {type: 'function'},
  argTypes: {
    path: 'string',
  },
  returnType: inputTypes => list(typedDict({})),
  resolver: ({path}) => {
    throw new Error('not implemented');
  },
  resolveOutputType: async (node, executableNode, client) => {
    const firstRowNode = opIndex({arr: executableNode, index: constNumber(1)});
    const firstRow = await client.query(firstRowNode);
    let newType: Type = list(typedDict({}));

    if (firstRow != null) {
      newType = list(typedDict(_.mapValues(firstRow, v => valToTypeSimple(v))));
    }
    return {
      ...node,
      type: newType,
    };
  },
});

export const opSqlConn = makeOp({
  name: 'local-sqlconnection',
  description: 'hello',
  argDescriptions: {
    conf: 'hello',
    size: 'hello',
  },
  returnValueDescription: 'hello',
  renderInfo: {type: 'function'},
  argTypes: {
    path: 'string',
  },
  returnType: inputTypes => 'sqlconnection',
  resolver: ({path}) => {
    throw new Error('not implemented');
  },
});

export const opSqlConnTables = makeOp({
  hidden: true,
  name: 'sqlconnection-tables',
  description: 'hello',
  argDescriptions: {
    conf: 'hello',
    size: 'hello',
  },
  returnValueDescription: 'hello',
  argTypes: {
    conn: 'sqlconnection',
  },
  returnType: inputTypes => typedDict({}),
  resolver: ({path}) => {
    throw new Error('not implemented');
  },
  resolveOutputType: async (node, executableNode, client) => {
    const firstRowNode = opSqlConnTablesType({
      conn: executableNode.fromOp.inputs.conn as any,
    });
    const newType: Type = await client.query(firstRowNode);
    return {
      ...node,
      type: newType,
    };
  },
});

export const opSqlConnTablesType = makeOp({
  hidden: true,
  name: 'sqlconnection-tablesType',
  description: 'hello',
  argDescriptions: {
    conf: 'hello',
    size: 'hello',
  },
  returnValueDescription: 'hello',
  renderInfo: {type: 'function'},
  argTypes: {
    conn: 'sqlconnection',
  },
  returnType: inputTypes => 'type',
  resolver: ({path}) => {
    throw new Error('not implemented');
  },
});

export const opSqlConnTable = makeOp({
  hidden: true,
  name: 'sqlconnection-table',
  description: 'hello',
  argDescriptions: {
    conf: 'hello',
    size: 'hello',
  },
  returnValueDescription: 'hello',
  argTypes: {
    conn: 'sqlconnection',
    name: 'string',
  },
  returnType: inputTypes => typedDict({}),
  resolver: ({path}) => {
    throw new Error('not implemented');
  },
  resolveOutputType: async (node, executableNode, client) => {
    const firstRowNode = opIndex({arr: executableNode, index: constNumber(1)});
    const firstRow = await client.query(firstRowNode);
    let newType: Type = list(typedDict({}));

    if (firstRow != null) {
      newType = list(typedDict(_.mapValues(firstRow, v => valToTypeSimple(v))));
    }
    return {
      ...node,
      type: newType,
    };
  },
});

export const opGetReturnType = makeOp({
  hidden: true,
  name: 'getReturnType',
  description: 'hello',
  argDescriptions: {
    conf: 'hello',
    size: 'hello',
  },
  returnValueDescription: 'hello',
  renderInfo: {type: 'function'},
  argTypes: {
    path: 'string',
  },
  returnType: inputTypes => 'type',
  resolver: ({path}) => {
    throw new Error('not implemented');
  },
});

export const opGet = makeOp({
  hidden: true,
  name: 'get',
  renderInfo: {type: 'function'},
  description: 'hello',
  argDescriptions: {
    conf: 'hello',
    size: 'hello',
  },
  returnValueDescription: 'hello',
  argTypes: {
    uri: 'string',
  },
  returnType: inputTypes => 'any',
  resolver: ({path}) => {
    throw new Error('not implemented');
  },
  resolveOutputType: async (node, executableNode, client) => {
    const typeNode = opGetReturnType(executableNode.fromOp.inputs as any);
    const newType: Type = await client.query(typeNode);
    return {
      ...node,
      type: newType,
    };
  },
});
export const opSave = makeOp({
  hidden: true,
  name: 'save',
  description: 'hello',
  argDescriptions: {
    obj: 'hello',
    name: 'hello',
  },
  returnValueDescription: 'hello',
  argTypes: {
    obj: 'any',
    name: 'string',
  },
  returnType: inputTypes => inputTypes.obj.type,
  resolver: ({path}) => {
    throw new Error('not implemented');
  },
});

export const opArtifactVersionFileType = makeOp({
  hidden: true,
  name: 'artifactVersion-fileReturnType',
  description: 'hello',
  argDescriptions: {
    conf: 'hello',
    size: 'hello',
  },
  returnValueDescription: 'hello',
  renderInfo: {type: 'function'},
  argTypes: {
    path: 'string',
  },
  returnType: inputTypes => 'type',
  resolver: ({path}) => {
    throw new Error('not implemented');
  },
});

export const opRefGet = makeBasicOp({
  hidden: false,
  name: 'Ref-get',
  description: 'hello',
  argDescriptions: {
    conf: 'hello',
    size: 'hello',
  },
  returnValueDescription: 'hello',
  argTypes: {
    self: {
      type: 'union',
      members: [
        {type: 'Ref' as any, objectType: 'any'},
        {type: 'FilesystemArtifactRef', objectType: 'any'},
      ],
    },
  },
  returnType: inputTypes => {
    const selfType = inputTypes.self;
    if (isUnion(selfType)) {
      return union(selfType.members.map(m => m.objectType as Type));
    }
    return (selfType as any).objectType;
  },
  resolver: ({self}) => {
    throw new Error('not implemented');
  },
});

export const opExecute = makeOp({
  hidden: true,
  name: 'execute',
  description: 'hello',
  argDescriptions: {
    conf: 'hello',
    size: 'hello',
  },
  returnValueDescription: 'hello',
  argTypes: {
    node: {type: 'function', inputTypes: {}, outputType: 'any'},
  },
  returnType: inputTypes => inputTypes.node.type.outputType,
  resolver: ({path}) => {
    throw new Error('not implemented');
  },
});

export const opFunctionCall = makeOp({
  hidden: true,
  name: 'function-__call__',
  argTypes: {
    self: {type: 'function', inputTypes: {}, outputType: 'any'},
  },
  returnType: inputTypes => inputTypes.self.type.outputType,
  resolver: ({path}) => {
    throw new Error('not implemented');
  },
});

export const opScatterSelected = makeOp({
  hidden: true,
  name: 'Scatter-selected',
  argTypes: {
    self: {type: 'Scatter'} as any,
  },
  returnType: inputTypes => {
    // Note ! Something is wrong here. self is a ConstNode,
    // not a type!
    // TODO: FIX!
    return inputTypes.self.type.input_node.outputType;
  },
  resolver: ({path}) => {
    throw new Error('not implemented');
  },
});

export const opGeoSelected = makeOp({
  hidden: true,
  name: 'Geo-selected',
  argTypes: {
    self: {type: 'Geo'} as any,
  },
  returnType: inputTypes => {
    // Note ! Something is wrong here. self is a ConstNode,
    // not a type!
    // TODO: FIX!
    return inputTypes.self.type.input_node.outputType;
  },
  resolver: ({path}) => {
    throw new Error('not implemented');
  },
});

export const opFacetSelected = makeOp({
  hidden: false,
  name: 'Facet-selected',
  description: 'Show selected rows of a Facet panel',
  argDescriptions: {
    self: 'The facet panel',
  },
  returnValueDescription: 'selected rows',
  argTypes: {
    self: {type: 'Facet'} as any,
  },
  returnType: inputTypes => {
    // Note ! Something is wrong here. self is a ConstNode,
    // not a type!
    // TODO: FIX!
    return inputTypes.self.type.input_node.outputType;
  },
  resolver: ({path}) => {
    throw new Error('not implemented');
  },
});

const unwrapConstType = (type: Type): Type => {
  if (isConstType(type)) {
    if (type.valType === 'type') {
      return unwrapConstType(type.val);
    } else {
      return unwrapConstType(type.valType);
    }
  }
  return type;
};

// This Op is a WIP - we are currently iterating on the design of Types
// which will result in refactoring this op to be more generic. Ultimately,
// we should not have all these conditionals to handle different circumstances.
// For now we will check this in and keep moving forward.
export const opObjGetAttr = makeStandardOp({
  hidden: true,
  name: 'Object-__getattr__',
  argTypes: {
    self: 'any',
    name: 'string',
  },
  returnType: (inputTypes, inputs) => {
    const selfType = unwrapConstType(inputTypes.self);
    // If the name node is not a const, then we have no idea what the return will be.
    if (inputs.name.nodeType !== 'const') {
      return 'unknown';
      // If the self node is of type `type`, then we have three special cases:
    }
    const attrName = inputs.name.val;
    if (isSimpleTypeShape(selfType) && selfType === 'type') {
      // First, a special case where we are getting the `property_types` off of the `dict` type. (support both python and ts casings)
      if (attrName === 'property_types' || attrName === 'propertyTypes') {
        return dict('type');
        // Next, we are getting the members of a union
      } else if (attrName === 'members') {
        return list('type');
      }
      return 'type';
    }

    const attrTypes = unionObjectTypeAttrTypes(selfType);
    return attrTypes[attrName] ?? 'unknown';
  },
  resolverIsSync: true,
  resolver: inputs => {
    let self = inputs.self;
    if (self == null) {
      return null;
    }
    // In the very specific case that the incoming object itself is a const type...
    if (self.type === 'const') {
      // If the property is a valid const property...
      if (inputs.name === 'val') {
        return self.val;
      } else if (inputs.name === 'valType') {
        return self.valType;
      }
      self = unwrapConstType(self);
    }

    // Next, in the specific case that we are getting the `property_types` off of a dictionary... (support both python and ts casings)
    if (inputs.name === 'property_types' || inputs.name === 'propertyTypes') {
      if (self.propertyTypes != null) {
        return self.propertyTypes;
      }
    }

    // Next, in the specific case that we are getting `object_type` from a list (support both python and ts casings)
    if (inputs.name === 'object_type' || inputs.name === 'objectType') {
      if (self.objectType != null) {
        return self.objectType;
      }
    }

    // // Finally, in the case that we are getting a property off of an object...
    return self[inputs.name];
  },
});

export const opTypeNewType = makeOp({
  hidden: true,
  name: 'type-__newType__',
  argTypes: {
    name: 'string',
    manyX: 'unknown',
  },
  returnType: 'type',
  resolver: inputs => {
    if (ALL_BASIC_TYPES.includes(inputs.name)) {
      return inputs.name;
    } else {
      return {
        type: inputs.name,
        ..._.mapValues(_.omit(inputs, 'name'), (val, key) => {
          if (val.type === 'const') {
            if (val.valType === 'type') {
              val = val.val;
            } else {
              val = val.valType;
            }
          }
          return val;
        }),
      };
    }
  },
});

export const opGetTagType = makeOp({
  hidden: true,
  name: 'op_get_tag_type',
  argTypes: {
    obj_type: 'type',
  },
  returnType: 'type',
  resolver: inputs => {
    if (isTaggedValue(inputs.obj_type)) {
      return inputs.obj_type.tag;
    }
    return 'none';
  },
});

export const opMakeTypeTagged = makeOp({
  hidden: true,
  name: 'op_make_type_tagged',
  argTypes: {
    obj_type: 'type',
    tag_type: 'type',
  },
  returnType: 'type',
  resolver: inputs => {
    if (isTypedDict(inputs.tag_type)) {
      taggedValue(inputs.tag_type, inputs.obj_type);
    }
    return inputs.obj_type;
  },
});

export const opMakeTypeKeyTag = makeOp({
  hidden: true,
  name: 'op_make_type_key_tag',
  argTypes: {
    obj_type: 'type',
    key: 'string',
    tag_type: 'type',
  },
  returnType: 'type',
  resolver: inputs => {
    let currentTags = {[inputs.key]: inputs.tag_type};
    if (isTaggedValue(inputs.tag_type) && isTypedDict(inputs.tag_type.tag)) {
      currentTags = {...currentTags, ...inputs.tag_type.tag.propertyTypes};
    }
    if (isTypedDict(inputs.tag_type)) {
      taggedValue(inputs.tag_type, inputs.obj_type);
    }
    return taggedValue(typedDict(currentTags), inputs.obj_type);
  },
});

export const opNonNone = makeOp({
  hidden: true,
  name: 'op-non_none',
  argTypes: {
    obj_type: 'type',
  },
  returnType: 'type',
  resolver: inputs => {
    return nonNullable(inputs.obj_type);
  },
});

export const opToPy = makeOp({
  hidden: true,
  name: 'op-to_py',
  argTypes: {
    self: 'any',
  },
  returnType: inputNodes => inputNodes.self.type,
  resolver: inputs => {
    throw new Error('cant resolve op-to_py in js');
  },
});

export const opCrossProduct = makeOp({
  name: 'op-cross_product',
  renderInfo: {
    type: 'function',
  },
  description: 'hello',
  argDescriptions: {
    conf: 'hello',
    size: 'hello',
  },
  returnValueDescription: 'hello',
  argTypes: {
    obj: {
      type: 'dict',
      objectType: {
        type: 'list',
        objectType: 'any',
      },
    },
  },
  returnType: inputNodes => {
    const objType = inputNodes.obj.type as Type;
    if (isTypedDict(objType)) {
      const newPropTypes = _.mapValues(
        objType.propertyTypes,
        propType => (propType as ListType).objectType
      );
      return {type: 'list', objectType: typedDict(newPropTypes)};
    }
    throw new Error('unhandled type in op-cross-product');
  },
});

const withColumnType = (
  curType: Type | undefined,
  key: string,
  newColType: Type
): Type => {
  if (curType == null || !isTypedDictLike(curType)) {
    curType = typedDict({});
  }
  const path = splitEscapedString(key);
  const propertyTypes = {...typedDictPropertyTypes(curType)} as {
    [key: string]: Type;
  };
  if (path.length > 1) {
    return withColumnType(
      curType,
      path[0],
      withColumnType(
        propertyTypes[path[0]],
        path.slice(1).join('.'),
        newColType
      )
    );
  }
  let colNames = Object.keys(propertyTypes);
  const colIndex = colNames.findIndex(colName => colName === key);
  if (colIndex !== -1) {
    delete propertyTypes[key];
    colNames = colNames.splice(colIndex, 1);
  }
  propertyTypes[key] = newColType;
  return typedDict(propertyTypes);
};

const withColumnsOutputType = (selfType: ListType, colsType: Type) => {
  if (!isTypedDict(colsType)) {
    throw new Error('invalid');
  }

  let objType = selfType.objectType;
  for (const [k, v] of Object.entries(colsType.propertyTypes)) {
    if (v == null || !isListLike(v)) {
      throw new Error('invalid ');
    }
    objType = withColumnType(objType, k, listObjectType(v));
  }
  return {
    type: 'ArrowWeaveList',
    objectType: objType,
    _base_type: {type: 'list'},
  } as Type;
};

export const opWithColumns = makeBasicOp({
  name: 'ArrowWeaveListTypedDict-with_columns',
  renderInfo: {
    type: 'function',
  },
  description: 'hello',
  argDescriptions: {},
  returnValueDescription: 'hello',
  argTypes: {
    self: {
      type: 'list',
      objectType: {
        type: 'typedDict',
        propertyTypes: {},
      },
    },
    cols: {
      type: 'dict',
      objectType: {type: 'list', objectType: 'any'},
    },
  },
  returnType: inputTypes => {
    return withColumnsOutputType(inputTypes.self, inputTypes.cols);
  },
  resolver: inputs => {
    throw new Error('cant resolve op-chain-run in js');
  },
});

export const opChainRun = makeStandardOp({
  name: 'Chain-run',
  description: 'hello',
  argDescriptions: {
    conf: 'hello',
    size: 'hello',
  },
  returnValueDescription: 'hello',
  argTypes: {
    chain: {
      type: 'Chain',
    } as any,
    query: 'string',
  },
  returnType: inputTypes => {
    return {
      type: 'ChainRunResult',
      _is_object: true,
      _base_type: {
        type: 'Object',
      },
      chain: inputTypes.chain,
      query: 'string',
      result: 'string',
      latency: 'number',
      trace: {
        type: 'wb_trace_tree',
      },
    } as any;
  },
  resolver: inputs => {
    throw new Error('cant resolve op-chain-run in js');
  },
});

export const opRefEqual = makeEqualOp({
  hidden: true,
  name: 'Ref-__eq__',
  argType: {type: 'Ref'},
});

export const opRefToUri = makeOp({
  hidden: true,
  name: 'ref-toUri',
  argTypes: {
    self: {type: 'Ref'},
  },
  returnType: 'string',
  resolver: inputs => {
    throw new Error('cant resolve op-ref-toUri in js');
  },
});
