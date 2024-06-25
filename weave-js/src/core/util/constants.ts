export const MAX_RUN_LIMIT = 100;
export const MAX_DATE_MS = 8640000000000000; // max date value, https://stackoverflow.com/a/28425951/15867258

// If true, attach useful debugging fn's to globalThis:
//
// op(opName)    Access an op by name.  Positional args are mapped
//               to the expected input object by definition order and
//               js primitives are automatically wrapped w/ `constXYZ`
// cgQuery(node) Async query for node.
//
// Example:
// cgQuery(op('project-name')(op('root-project')('shawn','fasion-sweep'))
export const DEBUG_ATTACH_TO_GLOBAL_THIS = false;
export const LOG_DEBUG_MESSAGES = false;
