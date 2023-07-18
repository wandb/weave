import * as _ from 'lodash';

import {listWithLength, Node, typedDict, union} from '../../model';
import {makeOp} from '../../opStore';
import {docType} from '../../util/docs';
import {spread} from '../util';

export const opArray = makeOp({
  hidden: true,
  name: 'list',
  // This takes a variable number of arguments, but we only specify one...
  // TODO: This will break the graph view. Figure out a way to specify this.
  // Using invalid type so these opArray doesn't show up in auto-suggest for now.
  argTypes: {manyX: 'invalid'},
  renderInfo: {
    type: 'arrayLiteral',
  },
  description: `Creates a ${docType(
    'list'
  )} from a variable number of arguments`,
  argDescriptions: {
    manyX: `The values to add to the ${docType(
      'list'
    )}: Note: in Weave, the arguments are {[index:number]: value}`,
  },
  returnValueDescription: `The ${docType('list')}`,
  returnType: inputs => {
    const argValues = Object.values(inputs);
    // I added the av.type !== null to allow for null types in the array
    // if (
    //   argValues
    //     .slice(1)
    //     .some(av => av.type !== null && !_.isEqual(av.type, argValues[0].type))
    // ) {
    //   throw new Error('array member types must be homogenous');
    // }
    return listWithLength(
      argValues.length,
      argValues.length > 0 ? union(argValues.map(av => av.type)) : 'unknown'
    );
  },
  resolver: inputs => {
    // Inputs are all arguments
    return Object.values(inputs);
  },
});

export const opList = opArray;

export const maybeOpArray = <T extends Node>(items: T[]) => {
  if (items.length === 1) {
    return items[0];
  }
  return opArray(spread(items) as any);
};

export const opDict = makeOp({
  hidden: true,
  name: 'dict',
  // This takes a variable number of arguments, but we only specify one...
  // TODO: This will break the graph view. Figure out a way to specify this.
  // Using invalid type so these opArray doesn't show up in auto-suggest for now.
  argTypes: {manyX: 'invalid'},
  description: `Creates a ${docType(
    'typedDict'
  )} from a variable number of arguments`,
  argDescriptions: {
    manyX: `The values to add to the ${docType(
      'typedDict'
    )}: Note: in Weave, the arguments are {[key:string]: value}`,
  },
  returnValueDescription: `The ${docType('typedDict')}`,
  renderInfo: {
    type: 'dictionaryLiteral',
  },
  returnType: inputs => {
    // const argValues = Object.values(inputs);
    return typedDict(_.mapValues(inputs, n => n.type) as any);
  },
  resolver: inputs => {
    return inputs;
  },
});

export const opTimestamp = makeOp({
  hidden: true,
  name: 'timestamp',
  argTypes: {timestampISO: 'string'},
  description: `Creates a ${docType(
    'timestamp'
  )} from a variable number of arguments`,
  argDescriptions: {
    dateISO: `An ISO date string to convert to a ${docType('timestamp')}`,
  },
  returnValueDescription: `The ${docType('timestamp')}`,
  renderInfo: {
    type: 'function',
  },
  returnType: inputs => {
    return {type: 'union', members: ['none', {type: 'timestamp'}]};
  },
  resolver: inputs => {
    const date = new Date(inputs.timestampISO);
    const timestamp = date.getTime();
    if (isNaN(timestamp)) {
      return null;
    }
    return timestamp;
  },
});
