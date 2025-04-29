import * as _ from 'lodash';

import type {Client} from '../../client';
import {EngineClient} from '../../client';
import * as HL from '../../hl';
import {
  isIncrementalTable,
  isTaggedValue,
  list,
  mappableNullableSkipTaggable,
  mappableNullableTaggable,
  mappableNullableTaggableVal,
  maybe,
  MediaIncrementalTable,
  nullableOneOrMany,
  OpInputNodes,
  OutputNode,
  taggedValue,
  TaggedValueType,
  typedDict,
  withFileTag,
  withTableRowTag,
} from '../../model';
import {makeOp} from '../../opStore';
import {docType} from '../../util/docs';
import {makeTagGetterOp} from '../opKinds';
import {makeResolveOutputTypeFromOp} from './refineOp';

export const opIncrementalTableRowsType = makeOp({
  hidden: true,
  name: 'incrementaltable-rowsType',
  argTypes: {
    incrementalTable: nullableOneOrMany({
      type: 'incremental-table',
      columnTypes: {},
    }),
  },
  returnType: 'type',
  resolver: async (
    {incrementalTable},
    forwardGraph,
    forwardOp,
    context,
    engine
  ) => {
    throw Error('not implemented');
  },
});

export const opIncrementalTableRows = makeOp({
  name: 'incrementaltable-rows',
  argTypes: {
    incrementalTable: nullableOneOrMany({
      type: 'incremental-table',
      columnTypes: {},
    }),
  },
  description: `Returns the rows of a ${docType('incremental-table')}`,
  argDescriptions: {
    incrementalTable: `The ${docType('incremental-table')} to get rows from`,
  },
  returnValueDescription: `Rows of the ${docType('incremental-table')}`,
  returnType: inputs => {
    return mappableNullableSkipTaggable(inputs.incrementalTable.type, t => {
      if (!isIncrementalTable(t)) {
        throw new Error('opIncrementalTableRows: expected incremental table');
      }
      return list(withTableRowTag(typedDict({}), inputs.incrementalTable.type));
    });
  },
  resolver: async (inputs, forwardGraph, forwardOp, context, engine) => {
    throw new Error('not implemented');
  },
  resolveOutputType: makeResolveOutputTypeFromOp(opIncrementalTableRowsType, [
    'incrementalTable',
  ]),
});
