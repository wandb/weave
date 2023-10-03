import {
  callOpVeryUnsafe,
  constNumber,
  constString,
  opGet,
  Node,
  constFunction,
  constNodeUnsafe,
  Type,
  varNode,
  listObjectType,
  opRefEqual,
  opPick,
  opOr,
  opFilter,
  opMap,
  opDict,
  opGroupGroupKey,
  opCount,
  opGroupby,
  opStringEqual,
  opAnd,
  opNumberMult,
} from '@wandb/weave/core';

export interface StreamId {
  entityName: string;
  projectName: string;
  streamName: string;
}

export interface CallFilter {
  opUri?: string;
  inputUris?: string[];
  traceId?: string;
}

// TODO: Put into Types
const refWeaveType = {
  type: 'FilesystemArtifactRef',
  _base_type: {
    type: 'Ref',
    objectType: 'any',
  },
  objectType: 'any',
} as unknown as Type;

const callsTableWeaveType: Type = {
  type: 'list',
  objectType: {
    type: 'typedDict',
    propertyTypes: {
      name: 'string',
      inputs: {
        type: 'typedDict',
        propertyTypes: {
          _ref0: refWeaveType,
          _ref1: refWeaveType,
        },
      },
      output: 'any',
      summary: 'any',
      span_id: 'string',
      trace_id: 'string',
      parent_id: 'string',
      timestamp: 'any',
      start_time_s: 'number',
      end_time_s: 'number',
    },
  },
};

export const callsTableNode = (streamId: StreamId) => {
  const predsRefStr = `wandb-artifact:///${streamId.entityName}/${streamId.projectName}/${streamId.streamName}:latest/obj`;
  const streamTableRowsNode = callOpVeryUnsafe('stream_table-rows', {
    stream_table: opGet({
      uri: constString(predsRefStr),
    }),
  }) as Node;
  streamTableRowsNode.type = callsTableWeaveType;
  return streamTableRowsNode;
};

export const callsTableSelect = (stNode: Node) => {
  return opMap({
    arr: stNode,
    mapFn: constFunction({row: listObjectType(stNode.type)}, ({row}) =>
      opDict({
        name: opPick({
          obj: row,
          key: constString('name'),
        }),
        inputs: opPick({
          obj: row,
          key: constString('inputs'),
        }),
        output: opPick({
          obj: row,
          key: constString('output'),
        }),
        timestamp: opPick({
          obj: row,
          key: constString('timestamp'),
        }),
        trace_id: opPick({
          obj: row,
          key: constString('trace_id'),
        }),
        parent_id: opPick({
          obj: row,
          key: constString('parent_id'),
        }),
        span_id: opPick({
          obj: row,
          key: constString('span_id'),
        }),
        start_time_ms: opNumberMult({
          lhs: opPick({
            obj: row,
            key: constString('start_time_s'),
          }),
          rhs: constNumber(1000),
        }),
        end_time_ms: opNumberMult({
          lhs: opPick({
            obj: row,
            key: constString('end_time_s'),
          }),
          rhs: constNumber(1000),
        }),
        summary: opPick({
          obj: row,
          key: constString('summary'),
        } as any) as any,
      } as any)
    ) as Node,
  });
};

const makeFilterExpr = (filters: CallFilter): Node | undefined => {
  const rowVar = varNode(listObjectType(callsTableWeaveType), 'row');
  const filterClauses: Node[] = [];
  if (filters.opUri != null) {
    filterClauses.push(
      opStringEqual({
        lhs: opPick({
          obj: rowVar,
          key: constString('name'),
        }),
        rhs: constString(filters.opUri),
      }) as Node
    );
  }
  if (filters.inputUris != null) {
    for (const inputUri of filters.inputUris) {
      filterClauses.push(
        opOr({
          lhs: opRefEqual({
            lhs: opPick({
              obj: rowVar,
              key: constString('inputs._ref0'),
            }),
            rhs: constNodeUnsafe(refWeaveType, inputUri),
          }) as any,
          rhs: opRefEqual({
            lhs: opPick({
              obj: rowVar,
              key: constString('inputs._ref1'),
            }),
            rhs: constNodeUnsafe(refWeaveType, inputUri),
          }) as any,
        }) as any
      );
    }
  }
  if (filters.traceId != null) {
    filterClauses.push(
      opStringEqual({
        lhs: opPick({
          obj: rowVar,
          key: constString('trace_id'),
        }),
        rhs: constString(filters.traceId),
      })
    );
  }

  let expr = filterClauses[0];
  for (const clause of filterClauses.slice(1)) {
    expr = opAnd({
      lhs: expr,
      rhs: clause,
    }) as Node;
  }
  return expr;
};

export const callsTableFilter = (stNode: Node, filters: CallFilter) => {
  const filterExpr = makeFilterExpr(filters);
  if (filterExpr == null) {
    return stNode;
  }
  return opFilter({
    arr: stNode,
    filterFn: constFunction({row: 'any'}, ({row}) => filterExpr),
  }) as Node;
};

export const callsTableOpCounts = (stNode: Node) => {
  const groups = opGroupby({
    arr: stNode,
    groupByFn: constFunction(
      {row: listObjectType(callsTableWeaveType)},
      ({row}) =>
        opPick({
          obj: row,
          key: constString('name'),
        }) as any
    ),
  });
  return opMap({
    arr: groups,
    mapFn: constFunction(
      {row: listObjectType(groups.type)},
      ({row}) =>
        opDict({
          name: opGroupGroupKey({
            obj: row,
          }),
          count: opCount({
            arr: row,
          }),
        } as any) as any
    ),
  });
};

export const callsTableSelectTraces = (stNode: Node) => {
  const groups = opGroupby({
    arr: stNode,
    groupByFn: constFunction(
      {row: listObjectType(callsTableWeaveType)},
      ({row}) =>
        opPick({
          obj: row,
          key: constString('trace_id'),
        }) as any
    ),
  });
  return opMap({
    arr: groups,
    mapFn: constFunction(
      {row: listObjectType(groups.type)},
      ({row}) =>
        opDict({
          trace_id: opGroupGroupKey({
            obj: row,
          }),
          span_count: opCount({
            arr: row,
          }),
        } as any) as any
    ),
  });
};
