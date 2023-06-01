// Provides stubbable server APIs.
//
// Many compute graph functions take context as their first argument.
// They use methods provided in context to make API calls.
// You can use the useContextBound hook in cgreact to make get
// versions of those functions that have the context populated
// by whatever is globally set.

import type {Frame} from './model/graph/types';
import type {ServerAPI} from './serverApi';
import type {Tracer} from './traceTypes';

export interface FreshContext {
  backend: ServerAPI;
  frame: Frame;
}

export interface ResolverContext extends FreshContext {
  trace: Tracer;
}
