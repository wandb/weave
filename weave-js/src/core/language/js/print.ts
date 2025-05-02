// High-level functions for manipulating and interpreting
// a compute graph.
//
// User code (UI) uses the functions in this file to manipulate and
// interact with the graph.

import _, {uniq} from 'lodash';

import type {EditingNode, EditingOp} from '../../model/graph/editing/types';
import {
  isFunction,
  isMediaType,
  isSimpleTypeShape,
  isTaggedValue,
  taggedValueValueType,
} from '../../model/helpers';
import type {Type} from '../../model/types';
import type {OpStore} from '../../opStore/types';
import {opNeedsParens} from '../../opStore/util';
import {opDisplayName} from '../../opStore/util';
import {indent} from '../../util/string';

export function nodeToString(
  node: EditingNode,
  opStore: OpStore,
  level: number | null = 0,
  root?: EditingNode
): string {
  if (node.nodeType === 'const') {
    if ((node.type as any)._is_object) {
      const objType = node.type as any;
      // we are an object
      return `<${objType.type}>`;
    }
    if (isFunction(node.type)) {
      if (level != null) {
        level += 2;
      }
      const inputVars = Object.keys(node.type.inputTypes);
      // This is a function argument

      const fnString =
        `(${uniq(inputVars).join(', ')}) => ` +
        nodeToString(node.val, opStore, level != null ? 0 : null, root);
      const lines =
        level != null
          ? fnString
              .split('\n')
              .map((l, i) => (i === 0 ? l : indent(l, level as number)))
              .join('\n')
          : fnString;
      return lines;
    } else if (node.type === 'none') {
      return 'null';
    }
    // NOTICE: JSON.stringify will transform single backslashes into double backslashes.
    // for example:
    // s = 'a\\b'
    // s.length // => 3 (the double backslash is needed to enter the raw value of 'a\b')
    // JSON.stringify(s) // => "a\\b" (see how it adds a slash)
    //
    // the following adjustment replaces all instances of `\\` with `\`.

    // Special case strings that contain double quotes and no single quotes: serialize as a single-quoted string
    if (
      typeof node.val === 'string' &&
      node.val.includes('"') &&
      !node.val.includes("'")
    ) {
      return indent(`'${node.val}'`, level as number);
    }

    return indent(
      JSON.stringify(node.val).replace(/\\\\/g, '\\'),
      level as number
    );
  } else if (node.nodeType === 'void') {
    return '';
  } else if (node.nodeType === 'var') {
    // TODO: Big hack, if we encounter a var, make it look like a function
    // call. This won't work at all in scenarios where we encounter more
    // than one var!
    // TODO: Broke this hack in this commit
    return `${node.varName}`;
  } else if (node.nodeType == null) {
    // TODO: in the join op `ops.ts#opJoin`, the return type has 6 keys,
    // 2 of which (arr1 and arr2) end up being objectTypes, but lack the
    // fromOp and nodeType keys. We should resolve that which would remove this
    // branch of the conditional.
    return '';
  } else {
    return opToString(node.fromOp, root || node, opStore, level);
  }
}

function opToString(
  op: EditingOp,
  graph: EditingNode,
  opStore: OpStore,
  level: number | null = 0
): string {
  const argValues = Object.values(op.inputs);
  const innerNodeToString = (node: EditingNode) => {
    return nodeToString(node, opStore, level, graph);
  };

  const opDef = opStore.getOpDef(op.name);

  // Special case for __getattr__
  if (op.name.endsWith('__getattr__')) {
    return `${innerNodeToString(argValues[0])}.${innerNodeToString(
      argValues[1]
    ).slice(1, -1)}`;
  }

  switch (opDef.renderInfo.type) {
    case 'arrayLiteral': {
      let res = '[';
      const elements = [];
      for (const index of Object.keys(op.inputs)) {
        elements.push(`${innerNodeToString(op.inputs[index])}`);
      }
      res += elements.join(', ');
      res += ']';
      return res;
    }
    case 'dictionaryLiteral': {
      let res = '{';
      const properties = [];
      for (const argName of Object.keys(op.inputs)) {
        properties.push(`${argName}: ${innerNodeToString(op.inputs[argName])}`);
      }
      res += properties.join(', ');
      res += '}';
      return res;
    }
    case 'unary': {
      const needsParens = opNeedsParens(op, graph, opStore);

      return `${opDef.renderInfo.repr}${
        needsParens ? '(' : ''
      }${innerNodeToString(argValues[0])}${needsParens ? ')' : ''}`;
    }
    case 'binary': {
      const needsParens = opNeedsParens(op, graph, opStore);

      return `${needsParens ? '(' : ''}${innerNodeToString(argValues[0])} ${
        opDef.renderInfo.repr
      } ${innerNodeToString(argValues[1])}${needsParens ? ')' : ''}`;
    }
    case 'brackets':
      return `${innerNodeToString(argValues[0])}[${innerNodeToString(
        argValues[1]
      )}]`;
    case 'chain':
      const restOfArgs = argValues.slice(1);
      const unaryOpArgs =
        restOfArgs.length > 0
          ? `(${restOfArgs.map(innerNodeToString).join(', ')})`
          : '';
      return `${argValues.length > 0 ? innerNodeToString(argValues[0]) : ''}${
        level != null ? '\n  ' : ''
      }.${opDisplayName(op, opStore)}${unaryOpArgs}`;
    case 'function':
      const opArgs = argValues
        .map(innerNodeToString)
        .map(argLinesString =>
          level != null
            ? argLinesString
                .split('\n')
                .map(v => indent(v, 2))
                .join('\n')
            : argLinesString
        )
        .join(`,${level != null ? '\n' : ' '}`);
      return `${opDisplayName(op, opStore)}(${
        level != null ? '\n' : ''
      }${opArgs})`;
    default:
      throw new Error(
        `op ${op.name} has invalid renderInfo.type ${
          (opDef.renderInfo as any).type
        }`
      );
  }
}

export function typeToString(
  type: Type,
  simple = true,
  level = 0,
  skipTags = false
): string {
  if (type === undefined) {
    return 'INVALID_TYPE_ERROR';
  }

  if (skipTags && isTaggedValue(type)) {
    return typeToString(taggedValueValueType(type), simple, level, skipTags);
  }

  if (isSimpleTypeShape(type)) {
    return type;
  } else if (type.type === 'typedDict') {
    return simple
      ? 'dict'
      : [
          '{',
          ..._.map(type.propertyTypes, (v, k) =>
            indent(k + ':' + typeToString(v!, simple, level + 1), level + 1)
          ),
          indent('}', level),
        ].join('\n');
  } else if (type.type === 'table') {
    return simple
      ? '(table)'
      : _.isEmpty(type.columnTypes)
      ? 'Table'
      : [
          'Table<',
          ..._.map(type.columnTypes, (v, k) =>
            indent(k + ':' + typeToString(v, simple, level + 1), level + 1)
          ),
          indent('>', level),
        ].join('\n');
  } else if (type.type === 'joined-table') {
    return simple
      ? '(joined table)'
      : _.isEmpty(type.columnTypes)
      ? 'JoinedTable'
      : [
          'JoinedTable<',
          ..._.map(type.columnTypes, (v, k) =>
            indent(k + ':' + typeToString(v, simple, level + 1), level + 1)
          ),
          indent('>', level),
        ].join('\n');
  } else if (type.type === 'partitioned-table') {
    return simple
      ? '(partitioned table)'
      : _.isEmpty(type.columnTypes)
      ? 'PartitionedTable'
      : [
          'PartitionedTable<',
          ..._.map(type.columnTypes, (v, k) =>
            indent(k + ':' + typeToString(v, simple, level + 1), level + 1)
          ),
          indent('>', level),
        ].join('\n');
  } else if (type.type === 'dict') {
    return simple
      ? '(dictionary)'
      : `{[k]: ${typeToString(type.objectType, simple, level + 1)}}`;
  } else if (type.type === 'tagged') {
    if (simple) {
      return typeToString(type.value, simple, level);
    }
    return [
      'Tagged<',
      indent('tag: ' + typeToString(type.tag, simple, level + 1), level + 1),
      indent(
        'value: ' + typeToString(type.value, simple, level + 1),
        level + 1
      ),
      indent('>', level),
    ].join('\n');
  } else if (type.type === 'list') {
    return `List<${typeToString(type.objectType, simple, level)}>`;
  } else if (type.type === 'function') {
    return `Function<outputType: ${typeToString(
      type.outputType,
      simple,
      level
    )}>`;
  } else if (type.type === 'file') {
    if (type.wbObjectType != null) {
      return `File<${typeToString(type.wbObjectType, simple, level)}>`;
    }
    return `File<{${
      type.extension != null ? 'extension: ' + type.extension : ''
    }}>`;
  } else if (type.type === 'dir') {
    return 'Dir';
  } else if (type.type === 'union') {
    if (type.members.length === 2 && type.members.includes('none')) {
      const nonNone = type.members.filter(m => m !== 'none')[0];
      return `Maybe<${typeToString(nonNone, simple, level + 1)}>`;
    }
    return simple
      ? 'Union<...>'
      : [
          'Union<',
          type.members
            .map(t => indent(typeToString(t, simple, level + 1), level + 1))
            .join(' |\n'),
          indent('>', level),
        ].join('\n');
  } else if (type.type === 'ndarray') {
    return `NDArray<${type.shape}>`;
  } else if (type.type === 'const') {
    return typeToString(type.valType, simple, level);
  } else if (isMediaType(type)) {
    return type.type;
  } else if (type.type != null) {
    return type.type;
  }
  throw new Error(`unhandled type ${JSON.stringify(type)}`);
}
