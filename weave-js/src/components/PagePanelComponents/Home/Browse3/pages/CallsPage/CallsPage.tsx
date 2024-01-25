import {
  Box,
  CircularProgress,
  IconButton,
  Snackbar,
  Typography,
} from '@material-ui/core';
import {DashboardCustomize, PivotTableChart} from '@mui/icons-material';
import {
  Autocomplete,
  Checkbox,
  FormControl,
  ListItem,
  ListItemButton,
  ListItemText,
  TextField,
} from '@mui/material';
import {
  DataGrid,
  GRID_CHECKBOX_SELECTION_COL_DEF,
  GridColDef,
} from '@mui/x-data-grid';
import _ from 'lodash';
import React, {useEffect, useMemo, useState} from 'react';

import {parseRef} from '../../../../../../react';
import {flattenObject} from '../../../Browse2/browse2Util';
import {CallFilter, SpanWithFeedback} from '../../../Browse2/callTree';
import {fnRunsNode, useRunsWithFeedback} from '../../../Browse2/callTreeHooks';
import {
  buildTree,
  DataGridColumnGroupingModel,
  RunsTable,
} from '../../../Browse2/RunsTable';
import {SmallRef} from '../../../Browse2/SmallRef';
import {useWeaveflowRouteContext} from '../../context';
import {StyledDataGrid} from '../../StyledDataGrid';
import {useMakeNewBoard} from '../common/hooks';
import {opNiceName} from '../common/Links';
import {FilterLayoutTemplate} from '../common/SimpleFilterableDataTable';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {renderCell, truncateID} from '../util';
import {
  useWeaveflowORMContext,
  WeaveflowORMContextType,
} from '../wfInterface/context';
import {
  HackyOpCategory,
  WFCall,
  WFObjectVersion,
  WFOpVersion,
} from '../wfInterface/types';

export type WFHighLevelCallFilter = {
  traceRootsOnly?: boolean;
  opCategory?: HackyOpCategory | null;
  opVersions?: string[];
  inputObjectVersions?: string[];
  parentId?: string | null;
  traceId?: string | null;
};

export const CallsPage: React.FC<{
  entity: string;
  project: string;
  initialFilter?: WFHighLevelCallFilter;
  // Setting this will make the component a controlled component. The parent
  // is responsible for updating the filter.
  onFilterUpdate?: (filter: WFHighLevelCallFilter) => void;
}> = props => {
  return (
    <SimplePageLayout
      title="Calls"
      tabs={[
        {
          label: 'All',
          content: <CallsTable {...props} />,
        },
      ]}
    />
  );
};

export const CallsTable: React.FC<{
  entity: string;
  project: string;
  frozenFilter?: WFHighLevelCallFilter;
  initialFilter?: WFHighLevelCallFilter;
  // Setting this will make the component a controlled component. The parent
  // is responsible for updating the filter.
  onFilterUpdate?: (filter: WFHighLevelCallFilter) => void;
}> = props => {
  const {baseRouter} = useWeaveflowRouteContext();
  const orm = useWeaveflowORMContext(props.entity, props.project);

  const [filterState, setFilterState] = useState<WFHighLevelCallFilter>(
    props.initialFilter ?? {}
  );
  useEffect(() => {
    if (props.initialFilter) {
      setFilterState(props.initialFilter);
    }
  }, [props.initialFilter]);

  // If the caller is controlling the filter, use the caller's filter state
  const filter = useMemo(
    () => (props.onFilterUpdate ? props.initialFilter ?? {} : filterState),
    [filterState, props.initialFilter, props.onFilterUpdate]
  );
  const setFilter = useMemo(
    () => (props.onFilterUpdate ? props.onFilterUpdate : setFilterState),
    [props.onFilterUpdate]
  );

  const effectiveFilter = useMemo(() => {
    return {...filter, ...props.frozenFilter};
  }, [filter, props.frozenFilter]);

  const lowLevelFilter: CallFilter = useMemo(() => {
    return convertHighLevelFilterToLowLevelFilter(orm, effectiveFilter);
  }, [effectiveFilter, orm]);
  const streamId = {
    entityName: props.entity,
    projectName: props.project,
    streamName: 'stream',
  };

  const runsWithFeedbackQuery = useRunsWithFeedback(streamId, lowLevelFilter);

  // # TODO: All of these need to be handled much more logically since
  // we need to calculate the options based on everything except a specific filter.
  const opVersionOptions = useOpVersionOptions(
    orm,
    props.entity,
    props.project,
    effectiveFilter
  );
  const consumesObjectVersionOptions = useConsumesObjectVersionOptions(
    orm,
    props.entity,
    props.project,
    effectiveFilter
  );
  const parentIdOptions = useParentIdOptions(
    orm,
    props.entity,
    props.project,
    effectiveFilter
  );
  const traceIdOptions = useTraceIdOptions(
    orm,
    props.entity,
    props.project,
    effectiveFilter
  );
  const opCategoryOptions = useOpCategoryOptions(
    orm,
    props.entity,
    props.project,
    effectiveFilter
  );
  const traceRootOptions = useTraceRootOptions(
    orm,
    props.entity,
    props.project,
    effectiveFilter
  );
  const {onMakeBoard, isGenerating} = useMakeBoardForCalls(
    props.entity,
    props.project,
    lowLevelFilter
  );

  // TODO(tim/pivot_tables): Add these to the incoming filter state and URL.
  const [userEnabledPivot, setUserEnabledPivot] = useState(false);
  const [pivotRowDim, setPivotRowDim] = useState<string | null>();
  const [pivotColDim, setPivotColDim] = useState<string | null>();

  const [pivotRowOptions, setPivotRowOptions] = useState<string[]>([]);
  const [pivotColOptions, setPivotColOptions] = useState<string[]>([]);
  const canPivot = useMemo(() => {
    return (
      effectiveFilter.opVersions?.length === 1 && pivotRowOptions.length > 1
    );
  }, [effectiveFilter.opVersions?.length, pivotRowOptions.length]);
  const isPivoting = userEnabledPivot && canPivot;

  useEffect(() => {
    if (runsWithFeedbackQuery.loading) {
      return;
    }
    const runs = runsWithFeedbackQuery.result;
    if (runs.length === 0) {
      return;
    }
    const firstRun = runs[0];
    const options: string[] = [];
    Object.entries(firstRun.inputs).forEach(([key, value]) => {
      if (
        typeof value === 'string' &&
        value.startsWith('wandb-artifact:///') &&
        !key.startsWith('_')
      ) {
        options.push('inputs.' + key);
      }
    });
    setPivotRowOptions(options);
    setPivotColOptions(options);
    if (options.length > 1) {
      if (options[0] === 'inputs.self') {
        setPivotRowDim(options[1]);
        setPivotColDim(options[0]);
      } else {
        setPivotRowDim(options[0]);
        setPivotColDim(options[1]);
      }
    }
  }, [runsWithFeedbackQuery.loading, runsWithFeedbackQuery.result]);

  return (
    <FilterLayoutTemplate
      showFilterIndicator={Object.keys(effectiveFilter ?? {}).length > 0}
      showPopoutButton={Object.keys(props.frozenFilter ?? {}).length > 0}
      filterPopoutTargetUrl={baseRouter.callsUIUrl(
        props.entity,
        props.project,
        effectiveFilter
      )}
      filterListItems={
        <>
          <IconButton
            style={{display: 'none', width: '37px', height: '37px'}}
            size="small"
            onClick={() => {
              onMakeBoard();
            }}>
            {isGenerating ? (
              <CircularProgress size={25} />
            ) : (
              <DashboardCustomize />
            )}
          </IconButton>
          {canPivot && (
            <IconButton
              style={{width: '37px', height: '37px'}}
              size="small"
              color={userEnabledPivot ? 'primary' : 'default'}
              onClick={() => {
                setUserEnabledPivot(!userEnabledPivot);
              }}>
              <PivotTableChart />
            </IconButton>
          )}
          <ListItem>
            <FormControl fullWidth>
              <Autocomplete
                size={'small'}
                disabled={
                  isPivoting ||
                  Object.keys(props.frozenFilter ?? {}).includes('opCategory')
                }
                renderInput={params => (
                  <TextField {...params} label="Category" />
                )}
                value={effectiveFilter.opCategory ?? null}
                onChange={(event, newValue) => {
                  setFilter({
                    ...filter,
                    opCategory: newValue,
                  });
                }}
                options={opCategoryOptions}
              />
            </FormControl>
          </ListItem>
          <ListItem>
            <FormControl fullWidth>
              <Autocomplete
                size={'small'}
                // Temp disable multiple for simplicity - may want to re-enable
                // multiple
                limitTags={1}
                disabled={
                  isPivoting ||
                  Object.keys(props.frozenFilter ?? {}).includes('opVersions')
                }
                value={effectiveFilter.opVersions?.[0] ?? null}
                onChange={(event, newValue) => {
                  setFilter({
                    ...filter,
                    opVersions: newValue ? [newValue] : [],
                  });
                }}
                renderInput={params => (
                  <TextField {...params} label="Op" />
                  // <TextField {...params} label="Op Version" />
                )}
                getOptionLabel={option => {
                  return opVersionOptions[option] ?? option;
                }}
                options={Object.keys(opVersionOptions)}
              />
            </FormControl>
          </ListItem>
          <ListItem>
            <FormControl fullWidth>
              <Autocomplete
                size={'small'}
                limitTags={1}
                // Temp disable multiple for simplicity - may want to re-enable
                // multiple
                disabled={
                  isPivoting ||
                  Object.keys(props.frozenFilter ?? {}).includes(
                    'inputObjectVersions'
                  )
                }
                renderInput={params => (
                  <TextField {...params} label="Inputs" />
                  // <TextField {...params} label="Consumes Objects" />
                )}
                value={effectiveFilter.inputObjectVersions?.[0] ?? null}
                onChange={(event, newValue) => {
                  setFilter({
                    ...filter,
                    inputObjectVersions: newValue ? [newValue] : [],
                  });
                }}
                getOptionLabel={option => {
                  return consumesObjectVersionOptions[option] ?? option;
                }}
                options={Object.keys(consumesObjectVersionOptions)}
              />
            </FormControl>
          </ListItem>
          <ListItem>
            <FormControl fullWidth>
              <Autocomplete
                size={'small'}
                disabled={
                  isPivoting ||
                  Object.keys(props.frozenFilter ?? {}).includes('traceId')
                }
                renderInput={params => <TextField {...params} label="Trace" />}
                value={effectiveFilter.traceId ?? null}
                onChange={(event, newValue) => {
                  setFilter({
                    ...filter,
                    traceId: newValue,
                  });
                }}
                getOptionLabel={option => {
                  return traceIdOptions[option] ?? option;
                }}
                options={Object.keys(traceIdOptions)}
              />
            </FormControl>
          </ListItem>
          <ListItem>
            <FormControl fullWidth>
              <Autocomplete
                size={'small'}
                disabled={
                  isPivoting ||
                  Object.keys(props.frozenFilter ?? {}).includes('parentId')
                }
                renderInput={params => <TextField {...params} label="Parent" />}
                value={effectiveFilter.parentId ?? null}
                onChange={(event, newValue) => {
                  setFilter({
                    ...filter,
                    parentId: newValue,
                  });
                }}
                getOptionLabel={option => {
                  return parentIdOptions[option] ?? option;
                }}
                options={Object.keys(parentIdOptions)}
              />
            </FormControl>
          </ListItem>
          <ListItem
            secondaryAction={
              <Checkbox
                edge="end"
                checked={
                  !!effectiveFilter.traceRootsOnly ||
                  (traceRootOptions.length === 1 && traceRootOptions[0])
                }
                onChange={() => {
                  setFilter({
                    ...filter,
                    traceRootsOnly: !effectiveFilter.traceRootsOnly,
                  });
                }}
              />
            }
            disabled={
              isPivoting ||
              traceRootOptions.length <= 1 ||
              Object.keys(props.frozenFilter ?? {}).includes('traceRootsOnly')
            }
            disablePadding>
            <ListItemButton
              onClick={() => {
                setFilter({
                  ...filter,
                  traceRootsOnly: !effectiveFilter.traceRootsOnly,
                });
              }}>
              <ListItemText primary="Roots Only" />
            </ListItemButton>
          </ListItem>
        </>
      }
      pivotListItems={
        isPivoting && (
          <>
            <Typography
              style={{width: '38px', textAlign: 'center', flex: '0 0 auto'}}>
              Pivot
            </Typography>
            <ListItem>
              <FormControl fullWidth>
                <Autocomplete
                  size={'small'}
                  renderInput={params => <TextField {...params} label="Rows" />}
                  value={pivotRowDim ?? null}
                  onChange={(event, newValue) => {
                    setPivotRowDim(newValue);
                  }}
                  options={pivotRowOptions}
                />
              </FormControl>
            </ListItem>
            <ListItem>
              <FormControl fullWidth>
                <Autocomplete
                  size={'small'}
                  renderInput={params => (
                    <TextField {...params} label="Columns" />
                  )}
                  value={pivotColDim ?? null}
                  onChange={(event, newValue) => {
                    setPivotColDim(newValue);
                  }}
                  options={pivotColOptions}
                />
              </FormControl>
            </ListItem>
          </>
        )
      }>
      {isPivoting ? (
        <PivotRunsTable
          loading={runsWithFeedbackQuery.loading}
          runs={runsWithFeedbackQuery.result}
          rowsDim={pivotRowDim}
          colsDim={pivotColDim}
        />
      ) : (
        <RunsTable
          loading={runsWithFeedbackQuery.loading}
          spans={runsWithFeedbackQuery.result}
        />
      )}
    </FilterLayoutTemplate>
  );
};
const getValueAtNestedKey = (value: any, dimKey: string) => {
  dimKey.split('.').forEach(dim => {
    if (value != null) {
      value = value[dim];
    }
  });
  return value;
};

const PivotRunsTable: React.FC<{
  loading: boolean;
  runs: SpanWithFeedback[];
  rowsDim?: string | null;
  colsDim?: string | null;
}> = props => {
  const {pivotData, pivotColumns} = useMemo(() => {
    if (props.rowsDim == null || props.colsDim == null) {
      return {pivotData: [], pivotColumns: new Set<string>()};
    }

    // TODO(tim/pivot_tables): Make this configurable and sort by timestamp!
    const aggregation = (values: any[]) => {
      return values[0];
    };

    // Step 1: Create a map of values
    const values: {[rowId: string]: {[colId: string]: any[]}} = {};
    const pivotColumns: Set<string> = new Set();
    props.runs.forEach(r => {
      const rowValue = getValueAtNestedKey(r, props.rowsDim!);
      const colValue = getValueAtNestedKey(r, props.colsDim!);
      if (rowValue == null || colValue == null) {
        return;
      }
      pivotColumns.add(colValue);
      if (!values[rowValue]) {
        values[rowValue] = {};
      }
      if (!values[rowValue][colValue]) {
        values[rowValue][colValue] = [];
      }
      values[rowValue][colValue].push(r);
    });

    // Step 2: Create a list of rows
    const rows: Array<{[col: string]: any}> = [];
    Object.keys(values).forEach(rowKey => {
      const row: {[col: string]: any} = {
        id: rowKey,
      };
      row[props.rowsDim!] = rowKey;
      Object.keys(values[rowKey]).forEach(colKey => {
        row[colKey] = aggregation(values[rowKey][colKey]);
      });
      rows.push(row);
    });

    return {pivotData: rows, pivotColumns};
  }, [props.colsDim, props.rowsDim, props.runs]);

  const columns = useMemo(() => {
    const cols: GridColDef[] = [
      {
        flex: 1,
        minWidth: 175,
        field: props.rowsDim!,
        headerName: props.rowsDim!,
        renderCell: cellParams => {
          const value = cellParams.row[props.rowsDim!];
          if (
            typeof value === 'string' &&
            value.startsWith('wandb-artifact:///')
          ) {
            return <SmallRef objRef={parseRef(value)} />;
          }
          return value;
        },
      },
    ];

    const colGroupingModel: DataGridColumnGroupingModel = [];

    if (pivotData.length === 0) {
      return {cols: [], colGroupingModel: []};
    }
    pivotColumns.forEach(col => {
      // All output keys as we don't have the order key yet.
      let outputKeys: {[key: string]: true} = {};
      pivotData.forEach(pivotRow => {
        if (pivotRow[col]) {
          for (const [k, v] of Object.entries(
            flattenObject(pivotRow[col].output!)
          )) {
            if (v != null && (!k.startsWith('_') || k === '_result')) {
              outputKeys[k] = true;
            }
          }
        }
      });

      const outputOrder = Object.keys(outputKeys);
      const outputGrouping = buildTree(outputOrder, col);
      outputGrouping.renderHeaderGroup = params => {
        const value = col;
        if (
          typeof value === 'string' &&
          value.startsWith('wandb-artifact:///')
        ) {
          return (
            <Box>
              <SmallRef objRef={parseRef(value)} />
            </Box>
          );
        }
        return value;
      };
      colGroupingModel.push(outputGrouping);
      for (const key of outputOrder) {
        cols.push({
          flex: 1,
          minWidth: 150,
          field: col + '.' + key,
          headerName: key.split('.').slice(-1)[0],
          // renderHeader: params => {
          //   console.log(params);
          //   if (params.field === col) {
          //     console.log(params);
          //   }
          //   // console.log('NO');
          // },
          renderCell: cellParams => {
            return renderCell(
              getValueAtNestedKey(cellParams.row[col]?.['output'], key)
            );
          },
        });
      }
    });

    return {cols, colGroupingModel};
  }, [pivotColumns, pivotData, props.rowsDim]);

  const [rowSelectionModel, setRowSelectionModel] = useState<string[]>([]);
  const [snackOpen, setSnackOpen] = useState(false);
  if (props.loading) {
    return <CircularProgress />;
  }
  if (props.rowsDim == null || props.colsDim == null) {
    return <>Call to action: Select dimensions</>;
  }

  // console.log({
  //   props,
  //   columns,
  //   pivotData,
  // });

  return (
    <>
      <Snackbar
        open={snackOpen}
        autoHideDuration={2000}
        onClose={() => {
          setSnackOpen(false);
        }}
        message="Only 2 rows can be selected at a time."
      />
      <StyledDataGrid
        columnHeaderHeight={40}
        // apiRef={apiRef}
        // loading={loading}
        rows={pivotData}
        // density="compact"
        // initialState={initialState}
        rowHeight={38}
        columns={columns.cols}
        experimentalFeatures={{columnGrouping: true}}
        disableRowSelectionOnClick
        // rowSelectionModel={rowSelectionModel}
        initialState={{
          pinnedColumns: {
            left: [GRID_CHECKBOX_SELECTION_COL_DEF.field, props.rowsDim!],
          },
        }}
        checkboxSelection={false}
        columnGroupingModel={columns.colGroupingModel}
        // onRowClick={({id}) => {
        //   history.push(
        //     peekingRouter.callUIUrl(
        //       params.entity,
        //       params.project,
        //       '',
        //       id as string
        //     )
        //   );
        // }}
        // isRowSelectable={(params: GridRowParams) =>
        //   rowSelectionModel.includes(params.id as string) ||
        //   rowSelectionModel.length < 2
        // }
        rowSelectionModel={rowSelectionModel}
        onRowSelectionModelChange={newSelection => {
          if (newSelection.length > 2) {
            // Limit to 2 selections for the time being.
            setSnackOpen(true);
            return;
          }
          setRowSelectionModel(newSelection as string[]);
        }}
      />
    </>
  );
};

const useMakeBoardForCalls = (
  entityName: string,
  projectName: string,
  lowLevelFilter: CallFilter
) => {
  // TODO: Make a generator on the python side that is more robust.
  // 1. Make feedback a join in weave
  // 2. Control the column selection like we do in the current table
  // 3. Map column processing to weave (example timestamps)
  // 4. Handle references more cleanly
  // 5. Probably control ordering.

  const runsNode = fnRunsNode(
    {
      entityName,
      projectName,
      streamName: 'stream',
    },
    lowLevelFilter
  );
  return useMakeNewBoard(runsNode);
};

const convertHighLevelFilterToLowLevelFilter = (
  orm: WeaveflowORMContextType,
  effectiveFilter: WFHighLevelCallFilter
): CallFilter => {
  const opUrisFromVersions =
    (effectiveFilter.opVersions
      ?.map(uri => {
        const [opName, version] = uri.split(':');
        const opVersion = orm.projectConnection.opVersion(opName, version);
        return opVersion?.refUri();
      })
      .filter(item => item != null) as string[]) ?? [];
  let opUrisFromCategory = orm.projectConnection
    .opVersions()
    .filter(ov => ov.opCategory() === effectiveFilter.opCategory)
    .map(ov => ov.refUri());
  if (opUrisFromCategory.length === 0 && effectiveFilter.opCategory) {
    opUrisFromCategory = ['DOES_NOT_EXIST:VALUE'];
  }

  let finalURISet = new Set<string>([]);
  const opUrisFromVersionsSet = new Set<string>(opUrisFromVersions);
  const opUrisFromCategorySet = new Set<string>(opUrisFromCategory);
  const includeVersions =
    effectiveFilter.opVersions != null &&
    effectiveFilter.opVersions.length >= 0;
  const includeCategories = effectiveFilter.opCategory != null;

  if (includeVersions && includeCategories) {
    // intersect the two sets
    finalURISet = new Set<string>(
      [...opUrisFromVersionsSet].filter(x => opUrisFromCategorySet.has(x))
    );
  } else if (includeVersions) {
    finalURISet = opUrisFromVersionsSet;
  } else if (includeCategories) {
    finalURISet = opUrisFromCategorySet;
  } else {
    finalURISet = new Set<string>([]);
  }

  return {
    traceRootsOnly: effectiveFilter.traceRootsOnly,
    opUris: Array.from(finalURISet),
    inputUris: effectiveFilter.inputObjectVersions
      ?.map(uri => {
        const [objectName, version] = uri.split(':');
        const objectVersion = orm.projectConnection.objectVersion(
          objectName,
          version
        );
        return objectVersion?.refUri();
      })
      .filter(item => item != null) as string[],
    traceId: effectiveFilter.traceId ?? undefined,
    parentId: effectiveFilter.parentId ?? undefined,
  };
};

const useOpVersionOptions = (
  orm: WeaveflowORMContextType,
  entity: string,
  project: string,
  highLevelFilter: WFHighLevelCallFilter
) => {
  const runs = useRunsWithFeedback(
    {
      entityName: entity,
      projectName: project,
      streamName: 'stream',
    },
    useMemo(() => {
      return convertHighLevelFilterToLowLevelFilter(
        orm,
        _.omit(highLevelFilter, ['opVersions'])
      );
    }, [highLevelFilter, orm])
  );
  return useMemo(() => {
    let versions: WFOpVersion[] = [];
    if (runs.loading) {
      versions = orm.projectConnection.opVersions();
    } else {
      versions = runs.result
        .map(r => orm.projectConnection.call(r.span_id)?.opVersion())
        .filter(v => v != null) as WFOpVersion[];
    }

    // Sort by name ascending, then version descending.
    versions.sort((a, b) => {
      const nameA = opNiceName(a.op().name());
      const nameB = opNiceName(b.op().name());
      if (nameA !== nameB) {
        return nameA.localeCompare(nameB);
      }
      return b.versionIndex() - a.versionIndex();
    });

    return _.fromPairs(
      versions.map(v => {
        return [
          v.op().name() + ':' + v.version(),
          opNiceName(v.op().name()) + ':v' + v.versionIndex(),
        ];
      })
    );
  }, [orm.projectConnection, runs.loading, runs.result]);
};

const useConsumesObjectVersionOptions = (
  orm: WeaveflowORMContextType,
  entity: string,
  project: string,
  highLevelFilter: WFHighLevelCallFilter
) => {
  const runs = useRunsWithFeedback(
    {
      entityName: entity,
      projectName: project,
      streamName: 'stream',
    },
    useMemo(() => {
      return convertHighLevelFilterToLowLevelFilter(
        orm,
        _.omit(highLevelFilter, ['inputObjectVersions'])
      );
    }, [highLevelFilter, orm])
  );
  return useMemo(() => {
    let versions: WFObjectVersion[] = [];
    if (runs.loading) {
      versions = orm.projectConnection.objectVersions();
    } else {
      versions = runs.result.flatMap(
        r => orm.projectConnection.call(r.span_id)?.inputs() ?? []
      );
    }

    // Sort by name ascending, then version descending.
    versions.sort((a, b) => {
      const nameA = a.object().name();
      const nameB = b.object().name();
      if (nameA !== nameB) {
        return nameA.localeCompare(nameB);
      }
      return b.versionIndex() - a.versionIndex();
    });

    return _.fromPairs(
      versions.map(v => {
        return [
          v.object().name() + ':' + v.version(),
          v.object().name() + ':v' + v.versionIndex(),
        ];
      })
    );
  }, [orm.projectConnection, runs.loading, runs.result]);
};

const useTraceIdOptions = (
  orm: WeaveflowORMContextType,
  entity: string,
  project: string,
  highLevelFilter: WFHighLevelCallFilter
) => {
  const runs = useRunsWithFeedback(
    {
      entityName: entity,
      projectName: project,
      streamName: 'stream',
    },
    useMemo(() => {
      return convertHighLevelFilterToLowLevelFilter(
        orm,
        _.omit(highLevelFilter, ['traceId'])
      );
    }, [highLevelFilter, orm])
  );
  return useMemo(() => {
    let roots: WFCall[] = [];
    if (runs.loading) {
      roots = orm.projectConnection.calls().filter(v => v.parentCall() == null);
    } else {
      roots = runs.result
        .map(r => orm.projectConnection.call(r.span_id)?.traceID())
        .filter(traceId => traceId != null)
        .flatMap(traceId =>
          orm.projectConnection.traceRoots(traceId!)
        ) as WFCall[];
    }

    return _.fromPairs(
      roots.map(c => {
        const version = c.opVersion();
        if (!version) {
          return [c.traceID(), c.spanName()];
        }
        return [
          c.traceID(),
          version.op().name() + ' (' + truncateID(c.callID()) + ')',
        ];
      })
    );
  }, [orm.projectConnection, runs.loading, runs.result]);
};

const useParentIdOptions = (
  orm: WeaveflowORMContextType,
  entity: string,
  project: string,
  highLevelFilter: WFHighLevelCallFilter
) => {
  const runs = useRunsWithFeedback(
    {
      entityName: entity,
      projectName: project,
      streamName: 'stream',
    },
    useMemo(() => {
      return convertHighLevelFilterToLowLevelFilter(
        orm,
        _.omit(highLevelFilter, ['parentId'])
      );
    }, [highLevelFilter, orm])
  );
  return useMemo(() => {
    let parents: WFCall[] = [];
    if (runs.loading) {
      parents = orm.projectConnection
        .calls()
        .map(c => c.parentCall())
        .filter(v => v != null) as WFCall[];
    } else {
      parents = runs.result
        .map(r => orm.projectConnection.call(r.span_id)?.parentCall())
        .filter(v => v != null) as WFCall[];
    }
    return _.fromPairs(
      parents.map(c => {
        const version = c.opVersion();
        if (!version) {
          return [c.traceID(), c.spanName()];
        }
        return [
          c.callID(),
          version.op().name() + ' (' + truncateID(c.callID()) + ')',
        ];
      })
    );
  }, [orm.projectConnection, runs.loading, runs.result]);
};

const useOpCategoryOptions = (
  orm: WeaveflowORMContextType,
  entity: string,
  project: string,
  highLevelFilter: WFHighLevelCallFilter
) => {
  const runs = useRunsWithFeedback(
    {
      entityName: entity,
      projectName: project,
      streamName: 'stream',
    },
    useMemo(() => {
      return convertHighLevelFilterToLowLevelFilter(
        orm,
        _.omit(highLevelFilter, ['opCategory'])
      );
    }, [highLevelFilter, orm])
  );
  return useMemo(() => {
    if (runs.loading) {
      return orm.projectConnection.opCategories();
    }
    return _.uniq(
      runs.result.map(r =>
        orm.projectConnection.call(r.span_id)?.opVersion()?.opCategory()
      )
    )
      .filter(v => v != null)
      .sort() as HackyOpCategory[];
  }, [orm.projectConnection, runs.loading, runs.result]);
};

const useTraceRootOptions = (
  orm: WeaveflowORMContextType,
  entity: string,
  project: string,
  highLevelFilter: WFHighLevelCallFilter
) => {
  const runs = useRunsWithFeedback(
    {
      entityName: entity,
      projectName: project,
      streamName: 'stream',
    },
    useMemo(() => {
      return convertHighLevelFilterToLowLevelFilter(
        orm,
        _.omit(highLevelFilter, ['traceRootsOnly'])
      );
    }, [highLevelFilter, orm])
  );
  return useMemo(() => {
    if (runs.loading) {
      return [true, false];
    }
    return _.uniq(runs.result.map(r => r.parent_id == null));
  }, [runs.loading, runs.result]);
};
