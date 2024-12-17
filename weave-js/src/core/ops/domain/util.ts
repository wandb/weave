import {dict, list, typedDict, union} from '../../model';

/**
 * `connectionToNodes` is a helper function that converts a `connection` type
 * returned from gql to its list of nodes. In many, many location in our
 * application, the GQL schema looks like:
 *
 * type Thing {
 * }
 *
 * type House {
 *  # Sometimes this is optional, sometimes required
 *  fullOf(): ThingConnection!
 * }
 *
 * type ThingEdge {
 *  # Sometimes this is optional, sometimes required
 *  node: Thing
 * }
 *
 * type ThingConnection {
 *  # in all cases checked, this is always a required list of required items
 *  edges: [ThingEdge!]!
 * }
 *
 * Now, if the user does not have authorization to view a Thing, then the
 * `Edge`'s `node` field will be null. Our resolvers all expect to return a list
 * of non-null nodes. However, each resolver was checking for nulls in
 * inconsistent ways. So, this function can be used by resolvers to walk an
 * object that is expected (but not required) to be a `connection` type. It will
 * handle nulls or invalid structure properly, and filter out the nulls.
 *
 * This problem was dormant for a long time until we started enforcing some auth
 * on certain edges, resulting in nulls flowing through the system.
 */
type MaybeConnection<T> =
  | {
      edges?: Array<{node?: T}>;
    }
  | null
  | undefined;
export const connectionToNodes = <T>(connection: MaybeConnection<T>): T[] =>
  (connection?.edges ?? [])
    .map(edge => edge?.node)
    .filter(node => node != null) as T[];

const traceFilterPropertyTypes = {
  trace_roots_only: union(['none', 'boolean']),
  op_names: union(['none', list('string')]),
  input_refs: union(['none', list('string')]),
  output_refs: union(['none', list('string')]),
  parent_ids: union(['none', list('string')]),
  trace_ids: union(['none', list('string')]),
  call_ids: union(['none', list('string')]),
  wb_user_ids: union(['none', list('string')]),
  wb_run_ids: union(['none', list('string')]),
};

export const traceFilterType = union([
  'none',
  typedDict(traceFilterPropertyTypes, Object.keys(traceFilterPropertyTypes)),
]);
export const traceLimitType = union(['none', 'number']);
export const traceOffsetType = union(['none', 'number']);
export const traceSortByType = union([
  'none',
  list(typedDict({field: 'string', direction: 'string'})),
]);
export const traceQueryType = union(['none', dict('any')]);
