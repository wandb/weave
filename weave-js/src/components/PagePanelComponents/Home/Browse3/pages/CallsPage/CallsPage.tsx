/**
 * Step 1: Nicer treatment of displays
 * Step 2: Allow lazy loading of options? (how do we re-narrow this down?)
 * Step 3: Perf of the compare view is really bad
 * TODO: The Pivot Table and Calls Compare are pretty jank and the typing is off: really should refactor since it is likely needed to push the grouping down to the server.
 */

// import {
//   CircularProgress,
//   IconButton,
//   InputLabel,
//   MenuItem,
//   OutlinedInput,
//   Select,
// } from '@material-ui/core';
import {DashboardCustomize, PivotTableChart} from '@mui/icons-material';
import {
  Autocomplete,
  Checkbox,
  CircularProgress,
  FormControl,
  IconButton,
  ListItem,
  ListItemButton,
  ListItemText,
  TextField,
} from '@mui/material';
import _ from 'lodash';
import React, {FC, useCallback, useMemo} from 'react';

import {fnRunsNode, useRunsWithFeedback} from '../../../Browse2/callTreeHooks';
import {RunsTable} from '../../../Browse2/RunsTable';
import {useWeaveflowRouteContext} from '../../context';
import {useMakeNewBoard} from '../common/hooks';
import {opNiceName} from '../common/Links';
import {FilterLayoutTemplate} from '../common/SimpleFilterableDataTable';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {truncateID, useInitializingFilter} from '../util';
import {WeaveflowORMContextType} from '../wfInterface/context';
import {HackyOpCategory, WFCall, WFObjectVersion} from '../wfInterface/types';
import {
  CallFilter,
  OP_CATEGORIES,
  opVersionKeyToRefUri,
  opVersionRefOpName,
  refUriToOpVersionKey,
  useCalls,
  useOpVersions,
} from '../wfReactInterface/interface';
import {PivotRunsView, WFHighLevelPivotSpec} from './PivotRunsTable';

export type WFHighLevelCallFilter = {
  traceRootsOnly?: boolean;
  opCategory?: HackyOpCategory | null;
  opVersionRefs?: string[];
  inputObjectVersionRefs?: string[];
  // outputObjectVersionRefs?: string[];
  parentId?: string | null;
  // traceId?: string | null;
  isPivot?: boolean;
  pivotSpec?: Partial<WFHighLevelPivotSpec>;
};

export const CallsPage: FC<{
  entity: string;
  project: string;
  initialFilter?: WFHighLevelCallFilter;
  // Setting this will make the component a controlled component. The parent
  // is responsible for updating the filter.
  onFilterUpdate?: (filter: WFHighLevelCallFilter) => void;
}> = props => {
  const {filter, setFilter} = useInitializingFilter(
    props.initialFilter,
    props.onFilterUpdate
  );

  const title = useMemo(() => {
    // const traceRootsOnly = !(
    //   !!filter.opVersionRefs ||
    //   !!filter.inputObjectVersionRefs ||
    //   !!filter.parentId
    // );
    // if (traceRootsOnly) {
    //   return 'Root Traces';
    // }
    if (filter.opVersionRefs?.length === 1) {
      const opName = opVersionRefOpName(filter.opVersionRefs[0]);
      return opNiceName(opName) + ' Traces';
    } else if (filter.opCategory) {
      return _.capitalize(filter.opCategory) + ' Traces';
    }
    return 'Traces';
  }, [filter.opCategory, filter.opVersionRefs]);

  return (
    <SimplePageLayout
      title={title}
      hideTabsIfSingle
      tabs={[
        {
          label: 'All',
          content: (
            <CallsTable
              {...props}
              initialFilter={filter}
              onFilterUpdate={setFilter}
            />
          ),
        },
      ]}
    />
  );
};

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
}> = props => {
  const {baseRouter} = useWeaveflowRouteContext();
  // const orm = useWeaveflowORMContext(props.entity, props.project);

  const {filter, setFilter} = useInitializingFilter(
    props.initialFilter,
    props.onFilterUpdate
  );

  const effectiveFilter = useMemo(() => {
    return {...filter, ...props.frozenFilter};
  }, [filter, props.frozenFilter]);

  const lowLevelFilter: CallFilter = useMemo(() => {
    return convertHighLevelFilterToLowLevelFilter(effectiveFilter);
  }, [effectiveFilter]);

  const calls = useCalls(props.entity, props.project, lowLevelFilter);

  // # TODO: All of these need to be handled much more logically since
  // we need to calculate the options based on everything except a specific filter.
  // Rules: Show all if loading and inexpensive (if expensive, none), show options based on the filtered data if not loading.... (new) always allow additions
  const opVersionOptions = useOpVersionOptions(
    props.entity,
    props.project,
    effectiveFilter
  );

  const consumesObjectVersionOptions: {[key: string]: string} = {};
  // const consumesObjectVersionOptions = useConsumesObjectVersionOptions(
  //   orm,
  //   props.entity,
  //   props.project,
  //   effectiveFilter
  // );
  const parentIdOptions: {[key: string]: string} = {};
  // const parentIdOptions = useParentIdOptions(
  //   orm,
  //   props.entity,
  //   props.project,
  //   effectiveFilter
  // );
  const opCategoryOptions = OP_CATEGORIES;
  // const opCategoryOptions = useOpCategoryOptions(
  //   orm,
  //   props.entity,
  //   props.project,
  //   effectiveFilter
  // );
  const traceRootOptions = [true, false];
  // const traceRootOptions = useTraceRootOptions(
  //   orm,
  //   props.entity,
  //   props.project,
  //   effectiveFilter
  // );
  const {onMakeBoard, isGenerating} = useMakeBoardForCalls(
    props.entity,
    props.project,
    lowLevelFilter
  );

  const userEnabledPivot = effectiveFilter.isPivot ?? false;
  const setUserEnabledPivot = useCallback(
    (enabled: boolean) => {
      setFilter({
        ...filter,
        isPivot: enabled,
        // Reset the pivot dims when disabling pivot
        pivotSpec:
          filter.pivotSpec?.colDim == null || filter.pivotSpec?.rowDim == null
            ? undefined
            : filter.pivotSpec,
      });
    },
    [filter, setFilter]
  );
  const setPivotDims = useCallback(
    (spec: Partial<WFHighLevelPivotSpec>) => {
      if (
        filter.pivotSpec?.colDim !== spec.colDim ||
        filter.pivotSpec?.rowDim !== spec.rowDim
      ) {
        setFilter({
          ...filter,
          pivotSpec: {
            ...filter.pivotSpec,
            ...spec,
          },
        });
      }
    },
    [filter, setFilter]
  );

  const qualifiesForPivoting = useMemo(() => {
    const shownSpanNames = _.uniq(
      (calls.result ?? []).map(span => span.spanName)
    );
    // Super restrictive for now - just showing pivot when
    // there is only one span name and it is the evaluation.
    return (
      shownSpanNames.length === 1 &&
      shownSpanNames[0].includes('Evaluation-evaluate')
    );
  }, [calls.result]);

  const isPivoting = userEnabledPivot && qualifiesForPivoting;
  const hidePivotControls = true;
  const clearFilters = useMemo(() => {
    if (Object.keys(filter ?? {}).length > 0) {
      return () => setFilter({});
    }
    return null;
  }, [filter, setFilter]);

  return (
    <FilterLayoutTemplate
      showFilterIndicator={Object.keys(effectiveFilter ?? {}).length > 0}
      showPopoutButton={Object.keys(props.frozenFilter ?? {}).length > 0}
      filterPopoutTargetUrl={baseRouter.callsUIUrl(
        props.entity,
        props.project,
        effectiveFilter
      )}
      filterListSx={{
        // Hide until we show filters
        pb: isPivoting && !hidePivotControls ? 0 : 1,
        display: props.hideControls ? 'none' : 'flex',
      }}
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
          {qualifiesForPivoting && (
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
                renderInput={params => {
                  console.log(params);

                  return <TextField {...params} label="Category" />;
                }}
                value={effectiveFilter.opCategory ?? null}
                onChange={(event, newValue) => {
                  setFilter({
                    ...filter,
                    opCategory: newValue,
                  });
                }}
                options={opCategoryOptions}
                // renderOption={(props, option, {selected}) => {
                //   return (
                //     <li {...props}>
                //       <CategoryChip value={option} />
                //     </li>
                //   );
                // }}
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
                value={effectiveFilter.opVersionRefs?.[0] ?? null}
                onChange={(event, newValue) => {
                  setFilter({
                    ...filter,
                    opVersionRefs: newValue ? [newValue] : [],
                  });
                }}
                renderInput={params => <TextField {...params} label="Op" />}
                getOptionLabel={option => {
                  return opVersionOptions[option]?.title;
                }}
                groupBy={option => opVersionOptions[option]?.group}
                options={Object.keys(opVersionOptions)}
                // freeSolo
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
                value={effectiveFilter.inputObjectVersionRefs?.[0] ?? null}
                onChange={(event, newValue) => {
                  setFilter({
                    ...filter,
                    inputObjectVersionRefs: newValue ? [newValue] : [],
                  });
                }}
                // getOptionLabel={option => {
                //   return consumesObjectVersionOptions[option] ?? option;
                // }}
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
                // getOptionLabel={option => {
                //   return parentIdOptions[option] ?? option;
                // }}
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
      }>
      {isPivoting ? (
        <PivotRunsView
          loading={calls.loading}
          runs={calls.result ?? []}
          pivotSpec={effectiveFilter.pivotSpec ?? {}}
          onPivotSpecChange={setPivotDims}
          entity={props.entity}
          project={props.project}
          showCompareButton
          // Since we have a very constrained pivot, we can hide
          // the controls for now as there is no need to change them.
          // Punting on design
          hideControls={hidePivotControls}
        />
      ) : (
        <RunsTable
          loading={calls.loading}
          spans={calls.result ?? []}
          clearFilters={clearFilters}
          ioColumnsOnly={props.ioColumnsOnly}
        />
      )}
    </FilterLayoutTemplate>
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
  effectiveFilter: WFHighLevelCallFilter
): CallFilter => {
  return {
    // traceRootsOnly: !(
    //   !!effectiveFilter.opVersionRefs ||
    //   !!effectiveFilter.inputObjectVersionRefs ||
    //   !!effectiveFilter.parentId
    // ),
    traceRootsOnly: effectiveFilter.traceRootsOnly,
    opVersionRefs: effectiveFilter.opVersionRefs,
    inputObjectVersionRefs: effectiveFilter.inputObjectVersionRefs,
    // outputUris: effectiveFilter.outputObjectVersionRefs,
    // traceId: effectiveFilter.traceId ?? undefined,
    parentIds: effectiveFilter.parentId
      ? [effectiveFilter.parentId]
      : undefined,
    opCategory: effectiveFilter.opCategory
      ? [effectiveFilter.opCategory]
      : undefined,
  };
};

const useOpVersionOptions = (
  entity: string,
  project: string,
  effectiveFilter: WFHighLevelCallFilter
) => {
  // Get all the "latest" versions
  const latestOpVersions = useOpVersions(entity, project, {
    latestOnly: true,
  });

  // Get all the versions of the currently selected op
  const currentRef = effectiveFilter.opVersionRefs?.[0] ?? null;
  const currentOpId = currentRef ? refUriToOpVersionKey(currentRef).opId : null;
  const currentVersions = useOpVersions(
    entity,
    project,
    {
      opIds: [currentOpId ?? ''],
    },
    {
      skip: !currentOpId,
    }
  );

  return useMemo(() => {
    let result: Array<{title: string; ref: string; group: string}> = [];

    latestOpVersions.result?.forEach(ov => {
      const ref = opVersionKeyToRefUri({
        ...ov,
        versionHash: '*',
      });
      result.push({
        title: opNiceName(ov.opId),
        ref,
        group: 'Ops',
      });
    });

    currentVersions.result?.forEach(ov => {
      const ref = opVersionKeyToRefUri(ov);
      result.push({
        title: ov.opId + ':v' + ov.versionIndex,
        ref,
        group: `Versions of ${opNiceName(currentOpId!)}`,
      });
    });

    return _.fromPairs(
      _.sortBy(result, r => `${r.group}:${r.title}`).map(r => [r.ref, r])
    );
  }, [currentOpId, currentVersions.result, latestOpVersions.result]);
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
        _.omit(highLevelFilter, ['inputObjectVersions'])
      );
    }, [highLevelFilter])
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
        return [v.refUri(), v.object().name() + ':v' + v.versionIndex()];
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
        _.omit(highLevelFilter, ['parentId'])
      );
    }, [highLevelFilter])
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

    const pairs = _.uniqBy(
      parents.map(c => {
        const version = c.opVersion();
        if (!version) {
          return [c.traceID(), c.spanName()];
        }
        return [
          c.callID(),
          opNiceName(version.op().name()) + ' (' + truncateID(c.callID()) + ')',
        ];
      }),
      p => p[1]
    );

    pairs.sort((a, b) => {
      return a[1].localeCompare(b[1]);
    });

    return _.fromPairs(pairs);
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
        _.omit(highLevelFilter, ['opCategory'])
      );
    }, [highLevelFilter])
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

// const useTraceRootOptions = (
//   orm: WeaveflowORMContextType,
//   entity: string,
//   project: string,
//   highLevelFilter: WFHighLevelCallFilter
// ) => {
//   const runs = useRunsWithFeedback(
//     {
//       entityName: entity,
//       projectName: project,
//       streamName: 'stream',
//     },
//     useMemo(() => {
//       return convertHighLevelFilterToLowLevelFilter(
//         _.omit(highLevelFilter, ['traceRootsOnly'])
//       );
//     }, [highLevelFilter])
//   );
//   return useMemo(() => {
//     if (runs.loading) {
//       return [true, false];
//     }
//     return _.uniq(runs.result.map(r => r.parent_id == null));
//   }, [runs.loading, runs.result]);
// };
