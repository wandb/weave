/**
 * Step 3: Perf of the compare view is really bad
 * TODO: The Pivot Table and Calls Compare are pretty jank and the typing is off: really should refactor since it is likely needed to push the grouping down to the server.
 * Trace roots is still pretty confusing...
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
  Chip,
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

import {fnRunsNode} from '../../../Browse2/callTreeHooks';
import {RunsTable} from '../../../Browse2/RunsTable';
import {useWeaveflowRouteContext} from '../../context';
import {useMakeNewBoard} from '../common/hooks';
import {opNiceName} from '../common/Links';
import {FilterLayoutTemplate} from '../common/SimpleFilterableDataTable';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {truncateID, useInitializingFilter} from '../util';
import {HackyOpCategory} from '../wfInterface/types';
import {
  CallFilter,
  OP_CATEGORIES,
  opVersionKeyToRefUri,
  opVersionRefOpName,
  OpVersionSchema,
  refUriToObjectVersionKey,
  refUriToOpVersionKey,
  useCall,
  useCalls,
  useObjectVersion,
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
      const niceName = opNiceName(opName);
      if (niceName == 'Evaluation-evaluate') {
        // Very special case for now
        if (filter.isPivot) {
          return 'Evaluation Leaderboard';
        }
      }
      return opNiceName(opName) + ' Traces';
    } else if (filter.opCategory) {
      return _.capitalize(filter.opCategory) + ' Traces';
    }
    return 'Traces';
  }, [filter.isPivot, filter.opCategory, filter.opVersionRefs]);

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

  console.log({lowLevelFilter});
  const calls = useCalls(props.entity, props.project, lowLevelFilter);

  const opVersionOptions = useOpVersionOptions(
    props.entity,
    props.project,
    effectiveFilter
  );
  const opVersionRef = effectiveFilter.opVersionRefs?.[0] ?? null;
  const opVersion = opVersionRef
    ? opVersionOptions[opVersionRef]?.objectVersion
    : null;

  const consumesObjectVersionOptions = useConsumesObjectVersionOptions(
    props.entity,
    props.project,
    effectiveFilter
  );
  const inputObjectVersionRef =
    effectiveFilter.inputObjectVersionRefs?.[0] ?? null;
  const inputObjectVersion = inputObjectVersionRef
    ? consumesObjectVersionOptions[inputObjectVersionRef]
    : null;

  // const parentIdOptions: {[key: string]: string} = {};
  const parentIdOptions = useParentIdOptions(
    props.entity,
    props.project,
    effectiveFilter
  );
  const parentOpDisplay = effectiveFilter.parentId
    ? parentIdOptions[effectiveFilter.parentId]
    : null;
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

  const forcingNonTraceRootsOnly =
    (effectiveFilter.inputObjectVersionRefs?.length ?? 0) > 0 ||
    (effectiveFilter.opVersionRefs?.length ?? 0) > 0 ||
    effectiveFilter.parentId != null ||
    effectiveFilter.opCategory != null;

  const rootsOnlyDisabled =
    forcingNonTraceRootsOnly ||
    isPivoting ||
    traceRootOptions.length <= 1 ||
    Object.keys(props.frozenFilter ?? {}).includes('traceRootsOnly');

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

          <IconButton
            style={{width: '37px', height: '37px'}}
            size="small"
            color={userEnabledPivot ? 'primary' : 'default'}
            disabled={!qualifiesForPivoting}
            onClick={() => {
              setUserEnabledPivot(!userEnabledPivot);
            }}>
            <PivotTableChart />
          </IconButton>

          <ListItem sx={{width: '190px', flex: '0 0 190px'}}>
            <FormControl fullWidth>
              <Autocomplete
                size={'small'}
                disabled={
                  isPivoting ||
                  Object.keys(props.frozenFilter ?? {}).includes(
                    'opCategory'
                  ) ||
                  (effectiveFilter.opVersionRefs ?? []).length > 0
                }
                renderInput={params => {
                  return <TextField {...params} label="Category" />;
                }}
                value={
                  effectiveFilter.opCategory ?? opVersion?.category ?? null
                }
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
          <ListItem sx={{minWidth: '190px'}}>
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
          {/* <ListItem>
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
                getOptionLabel={option => {
                  return consumesObjectVersionOptions[option] ?? option;
                }}
                options={Object.keys(consumesObjectVersionOptions)}
              />
            </FormControl>
          </ListItem> */}
          {inputObjectVersion && (
            <Chip
              label={`Input: ${inputObjectVersion.objectId}:v${inputObjectVersion.versionIndex}`}
              onDelete={() => {
                setFilter({
                  ...filter,
                  inputObjectVersionRefs: undefined,
                });
              }}
            />
          )}
          {/* <ListItem>
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
          </ListItem> */}
          {parentOpDisplay && (
            <Chip
              label={`Parent: ${parentOpDisplay}`}
              onDelete={() => {
                setFilter({
                  ...filter,
                  parentId: undefined,
                });
              }}
            />
          )}
          <ListItem
            sx={{
              width: '190px',
              flex: '0 0 190px',
              // borderLeft: '1px solid #e0e0e0',
            }}
            secondaryAction={
              <Checkbox
                edge="end"
                checked={
                  !forcingNonTraceRootsOnly && !!effectiveFilter.traceRootsOnly
                }
              />
            }
            disabled={rootsOnlyDisabled}
            disablePadding>
            <ListItemButton
              onClick={() => {
                if (rootsOnlyDisabled) {
                  return;
                }
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
  const forcingNonTraceRootsOnly =
    (effectiveFilter.inputObjectVersionRefs?.length ?? 0) > 0 ||
    (effectiveFilter.opVersionRefs?.length ?? 0) > 0 ||
    effectiveFilter.parentId != null ||
    effectiveFilter.opCategory != null;
  return {
    // traceRootsOnly: !(
    //   !!effectiveFilter.opVersionRefs ||
    //   !!effectiveFilter.inputObjectVersionRefs ||
    //   !!effectiveFilter.parentId
    // ),
    traceRootsOnly: !forcingNonTraceRootsOnly && effectiveFilter.traceRootsOnly,
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
  const latestVersions = useOpVersions(entity, project, {
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
    let result: Array<{
      title: string;
      ref: string;
      group: string;
      objectVersion?: OpVersionSchema;
    }> = [];

    latestVersions.result?.forEach(ov => {
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
        objectVersion: ov,
      });
    });

    return _.fromPairs(
      _.sortBy(result, r => `${r.group}:${r.title}`).map(r => [r.ref, r])
    );
  }, [currentOpId, currentVersions.result, latestVersions.result]);
};

const useConsumesObjectVersionOptions = (
  entity: string,
  project: string,
  effectiveFilter: WFHighLevelCallFilter
) => {
  // We don't populate this one because it is expensive
  const currentRef = effectiveFilter.inputObjectVersionRefs?.[0] ?? null;
  const objectVersion = useObjectVersion(
    currentRef ? refUriToObjectVersionKey(currentRef) : null
  );
  return useMemo(() => {
    if (!currentRef || objectVersion.loading || !objectVersion.result) {
      return {};
    }
    return {
      [currentRef]: objectVersion.result,
    };
  }, [currentRef, objectVersion.loading, objectVersion.result]);
};

const useParentIdOptions = (
  entity: string,
  project: string,
  effectiveFilter: WFHighLevelCallFilter
) => {
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
