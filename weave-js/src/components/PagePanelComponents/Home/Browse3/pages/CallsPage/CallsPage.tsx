// import {PivotTableChart} from '@mui/icons-material';
import {
  Autocomplete,
  Checkbox,
  Chip,
  FormControl,
  // IconButton,
  ListItem,
  ListItemButton,
  ListItemText,
  TextField,
} from '@mui/material';
import _ from 'lodash';
import React, {FC, useCallback, useMemo} from 'react';

import {RunsTable} from '../../../Browse2/RunsTable';
import {useWeaveflowRouteContext} from '../../context';
import {isEvaluateOp} from '../common/heuristics';
import {opNiceName} from '../common/Links';
import {FilterLayoutTemplate} from '../common/SimpleFilterableDataTable';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {truncateID, useInitializingFilter} from '../util';
import {HackyOpCategory} from '../wfInterface/types';
import {OP_CATEGORIES} from '../wfReactInterface/constants';
import {useWFHooks} from '../wfReactInterface/context';
import {
  objectVersionNiceString,
  opVersionKeyToRefUri,
  opVersionRefOpName,
  refUriToObjectVersionKey,
  refUriToOpVersionKey,
} from '../wfReactInterface/utilities';
import {
  CallFilter,
  OpVersionSchema,
} from '../wfReactInterface/wfDataModelHooksInterface';
import {PivotRunsView, WFHighLevelPivotSpec} from './PivotRunsTable';

export type WFHighLevelCallFilter = {
  traceRootsOnly?: boolean;
  opCategory?: HackyOpCategory | null;
  opVersionRefs?: string[];
  inputObjectVersionRefs?: string[];
  outputObjectVersionRefs?: string[];
  parentId?: string | null;
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
    if (filter.opVersionRefs?.length === 1) {
      const opName = opVersionRefOpName(filter.opVersionRefs[0]);
      const niceName = opNiceName(opName);
      if (isEvaluateOp(niceName)) {
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
  const {useCalls} = useWFHooks();
  const {baseRouter} = useWeaveflowRouteContext();
  const {filter, setFilter} = useInitializingFilter(
    props.initialFilter,
    props.onFilterUpdate
  );

  const effectiveFilter = useMemo(() => {
    return {...filter, ...props.frozenFilter};
  }, [filter, props.frozenFilter]);

  if ((effectiveFilter.opVersionRefs?.length ?? 0) > 1) {
    throw new Error('Multiple op versions not yet supported');
  }

  if ((effectiveFilter.inputObjectVersionRefs?.length ?? 0) > 1) {
    throw new Error('Multiple input object versions not yet supported');
  }

  if ((effectiveFilter.outputObjectVersionRefs?.length ?? 0) > 1) {
    throw new Error('Multiple output object versions not yet supported');
  }

  const lowLevelFilter: CallFilter = useMemo(() => {
    return convertHighLevelFilterToLowLevelFilter(effectiveFilter);
  }, [effectiveFilter]);

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

  const consumesObjectVersionOptions =
    useConsumesObjectVersionOptions(effectiveFilter);
  const inputObjectVersionRef =
    effectiveFilter.inputObjectVersionRefs?.[0] ?? null;
  const inputObjectVersion = inputObjectVersionRef
    ? consumesObjectVersionOptions[inputObjectVersionRef]
    : null;

  const producesObjectVersionOptions =
    useProducesObjectVersionOptions(effectiveFilter);
  const outputObjectVersionRef =
    effectiveFilter.outputObjectVersionRefs?.[0] ?? null;
  const outputObjectVersion = outputObjectVersionRef
    ? producesObjectVersionOptions[outputObjectVersionRef]
    : null;

  const parentIdOptions = useParentIdOptions(
    props.entity,
    props.project,
    effectiveFilter
  );
  const parentOpDisplay = effectiveFilter.parentId
    ? parentIdOptions[effectiveFilter.parentId]
    : null;
  const opCategoryOptions = useMemo(() => {
    return _.sortBy(OP_CATEGORIES, _.identity);
  }, []);
  const traceRootOptions = [true, false];

  const userEnabledPivot = effectiveFilter.isPivot ?? false;
  // TODO: Decide if we want to expose pivot or remove.
  // const setUserEnabledPivot = useCallback(
  //   (enabled: boolean) => {
  //     setFilter({
  //       ...filter,
  //       isPivot: enabled,
  //       // Reset the pivot dims when disabling pivot
  //       pivotSpec:
  //         filter.pivotSpec?.colDim == null || filter.pivotSpec?.rowDim == null
  //           ? undefined
  //           : filter.pivotSpec,
  //     });
  //   },
  //   [filter, setFilter]
  // );
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
    return shownSpanNames.length === 1 && isEvaluateOp(shownSpanNames[0]);
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
    shouldForceNonTraceRootsOnly(effectiveFilter);

  const rootsOnlyDisabled =
    forcingNonTraceRootsOnly ||
    isPivoting ||
    traceRootOptions.length <= 1 ||
    Object.keys(props.frozenFilter ?? {}).includes('traceRootsOnly');

  const callsKey = useMemo(() => {
    if (calls.loading || calls.result == null) {
      return null;
    }
    return Math.random();
  }, [calls.loading, calls.result]);

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
          {/* <IconButton
            style={{width: '37px', height: '37px'}}
            size="small"
            color={userEnabledPivot ? 'primary' : 'default'}
            disabled={!qualifiesForPivoting}
            onClick={() => {
              setUserEnabledPivot(!userEnabledPivot);
            }}>
            <PivotTableChart />
          </IconButton> */}

          {/* <ListItem sx={{width: '190px', flex: '0 0 190px'}}>
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
              />
            </FormControl>
          </ListItem> */}
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
                value={opVersionRef}
                onChange={(event, newValue) => {
                  setFilter({
                    ...filter,
                    opVersionRefs: newValue ? [newValue] : [],
                  });
                }}
                renderInput={params => <TextField {...params} label="Op" />}
                getOptionLabel={option => {
                  return opVersionOptions[option]?.title ?? 'loading...';
                }}
                groupBy={option => opVersionOptions[option]?.group}
                options={Object.keys(opVersionOptions)}
              />
            </FormControl>
          </ListItem>
          {inputObjectVersion && (
            <Chip
              label={`Input: ${objectVersionNiceString(inputObjectVersion)}`}
              onDelete={() => {
                setFilter({
                  ...filter,
                  inputObjectVersionRefs: undefined,
                });
              }}
            />
          )}
          {outputObjectVersion && (
            <Chip
              label={`Output: ${objectVersionNiceString(outputObjectVersion)}`}
              onDelete={() => {
                setFilter({
                  ...filter,
                  outputObjectVersionRefs: undefined,
                });
              }}
            />
          )}
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
            }}
            secondaryAction={
              <Checkbox
                edge="end"
                checked={
                  !forcingNonTraceRootsOnly && !!effectiveFilter.traceRootsOnly
                }
                onClick={() => {
                  if (rootsOnlyDisabled) {
                    return;
                  }
                  setFilter({
                    ...filter,
                    traceRootsOnly: !effectiveFilter.traceRootsOnly,
                  });
                }}
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
              <ListItemText primary="Roots only" />
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
          key={callsKey}
          loading={calls.loading}
          spans={calls.result ?? []}
          clearFilters={clearFilters}
          ioColumnsOnly={props.ioColumnsOnly}
        />
      )}
    </FilterLayoutTemplate>
  );
};

const shouldForceNonTraceRootsOnly = (filter: WFHighLevelCallFilter) => {
  return (
    (filter.inputObjectVersionRefs?.length ?? 0) > 0 ||
    (filter.opVersionRefs?.length ?? 0) > 0 ||
    filter.parentId != null ||
    filter.opCategory != null
  );
};

const convertHighLevelFilterToLowLevelFilter = (
  effectiveFilter: WFHighLevelCallFilter
): CallFilter => {
  const forcingNonTraceRootsOnly =
    shouldForceNonTraceRootsOnly(effectiveFilter);
  return {
    traceRootsOnly: !forcingNonTraceRootsOnly && effectiveFilter.traceRootsOnly,
    opVersionRefs: effectiveFilter.opVersionRefs,
    inputObjectVersionRefs: effectiveFilter.inputObjectVersionRefs,
    outputObjectVersionRefs: effectiveFilter.outputObjectVersionRefs,
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
  const {useOpVersions} = useWFHooks();
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
    undefined,
    {
      skip: !currentOpId,
    }
  );

  return useMemo(() => {
    const result: Array<{
      title: string;
      ref: string;
      group: string;
      objectVersion?: OpVersionSchema;
    }> = [];

    _.sortBy(latestVersions.result ?? [], ov => [
      opNiceName(ov.opId).toLowerCase(),
      ov.opId.toLowerCase(),
    ]).forEach(ov => {
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

    if (currentOpId) {
      _.sortBy(currentVersions.result ?? [], ov => -ov.versionIndex).forEach(
        ov => {
          const ref = opVersionKeyToRefUri(ov);
          result.push({
            title: opNiceName(ov.opId) + ':v' + ov.versionIndex,
            ref,
            group: `Versions of ${opNiceName(currentOpId)}`,
            objectVersion: ov,
          });
        }
      );
    }

    return _.fromPairs(result.map(r => [r.ref, r]));
  }, [currentOpId, currentVersions.result, latestVersions.result]);
};

const useConsumesObjectVersionOptions = (
  effectiveFilter: WFHighLevelCallFilter
) => {
  const {useObjectVersion} = useWFHooks();
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

const useProducesObjectVersionOptions = (
  effectiveFilter: WFHighLevelCallFilter
) => {
  const {useObjectVersion} = useWFHooks();
  // We don't populate this one because it is expensive
  const currentRef = effectiveFilter.outputObjectVersionRefs?.[0] ?? null;
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
