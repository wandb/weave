import {toWeaveType} from '@wandb/weave/components/Panel2/toWeaveType';
import {
  callOpVeryUnsafe,
  constFunction,
  constNumber,
  constString,
  InputTypes,
  isListLike,
  isTypedDictLike,
  listObjectType,
  Node,
  opAnd,
  opCount,
  opDict,
  opFilter,
  opGet,
  opGroupby,
  opGroupGroupKey,
  opIsNone,
  opMap,
  opNumberMult,
  opOr,
  opPick,
  // opProjectRun,
  opRefToUri,
  // opRootProject,
  // opRunHistory3,
  opStringEndsWith,
  opStringEqual,
  opStringStartsWith,
  OutputType,
  Type,
  typedDictPropertyTypes,
  VarNode,
  varNode,
} from '@wandb/weave/core';
import * as _ from 'lodash';

import {WILDCARD_ARTIFACT_VERSION_AND_PATH} from '../Browse3/pages/wfReactInterface/constants';
import {
  RawSpanFromStreamTableEra,
  RawSpanFromStreamTableEraWithFeedback,
} from '../Browse3/pages/wfReactInterface/wfDataModelHooksInterface';

export interface StreamId {
  entityName: string;
  projectName: string;
  streamName: string;
}

export interface CallFilter {
  opUris?: string[];
  inputUris?: string[];
  outputUris?: string[];
  traceId?: string;
  parentIds?: string[];
  traceRootsOnly?: boolean;
  callIds?: string[];
}

export type Call = RawSpanFromStreamTableEra;
export type Span = Call;
export type SpanWithFeedback = RawSpanFromStreamTableEraWithFeedback;

export interface TraceSpan {
  traceId: string;
  spanId?: string;
}

// A subset of OpDefBase from weave core.
export interface OpSignature {
  inputTypes: InputTypes;

  // return type (may be a function of arguments)
  outputType: OutputType;
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
          _arg_order: {type: 'list', objectType: 'string'},
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
      status_code: 'string',
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
  // Going straight to the opRunHistory call saves about 1 second per request in
  // lookup time, but does not have the correct types, resulting in backend
  // errors or missing data until compaction.
  // const streamTableRowsNode = opRunHistory3({
  //   run: opProjectRun({
  //     project: opRootProject({
  //       entityName: constString(streamId.entityName),
  //       projectName: constString(streamId.projectName),
  //     }),
  //     runName: constString(streamId.streamName),
  //   }),
  // });
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
        status_code: opPick({
          obj: row,
          key: constString('status_code'),
        }),
        exception: opPick({
          obj: row,
          key: constString('exception'),
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
        attributes: opPick({
          obj: row,
          key: constString('attributes'),
        } as any) as any,
        summary: opPick({
          obj: row,
          key: constString('summary'),
        } as any) as any,
      } as any)
    ) as Node,
  });
};

const buildOpUriClause = (
  rowVar: VarNode<Type>,
  opUri: string,
  key: string
) => {
  if (opUri.endsWith(WILDCARD_ARTIFACT_VERSION_AND_PATH)) {
    return opAnd({
      lhs: opStringStartsWith({
        lhs: opPick({
          obj: rowVar,
          key: constString(key),
        }),
        rhs: constString(
          opUri.slice(0, -WILDCARD_ARTIFACT_VERSION_AND_PATH.length)
        ),
      }),
      rhs: opStringEndsWith({
        lhs: opPick({
          obj: rowVar,
          key: constString(key),
        }),
        rhs: constString('/obj'),
      }),
    });
  } else {
    return opStringEqual({
      lhs: opPick({
        obj: rowVar,
        key: constString(key),
      }),
      rhs: constString(opUri),
    });
  }
};

const makeFilterExpr = (filters: CallFilter): Node | undefined => {
  const rowVar = varNode(listObjectType(callsTableWeaveType), 'row');
  const filterClauses: Node[] = [];
  if (filters.opUris != null && filters.opUris.length > 0) {
    let clause = buildOpUriClause(rowVar, filters.opUris[0], 'name');
    for (const uri of filters.opUris.slice(1)) {
      clause = opOr({
        lhs: clause,
        rhs: buildOpUriClause(rowVar, uri, 'name'),
      });
    }
    filterClauses.push(clause);
  }
  if (filters.inputUris != null) {
    for (const inputUri of filters.inputUris) {
      filterClauses.push(
        opOr({
          lhs: opStringEqual({
            lhs: opRefToUri({
              self: opPick({
                obj: rowVar,
                key: constString('inputs._ref0'),
              }) as any,
            }),
            rhs: constString(inputUri),
          }) as any,
          rhs: opOr({
            lhs: opStringEqual({
              lhs: opRefToUri({
                self: opPick({
                  obj: rowVar,
                  key: constString('inputs._ref1'),
                }) as any,
              }),
              rhs: constString(inputUri),
            }) as any,
            rhs: opStringEqual({
              lhs: opRefToUri({
                self: opPick({
                  obj: rowVar,
                  key: constString('inputs._ref2'),
                }) as any,
              }),
              rhs: constString(inputUri),
            }) as any,
          }) as any,
        }) as any
      );
    }
  }
  if (filters.outputUris != null) {
    for (const outputUri of filters.outputUris) {
      filterClauses.push(
        opStringEqual({
          lhs: opRefToUri({
            self: opPick({
              obj: rowVar,
              key: constString('output._ref0'),
            }) as any,
          }),
          rhs: constString(outputUri),
        })
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
  if (filters.parentIds != null && filters.parentIds.length > 0) {
    let clause = opStringEqual({
      lhs: opPick({
        obj: rowVar,
        key: constString('parent_id'),
      }),
      rhs: constString(filters.parentIds[0]),
    });
    for (const callId of filters.parentIds.slice(1)) {
      clause = opOr({
        lhs: clause,
        rhs: opStringEqual({
          lhs: opPick({
            obj: rowVar,
            key: constString('parent_id'),
          }),
          rhs: constString(callId),
        }),
      });
    }
    filterClauses.push(clause);
  }

  if (filters.traceRootsOnly) {
    filterClauses.push(
      opIsNone({
        val: opPick({
          obj: rowVar,
          key: constString('parent_id'),
        }),
      })
    );
  }
  if (filters.callIds != null && filters.callIds.length > 0) {
    let clause = opStringEqual({
      lhs: opPick({
        obj: rowVar,
        key: constString('span_id'),
      }),
      rhs: constString(filters.callIds[0]),
    });
    for (const callId of filters.callIds.slice(1)) {
      clause = opOr({
        lhs: clause,
        rhs: opStringEqual({
          lhs: opPick({
            obj: rowVar,
            key: constString('span_id'),
          }),
          rhs: constString(callId),
        }),
      });
    }
    filterClauses.push(clause);
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
    filterFn: constFunction(
      {row: listObjectType(stNode.type)},
      ({row}) => filterExpr
    ),
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

export const opSignatureFromSpan = (span: Span): OpSignature => {
  const inputs = span.inputs;
  const inputOrder: string[] =
    inputs._input_order ?? Object.keys(inputs).filter(k => !k.startsWith('_'));
  const inputTypes = _.fromPairs(
    inputOrder
      .map(k => {
        return [k, toWeaveType(inputs[k])];
      })
      .filter(([k, v]) => v !== 'none')
  );
  const outputType = toWeaveType(span.output);
  return {
    inputTypes,
    outputType,
  };
};

const feedbackTableType: Type = {
  type: 'list',
  objectType: {
    type: 'typedDict',
    propertyTypes: {
      run_id: 'string',
      feedback_id: 'string',
      timestamp: 'any',
      feedback: 'any',
    },
  },
};

export const feedbackTableObjNode = (
  entityName: string,
  projectName: string
) => {
  const predsRefStr = `wandb-artifact:///${entityName}/${projectName}/run-feedback:latest/obj`;
  return opGet({
    uri: constString(predsRefStr),
  });
};

export const feedbackTableNode = (entityName: string, projectName: string) => {
  const streamTableRowsNode = callOpVeryUnsafe('stream_table-rows', {
    stream_table: feedbackTableObjNode(entityName, projectName),
  }) as Node;
  streamTableRowsNode.type = feedbackTableType;
  return streamTableRowsNode;
};

export const runFeedbackNode = (
  entityName: string,
  projectName: string,
  runId: string
) => {
  const feedbackNode = feedbackTableNode(entityName, projectName);
  return opFilter({
    arr: feedbackNode,
    filterFn: constFunction({row: listObjectType(feedbackNode.type)}, ({row}) =>
      opStringEqual({
        lhs: opPick({
          obj: row,
          key: constString('run_id'),
        }),
        rhs: constString(runId),
      })
    ),
  });
};

export const selectAll = (item: Node) => {
  if (!isTypedDictLike(item.type)) {
    throw new Error('Expected typed dict');
  }
  const keys = Object.keys(typedDictPropertyTypes(item.type));
  const dictOpArgs = _.fromPairs(
    keys.map(k => [k, opPick({obj: item, key: constString(k)})])
  );
  return opDict(dictOpArgs as any);
};

export const listSelectAll = (list: Node) => {
  if (!isListLike(list.type)) {
    throw new Error('Expected list');
  }
  return opMap({
    arr: list,
    mapFn: constFunction({row: listObjectType(list.type)}, ({row}) =>
      selectAll(row)
    ),
  });
};
