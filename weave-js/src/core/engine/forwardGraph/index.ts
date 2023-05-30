import {BaseForwardGraph} from './base';
import {HashingStorage} from './hashing';
import {RefStorage} from './ref';
import {ForwardGraph} from './types';

export type {ForwardGraph, ForwardOp} from './types';
export * from './util';

export function newForwardGraph(): ForwardGraph {
  return new BaseForwardGraph(new HashingStorage());
}

export function newRefForwardGraph(): ForwardGraph {
  return new BaseForwardGraph(new RefStorage());
}
