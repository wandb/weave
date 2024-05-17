/**
 * TODO:
 *    * (Ongoing) Continue to re-organize symbols / files
 *    * Address Refactor Groups (Labelled with CPR)
 *        * (GeneralRefactoring) Moving code around
 *        * (Ref Expansion) In-Mem Expansion Behind Hook
 *        * (Flattening) Refactor the flattening logic to be uniform and consistent
 *        * (CC+Hidden) Temp Disable CC and Hidden Fields (Optional)
 *    * Implement Controlled State for Sort / Filter / Pagination
 *    * Implement the custom hook that populates the data (in-memory to start):
 *        * Sort/Filter/Pagination/Expansion all done behind the hook!
 */

import {Autocomplete, Chip, FormControl, ListItem} from '@mui/material';
import {Box, Typography} from '@mui/material';
import {
  DataGridPro,
  GridApiPro,
  GridColDef,
  GridColumnGroup,
  GridColumnGroupingModel,
  GridColumnVisibilityModel,
  GridRowSelectionModel,
  useGridApiRef,
} from '@mui/x-data-grid-pro';
import * as Colors from '@wandb/weave/common/css/color.styles';
import {Button} from '@wandb/weave/components/Button';
import {Checkbox} from '@wandb/weave/components/Checkbox/Checkbox';
import {UserLink} from '@wandb/weave/components/UserLink';
import _ from 'lodash';
import React, {
  ComponentProps,
  FC,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import styled from 'styled-components';

import {hexToRGB} from '../../../../../../common/css/utils';
import {A, TargetBlank} from '../../../../../../common/util/links';
import {monthRoundedTime} from '../../../../../../common/util/time';
import {
  isObjectTypeLike,
  isTypedDictLike,
  Type,
  typedDictPropertyTypes,
} from '../../../../../../core';
import {useDeepMemo} from '../../../../../../hookUtils';
import {parseRef} from '../../../../../../react';
import {ErrorBoundary} from '../../../../../ErrorBoundary';
import {LoadingDots} from '../../../../../LoadingDots';
import {Timestamp} from '../../../../../Timestamp';
import {flattenObject} from '../../../Browse2/browse2Util';
import {CellValue} from '../../../Browse2/CellValue';
import {CollapseGroupHeader} from '../../../Browse2/CollapseGroupHeader';
import {CustomGroupedColumnHeader} from '../../../Browse2/CustomGroupedColumnHeader';
import {ExpandHeader} from '../../../Browse2/ExpandHeader';
import {NotApplicable} from '../../../Browse2/NotApplicable';
import {RefValue} from '../../../Browse2/RefValue';
import {
  columnHasRefs,
  columnRefs,
  computeTableStats,
  getInputColumns,
  useColumnVisibility,
} from '../../../Browse2/tableStats';
import {baseContext, WeaveHeaderExtrasContext} from '../../context';
import {StyledPaper} from '../../StyledAutocomplete';
import {StyledDataGrid} from '../../StyledDataGrid';
import {StyledTextField} from '../../StyledTextField';
import {BoringColumnInfo} from '../CallPage/BoringColumnInfo';
import {OverflowMenu} from '../CallPage/OverflowMenu';
import {Empty} from '../common/Empty';
import {
  EMPTY_PROPS_EVALUATIONS,
  EMPTY_PROPS_TRACES,
} from '../common/EmptyContent';
import {isPredictAndScoreOp} from '../common/heuristics';
import {CallLink, opNiceName} from '../common/Links';
import {FilterLayoutTemplate} from '../common/SimpleFilterableDataTable';
import {StatusChip} from '../common/StatusChip';
import {
  renderCell,
  truncateID,
  useControllableState,
  useURLSearchParamsDict,
} from '../util';
import {
  DICT_KEY_EDGE_NAME,
  OBJECT_ATTR_EDGE_NAME,
} from '../wfReactInterface/constants';
import {useWFHooks} from '../wfReactInterface/context';
import {
  objectVersionNiceString,
  opVersionRefOpName,
} from '../wfReactInterface/utilities';
import {
  CallSchema,
  OpVersionKey,
} from '../wfReactInterface/wfDataModelHooksInterface';
import {useCurrentFilterIsEvaluationsFilter} from './CallsPage';
import {WFHighLevelCallFilter} from './callsTableFilter';
import {getEffectiveFilter} from './callsTableFilter';
import {useOpVersionOptions} from './callsTableFilter';
import {ALL_TRACES_OR_CALLS_REF_KEY} from './callsTableFilter';
import {useInputObjectVersionOptions} from './callsTableFilter';
import {useOutputObjectVersionOptions} from './callsTableFilter';
import {useCallsForQuery} from './callsTableQuery';

const VisibilityAlert = styled.div`
  background-color: ${hexToRGB(Colors.MOON_950, 0.04)};
  color: ${Colors.MOON_800};
  padding: 6px 12px;
  font-size: 16px;
  font-weight: 400;
  line-height: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
`;
VisibilityAlert.displayName = 'S.VisibilityAlert';

const VisibilityAlertText = styled.div`
  white-space: nowrap;
  flex: 1 1 auto;
  overflow: hidden;
  text-overflow: ellipsis;
`;
VisibilityAlertText.displayName = 'S.VisibilityAlertText';

const VisibilityAlertAction = styled.div`
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
`;
VisibilityAlertAction.displayName = 'S.VisibilityAlertAction';

const OP_FILTER_GROUP_HEADER = 'Op';

export const CallsTable: FC<{
  entity: string;
  project: string;
  frozenFilter?: WFHighLevelCallFilter;
  initialFilter?: WFHighLevelCallFilter;
  // Setting this will make the component a controlled component. The parent
  // is responsible for updating the filter.
  onFilterUpdate?: (filter: WFHighLevelCallFilter) => void;
  hideControls?: boolean;
  ioColumnsOnly?: boolean;
}> = ({
  entity,
  project,
  initialFilter,
  onFilterUpdate,
  frozenFilter,
  hideControls,
  ioColumnsOnly,
}) => {
  // Load Context
  const {
    derived: {useGetRefsType},
  } = useWFHooks();
  const {addExtra, removeExtra} = useContext(WeaveHeaderExtrasContext);

  // Setup Ref to underlying table
  const apiRef = useGridApiRef();
  const apiRefIsReady =
    apiRef.current && Object.keys(apiRef.current).length > 0;

  // Register Export Button
  useEffect(() => {
    addExtra('exportRunsTableButton', {
      node: <ExportRunsTableButton tableRef={apiRef} />,
    });

    return () => removeExtra('exportRunsTableButton');
  }, [apiRef, addExtra, removeExtra]);

  // Make sure we respect the controlling nature of the filter
  const [filter, setFilter] = useControllableState(
    initialFilter ?? {},
    onFilterUpdate
  );

  // Calculate the effective filter
  const effectiveFilter = useMemo(
    () => getEffectiveFilter(filter, frozenFilter),
    [filter, frozenFilter]
  );

  // Fetch the calls
  const calls = useCallsForQuery(entity, project, effectiveFilter);
  if (calls.refetch) {
    baseContext.refetchCalls = calls.refetch;
  }
  const callsLoading = calls.loading;
  const callsResult = useMemo(() => calls.result ?? [], [calls.result]);

  // Now, there are 4 primary controls:
  // 1. Op Version
  // 2. Input Object Version
  // 3. Output Object Version
  // 4. Parent ID
  //
  // The following chunks of code are responsible for determining the
  // values for the options as well as the selected values for each of
  // these controls. They each follow the pattern of:
  //
  // const control = useControlOptions(...)
  // const selectedControl = useMemo(() => {...}, [...])
  //

  // 1. Op Version
  const opVersionOptions = useOpVersionOptions(
    entity,
    project,
    effectiveFilter
  );
  const selectedOpVersionOption = useMemo(() => {
    const opVersionRef = effectiveFilter.opVersionRefs?.[0] ?? null;
    return opVersionRef ?? ALL_TRACES_OR_CALLS_REF_KEY;
  }, [effectiveFilter.opVersionRefs]);

  // 2. Input Object Version
  const inputObjectVersionOptions =
    useInputObjectVersionOptions(effectiveFilter);
  const selectedInputObjectVersion = useMemo(() => {
    const inputObjectVersionRef =
      effectiveFilter.inputObjectVersionRefs?.[0] ?? null;
    return inputObjectVersionRef
      ? inputObjectVersionOptions[inputObjectVersionRef]
      : null;
  }, [inputObjectVersionOptions, effectiveFilter.inputObjectVersionRefs]);

  // 3. Output Object Version
  const outputObjectVersionOptions =
    useOutputObjectVersionOptions(effectiveFilter);
  const selectedOutputObjectVersion = useMemo(() => {
    const outputObjectVersionRef =
      effectiveFilter.outputObjectVersionRefs?.[0] ?? null;
    return outputObjectVersionRef
      ? outputObjectVersionOptions[outputObjectVersionRef]
      : null;
  }, [effectiveFilter.outputObjectVersionRefs, outputObjectVersionOptions]);

  // 4. Parent ID
  const parentIdOptions = useParentIdOptions(entity, project, effectiveFilter);
  const selectedParentId = useMemo(
    () =>
      effectiveFilter.parentId
        ? parentIdOptions[effectiveFilter.parentId]
        : null,
    [effectiveFilter.parentId, parentIdOptions]
  );

  // END OF CPR FACTORED CODE

  // CPR (Tim) - (Ref Expansion): Column Expansion needs to be moved to a "table state" object in the future
  const [expandedRefCols, setExpandedRefCols] = useState<Set<string>>(
    new Set<string>().add('input.example')
  );
  const onExpand = (col: string) => {
    setExpandedRefCols(prevState => new Set(prevState).add(col));
  };
  const onCollapse = (col: string) => {
    setExpandedRefCols(prevState => {
      const newSet = new Set(prevState);
      newSet.delete(col);
      return newSet;
    });
  };

  // CPR (Tim) - (Ref Expansion): This is going to go away completely once we move to remove expansion
  const [expandedColInfo, setExpandedColInfo] = useState<ExtraColumns>({});

  // CPR (Tim) - (CC+Hidden): We should change `isSingleOpVersion` and `isSingleOp` to be derived from the filter, not requiring a full pass
  const isSingleOpVersion = useMemo(() => {
    return _.uniq(callsResult.map(span => span.rawSpan.name)).length === 1;
  }, [callsResult]);
  const uniqueSpanNames = useMemo(() => {
    return _.uniq(callsResult.map(span => span.spanName));
  }, [callsResult]);
  const isSingleOp = useMemo(() => {
    return uniqueSpanNames.length === 1;
  }, [uniqueSpanNames]);

  // CPR (Tim) - (Flattening): This needs to be removed completely - we should not need to put `_result` in anywhere.
  // In fact, it should be removed from the read client as well. When we flatten the data, we can handle
  // primitive collisions with containers there.
  const newSpans = useMemo(
    () =>
      callsResult.map(s => ({
        ...s,
        output: s.rawSpan.output == null ? {_result: null} : s.rawSpan.output,
      })),
    [callsResult]
  );

  // CPR (Tim) - (Flattening): This is not a generally correct - why are we doing this?!?
  let onlyOneOutputResult = true;
  for (const s of newSpans) {
    // get display keys
    const keys = Object.keys(
      _.omitBy(
        flattenObject(s.rawSpan.output!),
        (v, k) => v == null || (k.startsWith('_') && k !== '_result')
      )
    );
    // ensure there is only one output _result
    if (keys.length > 1 || (keys[0] && keys[0] !== '_result')) {
      onlyOneOutputResult = false;
      break;
    }
  }

  // CPR (Tim) - (Flattening): The vast majority of this is going to roll into the calls hook that we create
  // Specifically: the flattening of the data. We should make this a highly structured and
  // typed output. Moreover, since sorting is moving to the backend, we don't need anything
  // fancy here: just the id and the flattened call.
  const tableData = useMemo(() => {
    return newSpans.map((call: CallSchema) => {
      const argOrder = call.rawSpan.inputs._input_order;
      let args: Record<string, any> = {};
      if (call.rawSpan.inputs._keys) {
        for (const key of call.rawSpan.inputs._keys) {
          args[key] = call.rawSpan.inputs[key];
        }
      } else {
        args = _.fromPairs(
          Object.entries(call.rawSpan.inputs).filter(
            ([k, c]) => c != null && !k.startsWith('_')
          )
        );
      }

      if (argOrder) {
        args = _.fromPairs(argOrder.map((k: string) => [k, args[k]]));
      }

      return {
        id: call.callId,
        call,
        loading: callsLoading,
        opVersion: call.opVersionRef,
        isRoot: call.parentId == null,
        trace_id: call.traceId,
        status_code: call.rawSpan.status_code,
        timestampMs: call.rawSpan.timestamp,
        userId: call.userId,
        latency: call.rawSpan.summary.latency_s,
        ..._.mapKeys(
          _.omitBy(args, v => v == null),
          (v, k) => {
            return 'input.' + k;
          }
        ),
        ..._.mapKeys(
          _.omitBy(
            flattenObject(call.rawSpan.output!),
            (v, k) => v == null || (k.startsWith('_') && k !== '_result')
          ),
          (v, k) => {
            // If there is only one output _result, we don't need to nest it
            if (onlyOneOutputResult && k === '_result') {
              return 'output';
            }
            return 'output.' + k;
          }
        ),
        ..._.mapKeys(
          flattenObject(call.rawFeedback ?? {}),
          (v, k) => 'feedback.' + k
        ),
        ..._.mapKeys(
          flattenObject(call.rawSpan.attributes ?? {}),
          (v, k) => 'attributes.' + k
        ),
      };
    });
  }, [callsLoading, onlyOneOutputResult, newSpans]);

  // CPR (Tim) - (CC+Hidden): Move table stats (and derivative calcs) into the new hook
  const tableStats = useMemo(() => {
    return computeTableStats(tableData);
  }, [tableData]);

  // CPR (Tim) - (Ref Expansion): This entire block goes away when we move to our new hook model. We don't
  // need to calculate new columns as they are already going to be part of the data itself
  const getRefsType = useGetRefsType();
  useEffect(() => {
    const fetchData = async () => {
      for (const col of expandedRefCols) {
        if (!(col in expandedColInfo)) {
          const refs = columnRefs(tableStats, col);
          const refTypes = await getRefsType(refs);
          const extraCols = getExtraColumns(refTypes);
          if (tableStats.rowCount !== 0) {
            setExpandedColInfo(prevState => ({
              ...prevState,
              [col]: extraCols,
            }));
          }
        }
      }
    };

    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expandedRefCols, tableStats]);

  // CPR (Tim) - (CC+Hidden): I really want to just always show everything - this hiding
  // feels more confusing than it is worth and also is costly. Remove.
  const [forceShowAll, setForceShowAll] = useState(false);
  const {allShown, columnVisibilityModel: defaultVisibilityModel} =
    useColumnVisibility(tableStats, isSingleOpVersion);

  // CPR (Tim) - (GeneralRefactoring): Move all GridModel controls to a common place
  const [columnVisibilityModel, setColumnVisibilityModel] =
    useState<GridColumnVisibilityModel>(defaultVisibilityModel);

  // CPR (Tim) - (CC+Hidden): This gets removed as well
  useEffect(() => {
    if (forceShowAll) {
      // If not specified, columns default to visible.
      setColumnVisibilityModel({});
    }
  }, [forceShowAll]);

  // CPR (Tim) - (CC+Hidden): This gets removed as well
  const showVisibilityAlert = !allShown && !forceShowAll;

  // CPR (Tim) - (GeneralRefactoring): Preferably this is passed in from the top, not
  // something where we inspect URLs deep in a component. At the
  // very least this should be moved to it's own function
  // Highlight table row if it matches peek drawer.
  const query = useURLSearchParamsDict();
  const {peekPath} = query;
  const peekId = getPeekId(peekPath);
  const rowIds = useMemo(() => {
    return tableData.map(row => row.id);
  }, [tableData]);
  const [rowSelectionModel, setRowSelectionModel] =
    useState<GridRowSelectionModel>([]);
  useEffect(() => {
    if (rowIds.length === 0) {
      // Data may have not loaded
      return;
    }
    if (peekId == null) {
      // No peek drawer, clear any selection
      setRowSelectionModel([]);
    } else {
      // If peek drawer matches a row, select it.
      // If not, don't modify selection.
      if (rowIds.includes(peekId)) {
        setRowSelectionModel([peekId]);
      }
    }
  }, [rowIds, peekId]);

  // CPR (Tim) - (GeneralRefactoring): Pull out into it's own function
  // Custom logic to control path preservation preference
  const preservePath = useMemo(() => {
    return (
      uniqueSpanNames.length === 1 &&
      isPredictAndScoreOp(opNiceName(uniqueSpanNames[0]))
    );
  }, [uniqueSpanNames]);

  const [selectedCalls, setSelectedCalls] = useState<CallSchema[]>([]);

  // CPR (Tim) - (GeneralRefactoring): Yeah, there is going to be a lot here. A few general notes:
  // * For readability: would be clean to extract each field def into a function
  // * Perhaps consider reducing the min-width for a lot of these
  const columns = useMemo(() => {
    const cols: Array<GridColDef<(typeof tableData)[number]>> = [
      {
        field: 'span_id',
        headerName: 'Trace',
        minWidth: 100,
        // This filter should be controlled by the custom filter
        // in the header
        filterable: false,
        width: 250,
        hideable: false,
        renderCell: rowParams => {
          const opVersion = rowParams.row.call.opVersionRef;
          if (opVersion == null) {
            return rowParams.row.call.spanName;
          }
          return (
            <>
              <Checkbox
                size="small"
                style={{marginRight: '8px', marginTop: '0px'}}
                checked={selectedCalls.includes(rowParams.row.call)}
                onClick={() => {
                  setSelectedCalls(prev => {
                    if (prev.includes(rowParams.row.call)) {
                      return prev.filter(call => call !== rowParams.row.call);
                    }
                    return [...prev, rowParams.row.call];
                  });
                }}
              />
              <CallLink
                entityName={entity}
                projectName={project}
                opName={opVersionRefOpName(opVersion)}
                callId={rowParams.row.id}
                fullWidth={true}
                preservePath={preservePath}
              />
            </>
          );
        },
      },
      ...(isSingleOp && !isSingleOpVersion
        ? [
            {
              field: 'opVersionIndex',
              headerName: 'Op Version',
              type: 'number',
              align: 'right' as const,
              disableColumnMenu: true,
              sortable: false,
              filterable: false,
              resizable: false,
              renderCell: (cellParams: any) => (
                <OpVersionIndexText opVersionRef={cellParams.row.opVersion} />
              ),
            },
          ]
        : []),
      // {
      //   field: 'run_id',
      //   headerName: 'Run',
      //   disableColumnMenu: true,
      //   renderCell: cellParams => {
      //     return (
      //       <div style={{margin: 'auto'}}>
      //         {cellParams.row.call.runId ?? <NotApplicable />}
      //       </div>
      //     );
      //   },
      // },
      {
        field: 'status_code',
        headerName: 'Status',
        headerAlign: 'center',
        sortable: false,
        disableColumnMenu: true,
        resizable: false,
        // Again, the underlying value is not obvious to the user,
        // so the default free-form filter is likely more confusing than helpful.
        filterable: false,
        width: 59,
        renderCell: cellParams => {
          return (
            <div style={{margin: 'auto'}}>
              <StatusChip value={cellParams.row.status_code} iconOnly />
            </div>
          );
        },
      },
    ];

    // CPR (Tim) - (Flattening): I still don't understand how inputs/outputs/attributes/summary aren't
    // all handled in the same generic way. Lets do that! Also, we don't have any concept
    // of "_keys" anymore, so we can remove all that junk. The flattening will be done before-hand.
    const colGroupingModel: GridColumnGroupingModel = [];
    const row0 = newSpans[0];
    if (row0 == null) {
      return {cols: [], colGroupingModel: []};
    }

    const attributesKeys: {[key: string]: true} = {};
    newSpans.forEach(span => {
      for (const [k, v] of Object.entries(
        flattenObject(span.rawSpan.attributes ?? {})
      )) {
        if (v != null && k !== '_keys') {
          attributesKeys[k] = true;
        }
      }
    });

    const attributesOrder = Object.keys(attributesKeys);
    const attributesGrouping = buildTree(attributesOrder, 'attributes');
    colGroupingModel.push(attributesGrouping);
    for (const key of attributesOrder) {
      if (!key.startsWith('_')) {
        cols.push({
          flex: 1,
          minWidth: 150,
          field: 'attributes.' + key,
          headerName: key.split('.').slice(-1)[0],
          renderCell: cellParams => {
            return renderCell((cellParams.row as any)['attributes.' + key]);
          },
        });
      }
    }

    // CPR (Tim) - (Flattening): Yeah, this is going to change likely.
    // Gets the children of a expanded group field(a ref that has been expanded)
    // returns an array of column definitions, for the children
    const getGroupChildren = (groupField: string) => {
      // start children array with self
      const colGroupChildren = [{field: groupField}];
      // get the expanded columns for the group field
      const expandCols = expandedColInfo[groupField] ?? [];
      // for each expanded column, add a column definition
      for (const col of expandCols) {
        // Don't show name or description column for expanded refs
        if (col.path === 'name' || col.path === 'description') {
          continue;
        }
        const expandField = groupField + '.' + col.path;
        cols.push({
          flex: 1,
          field: expandField,
          // Sorting on expanded ref columns is not supported
          sortable: false,
          // Filtering on expanded ref columns is not supported
          filterable: false,
          renderHeader: headerParams => (
            <CustomGroupedColumnHeader field={headerParams.field} />
          ),
          renderCell: cellParams => {
            const weaveRef = (cellParams.row as any)[groupField];
            if (weaveRef === undefined) {
              return <NotApplicable />;
            }
            return (
              <ErrorBoundary>
                <RefValue weaveRef={weaveRef} attribute={col.path} />
              </ErrorBoundary>
            );
          },
        });
        colGroupChildren.push({field: expandField});
      }
      return colGroupChildren;
    };

    const addColumnGroup = (groupName: string, colOrder: string[]) => {
      const colGroup: GridColumnGroup = {
        // input -> inputs, output -> outputs
        groupId: groupName + 's',
        children: [],
      };

      for (const key of colOrder) {
        const field = groupName + '.' + key;
        const fields = key.split('.');
        const isExpanded = expandedRefCols.has(field);
        cols.push({
          ...(isExpanded
            ? {
                // if the ref is expanded it will only be an icon and we want to give the ref icon less column space
                width: 100,
              }
            : {
                flex: 1,
                minWidth: 150,
              }),
          field,
          renderHeader: () => {
            const hasExpand = columnHasRefs(tableStats, field);
            return (
              <ExpandHeader
                // if the field is a flattened field, use the last key as the header
                headerName={isExpanded ? 'Ref' : fields.slice(-1)[0]}
                field={field}
                hasExpand={hasExpand && !isExpanded}
                onExpand={onExpand}
              />
            );
          },
          renderCell: cellParams => {
            if (field in cellParams.row) {
              const value = (cellParams.row as any)[field];
              return (
                <ErrorBoundary>
                  <CellValue value={value} isExpanded={isExpanded} />
                </ErrorBoundary>
              );
            }
            return <NotApplicable />;
          },
        });

        // if ref is expanded add the ref children to the colGroup
        if (isExpanded) {
          colGroup.children.push({
            groupId: field,
            headerName: key,
            // Nests all the children here
            children: getGroupChildren(field),
            renderHeaderGroup: () => {
              return (
                <CollapseGroupHeader
                  headerName={key}
                  field={field}
                  onCollapse={onCollapse}
                />
              );
            },
          });
        } else {
          // if ref is not expanded add the column to the colGroup
          addToTree(colGroup, fields, field, 0);
        }
      }
      colGroupingModel.push(colGroup);
    };

    // CPR (Tim) - (Flattening): Refactor this away
    // Add input columns
    const inputOrder = !isSingleOpVersion
      ? getInputColumns(tableStats)
      : row0.rawSpan.inputs._arg_order ??
        row0.rawSpan.inputs._keys ??
        Object.keys(_.omitBy(row0.rawSpan.inputs, v => v == null)).filter(
          k => !k.startsWith('_')
        );
    addColumnGroup('input', inputOrder);

    // Add output columns
    if (!onlyOneOutputResult) {
      // All output keys as we don't have the order key yet.
      const outputKeys: {[key: string]: true} = {};
      newSpans.forEach(span => {
        for (const [k, v] of Object.entries(
          flattenObject(span.rawSpan.output ?? {})
        )) {
          if (v != null && (!k.startsWith('_') || k === '_result')) {
            outputKeys[k] = true;
          }
        }
      });

      const outputOrder = Object.keys(outputKeys);
      addColumnGroup('output', outputOrder);
      // CPR (Tim) - (Flattening): Pretty sure this else branch goes away (or rather the one above.)
    } else {
      // If there is only one output _result, we don't need to do all the work on outputs
      // we add one special group from the _result and allow it to be expanded one level
      const colGroup: GridColumnGroup = {
        groupId: 'outputs',
        children: [],
        headerName: 'outputs',
        renderHeaderGroup: () => {
          return (
            <CollapseGroupHeader
              headerName={'output'}
              field={'output'}
              onCollapse={onCollapse}
            />
          );
        },
      };

      const isExpanded = expandedRefCols.has('output');
      cols.push({
        ...(isExpanded
          ? {
              // if the ref is expanded it will only be an icon and we want to give the ref icon less column space
              width: 100,
            }
          : {
              flex: 1,
              minWidth: 150,
            }),
        field: 'output',
        renderHeader: () => {
          const hasExpand = columnHasRefs(tableStats, 'output');
          return (
            <ExpandHeader
              // if the field is a flattened field, use the last key as the header
              headerName={isExpanded ? 'Ref' : 'outputs'}
              field={'output'}
              hasExpand={hasExpand && !isExpanded}
              onExpand={onExpand}
            />
          );
        },
        renderCell: cellParams => {
          return (
            <ErrorBoundary>
              <CellValue
                value={(cellParams.row as any).output}
                isExpanded={isExpanded}
              />
            </ErrorBoundary>
          );
        },
      });

      // if ref is expanded add the ref children to the colGroup
      if (isExpanded) {
        colGroup.children.push(...getGroupChildren('output'));
      }
      colGroupingModel.push(colGroup);
    }

    const feedbackKeys: {[key: string]: true} = {};
    newSpans.forEach(span => {
      for (const [k, v] of Object.entries(
        flattenObject(span.rawFeedback ?? {})
      )) {
        if (v != null && k !== '_keys') {
          feedbackKeys[k] = true;
        }
      }
    });

    const feedbackOrder = Object.keys(feedbackKeys);
    const feedbackGrouping = buildTree(feedbackOrder, 'feedback');
    colGroupingModel.push(feedbackGrouping);
    for (const key of feedbackOrder) {
      cols.push({
        flex: 1,
        minWidth: 150,
        field: 'feedback.' + key,
        headerName: key.split('.').slice(-1)[0],
        renderCell: cellParams => {
          return renderCell((cellParams.row as any)['feedback.' + key]);
        },
      });
    }

    cols.push({
      field: 'userId',
      headerName: 'User',
      headerAlign: 'center',
      width: 50,
      // Might be confusing to enable as-is, because the user sees name /
      // email but the underlying data is userId.
      filterable: false,
      align: 'center',
      sortable: false,
      resizable: false,
      disableColumnMenu: true,
      renderCell: cellParams => <UserLink username={cellParams.row.userId} />,
    });

    if (!ioColumnsOnly) {
      cols.push({
        field: 'timestampMs',
        headerName: 'Called',
        // Should have custom timestamp filter here.
        filterable: false,
        width: 100,
        minWidth: 100,
        maxWidth: 100,
        renderCell: (cellParams: any) => {
          return (
            <Timestamp
              value={cellParams.row.timestampMs / 1000}
              format="relative"
            />
          );
        },
      });
    }

    cols.push({
      field: 'latency',
      headerName: 'Latency',
      width: 100,
      minWidth: 100,
      maxWidth: 100,
      // Should probably have a custom filter here.
      filterable: false,
      renderCell: cellParams => {
        if (cellParams.row.status_code === 'UNSET') {
          // Call is still in progress, latency will be 0.
          // Displaying nothing seems preferable to being misleading.
          return null;
        }
        return monthRoundedTime(cellParams.row.latency);
      },
    });

    return {cols, colGroupingModel};
  }, [
    expandedColInfo,
    expandedRefCols,
    ioColumnsOnly,
    isSingleOp,
    isSingleOpVersion,
    onlyOneOutputResult,
    entity,
    project,
    preservePath,
    newSpans,
    tableStats,
    selectedCalls,
    setSelectedCalls,
  ]);

  // CPR (tim) - (GeneralRefactoring): Again, move to a hook
  const autosized = useRef(false);
  // const {peekingRouter} = useWeaveflowRouteContext();
  // const history = useHistory();
  useEffect(() => {
    if (!apiRefIsReady) {
      return;
    }
    if (autosized.current) {
      return;
    }
    if (callsLoading) {
      return;
    }
    autosized.current = true;
    apiRef.current.autosizeColumns({
      includeHeaders: true,
      expand: true,
    });
  }, [apiRef, callsLoading, apiRefIsReady]);

  // CPR (Tim) - (GeneralRefactoring): These will get extracted into their own controls (at least sorting will)
  const initialStateRaw: ComponentProps<typeof DataGridPro>['initialState'] =
    useMemo(() => {
      if (callsLoading) {
        return undefined;
      }
      return {
        pinnedColumns: {left: ['span_id']},
        sorting: {
          sortModel: [{field: 'timestampMs', sort: 'desc'}],
        },
      };
    }, [callsLoading]);

  // Various interactions (correctly) cause new data to be loaded, which causes
  // a trickle of state updates. However, if the ultimate state is the same,
  // we don't want to re-render the table.
  const initialState = useDeepMemo(initialStateRaw);

  // Tim (CPR): This whole section can be simplified I believe
  // This is a workaround.
  // initialState won't take effect if columns are not set.
  // see https://github.com/mui/mui-x/issues/6206
  useEffect(() => {
    if (apiRefIsReady && columns != null && initialState != null) {
      apiRef.current.restoreState(initialState);
    }
  }, [columns, initialState, apiRef, apiRefIsReady]);

  // CPR (Tim) - (GeneralRefactoring): Co-locate this closer to the effective filter stuff
  const clearFilters = useMemo(() => {
    if (Object.keys(filter ?? {}).length > 0) {
      return () => setFilter({});
    }
    return null;
  }, [filter, setFilter]);

  // CPR (Tim) - (GeneralRefactoring): Remove this, and add a slot for empty content that can be calculated
  // in the parent component
  const isEvaluateTable = useCurrentFilterIsEvaluationsFilter(
    effectiveFilter,
    entity,
    project
  );

  // CPR (Tim) - (GeneralRefactoring): Pull out different inline-properties and create them above
  return (
    <FilterLayoutTemplate
      filterListSx={{
        pb: 1,
        display: hideControls ? 'none' : 'flex',
      }}
      filterListItems={
        <>
          <ListItem sx={{minWidth: '190px'}}>
            <FormControl fullWidth>
              <Autocomplete
                PaperComponent={paperProps => <StyledPaper {...paperProps} />}
                size="small"
                // Temp disable multiple for simplicity - may want to re-enable
                // multiple
                limitTags={1}
                disabled={Object.keys(frozenFilter ?? {}).includes(
                  'opVersions'
                )}
                value={selectedOpVersionOption}
                onChange={(event, newValue) => {
                  if (newValue === ALL_TRACES_OR_CALLS_REF_KEY) {
                    setFilter({
                      ...filter,
                      opVersionRefs: [],
                    });
                  } else {
                    setFilter({
                      ...filter,
                      opVersionRefs: newValue ? [newValue] : [],
                    });
                  }
                }}
                renderInput={renderParams => (
                  <StyledTextField
                    {...renderParams}
                    label={OP_FILTER_GROUP_HEADER}
                    sx={{maxWidth: '350px'}}
                  />
                )}
                getOptionLabel={option => {
                  return opVersionOptions[option]?.title ?? 'loading...';
                }}
                disableClearable={
                  selectedOpVersionOption === ALL_TRACES_OR_CALLS_REF_KEY
                }
                groupBy={option => opVersionOptions[option]?.group}
                options={Object.keys(opVersionOptions)}
              />
            </FormControl>
          </ListItem>
          {selectedInputObjectVersion && (
            <Chip
              label={`Input: ${objectVersionNiceString(
                selectedInputObjectVersion
              )}`}
              onDelete={() => {
                setFilter({
                  ...filter,
                  inputObjectVersionRefs: undefined,
                });
              }}
            />
          )}
          {selectedOutputObjectVersion && (
            <Chip
              label={`Output: ${objectVersionNiceString(
                selectedOutputObjectVersion
              )}`}
              onDelete={() => {
                setFilter({
                  ...filter,
                  outputObjectVersionRefs: undefined,
                });
              }}
            />
          )}
          {selectedParentId && (
            <Chip
              label={`Parent: ${selectedParentId}`}
              onDelete={() => {
                setFilter({
                  ...filter,
                  parentId: undefined,
                });
              }}
            />
          )}
          <OverflowMenu
            selectedCalls={selectedCalls}
            refetch={calls.refetch}
            setSelectedCalls={setSelectedCalls}
          />
        </>
      }>
      {/* <React.Fragment key={callsKey}> */}
      <React.Fragment>
        {showVisibilityAlert && (
          <VisibilityAlert>
            <VisibilityAlertText>
              Columns having many empty values have been hidden.
            </VisibilityAlertText>
            <VisibilityAlertAction onClick={() => setForceShowAll(true)}>
              Show all
            </VisibilityAlertAction>
          </VisibilityAlert>
        )}
        <BoringColumnInfo
          tableStats={tableStats}
          columns={columns.cols as any}
        />
        <StyledDataGrid
          // Start Column Menu
          // ColumnMenu is needed to support pinning and column visibility
          disableColumnMenu={false}
          // ColumnFilter is definitely useful
          disableColumnFilter={false}
          disableMultipleColumnsFiltering={false}
          // ColumnPinning seems to be required in DataGridPro, else it crashes.
          // However, in this case it is also useful.
          disableColumnPinning={false}
          // ColumnReorder is definitely useful
          disableColumnReorder={false}
          // ColumnResize is definitely useful
          disableColumnResize={false}
          // ColumnSelector is definitely useful
          disableColumnSelector={false}
          disableMultipleColumnsSorting={true}
          // End Column Menu
          columnHeaderHeight={40}
          apiRef={apiRef}
          loading={callsLoading}
          rows={tableData}
          initialState={initialState}
          onColumnVisibilityModelChange={newModel =>
            setColumnVisibilityModel(newModel)
          }
          columnVisibilityModel={columnVisibilityModel}
          rowHeight={38}
          columns={columns.cols as any}
          experimentalFeatures={{columnGrouping: true}}
          disableRowSelectionOnClick
          rowSelectionModel={rowSelectionModel}
          columnGroupingModel={columns.colGroupingModel}
          hideFooterSelectedRowCount
          sx={{
            borderRadius: 0,
          }}
          slots={{
            noRowsOverlay: () => {
              const isEmpty = callsResult.length === 0;
              if (!callsLoading && isEmpty) {
                // CPR (Tim) - (GeneralRefactoring): Move "isEvaluateTable" out and instead make this empty state a prop
                if (isEvaluateTable) {
                  return <Empty {...EMPTY_PROPS_EVALUATIONS} />;
                } else if (effectiveFilter.traceRootsOnly) {
                  return <Empty {...EMPTY_PROPS_TRACES} />;
                }
              }
              return (
                <Box
                  sx={{
                    width: '100%',
                    height: '100%',
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                  }}>
                  <Typography color="textSecondary">
                    No calls found.{' '}
                    {clearFilters != null ? (
                      <>
                        Try{' '}
                        <A
                          onClick={() => {
                            clearFilters();
                          }}>
                          clearing the filters
                        </A>{' '}
                        or l
                      </>
                    ) : (
                      'L'
                    )}
                    earn more about how to log calls by visiting{' '}
                    <TargetBlank href="https://wandb.me/weave">
                      the docs
                    </TargetBlank>
                    .
                  </Typography>
                </Box>
              );
            },
          }}
        />
      </React.Fragment>
    </FilterLayoutTemplate>
  );
};

const useParentIdOptions = (
  entity: string,
  project: string,
  effectiveFilter: WFHighLevelCallFilter
) => {
  const {useCall} = useWFHooks();
  const parentCall = useCall(
    effectiveFilter.parentId
      ? {
          entity,
          project,
          callId: effectiveFilter.parentId,
        }
      : null
  );
  return useMemo(() => {
    if (parentCall.loading || parentCall.result == null) {
      return {};
    }
    return {
      [parentCall.result.callId]: `${parentCall.result.spanName} (${truncateID(
        parentCall.result.callId
      )})`,
    };
  }, [parentCall.loading, parentCall.result]);
};

/// Start of RunsTable.tsx move over

function addToTree(
  node: GridColumnGroup,
  fields: string[],
  fullPath: string,
  depth: number
): void {
  if (!fields.length) {
    return;
  }

  if (fields.length === 1) {
    node.children.push({
      field: fullPath,
    });
    return;
  }

  for (const child of node.children) {
    if ('groupId' in child && child.headerName === fields[0]) {
      addToTree(child as GridColumnGroup, fields.slice(1), fullPath, depth + 1);
      return;
    }
  }

  const newNode: GridColumnGroup = {
    headerName: fields[0],
    groupId: fullPath
      .split('.')
      .slice(0, depth + 2)
      .join('.'),
    children: [],
  };
  node.children.push(newNode);
  addToTree(newNode, fields.slice(1), fullPath, depth + 1);
}

function buildTree(strings: string[], rootGroupName: string): GridColumnGroup {
  const root: GridColumnGroup = {groupId: rootGroupName, children: []};

  for (const str of strings) {
    const fields = str.split('.');
    addToTree(root, fields, rootGroupName + '.' + str, 0);
  }

  return root;
}

type OpVersionIndexTextProps = {
  opVersionRef: string;
};

const OpVersionIndexText = ({opVersionRef}: OpVersionIndexTextProps) => {
  const {useOpVersion} = useWFHooks();
  const ref = parseRef(opVersionRef);
  let opVersionKey: OpVersionKey | null = null;
  if ('weaveKind' in ref && ref.weaveKind === 'op') {
    opVersionKey = {
      entity: ref.entityName,
      project: ref.projectName,
      opId: ref.artifactName,
      versionHash: ref.artifactVersion,
    };
  }
  const opVersion = useOpVersion(opVersionKey);
  if (opVersion.loading) {
    return <LoadingDots />;
  }
  return opVersion.result ? (
    <span>v{opVersion.result.versionIndex}</span>
  ) : null;
};

type ExtraColumns = Record<string, Array<{label: string; path: string}>>;

const isExpandableType = (type: Type): boolean => {
  return isObjectTypeLike(type) || isTypedDictLike(type);
};

const getExtraColumns = (
  result: Type[]
): Array<{label: string; path: string}> => {
  const cols: {[label: string]: string} = {};
  for (const refInfo of result) {
    if (isObjectTypeLike(refInfo)) {
      const keys = Object.keys(refInfo).filter(
        k => k !== 'type' && !k.startsWith('_')
      );
      keys.forEach(k => {
        const innerType = (refInfo as any)[k] as Type;
        if (isExpandableType(innerType)) {
          const subKeys = getExtraColumns([innerType]);
          subKeys.forEach(sk => {
            cols[k + '.' + sk.label] =
              k + `/${OBJECT_ATTR_EDGE_NAME}/` + sk.path;
          });
        } else {
          cols[k] = k;
        }
      });
    } else if (isTypedDictLike(refInfo)) {
      const propTypes = typedDictPropertyTypes(refInfo);
      const keys = Object.keys(propTypes);
      keys.forEach(k => {
        const innerType = propTypes[k] as Type;
        if (isExpandableType(innerType)) {
          const subKeys = getExtraColumns([innerType]);
          subKeys.forEach(sk => {
            cols[k + '.' + sk.label] = k + `/${DICT_KEY_EDGE_NAME}/` + sk.path;
          });
        } else {
          cols[k] = k;
        }
      });
    }
  }
  return Object.entries(cols).map(([label, path]) => ({label, path}));
};

// Get the tail of the peekPath (ignore query params)
const getPeekId = (peekPath: string | null): string | null => {
  if (!peekPath) {
    return null;
  }
  const baseUrl = `${window.location.protocol}//${window.location.host}`;
  const url = new URL(peekPath, baseUrl);
  const {pathname} = url;
  return pathname.split('/').pop() ?? null;
};

const ExportRunsTableButton = ({
  tableRef,
}: {
  tableRef: React.MutableRefObject<GridApiPro>;
}) => (
  <Box
    sx={{
      height: '100%',
      display: 'flex',
      alignItems: 'center',
    }}>
    <Button
      className="mx-16"
      size="medium"
      variant="secondary"
      onClick={() => tableRef.current?.exportDataAsCsv()}
      icon="export-share-upload">
      Export to CSV
    </Button>
  </Box>
);
