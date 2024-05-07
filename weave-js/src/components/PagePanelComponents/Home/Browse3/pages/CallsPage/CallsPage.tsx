// import {PivotTableChart} from '@mui/icons-material';
import {
  Autocomplete,
  Chip,
  FormControl,
  // IconButton,
  ListItem,
} from '@mui/material';
import _ from 'lodash';
import React, {FC, useCallback, useMemo} from 'react';

import {Loading} from '../../../../../Loading';
import {RunsTable} from '../../../Browse2/RunsTable';
import {
  useWeaveflowRouteContext,
  WeaveHeaderExtrasContext,
} from '../../context';
import {StyledPaper} from '../../StyledAutocomplete';
import {StyledTextField} from '../../StyledTextField';
import {Empty} from '../common/Empty';
import {
  EMPTY_PROPS_EVALUATIONS,
  EMPTY_PROPS_TRACES,
} from '../common/EmptyContent';
import {
  EVALUATE_OP_NAME_POST_PYDANTIC,
  isEvaluateOp,
} from '../common/heuristics';
import {opNiceName} from '../common/Links';
import {FilterLayoutTemplate} from '../common/SimpleFilterableDataTable';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {truncateID, useInitializingFilter} from '../util';
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
  opVersionRefs?: string[];
  inputObjectVersionRefs?: string[];
  outputObjectVersionRefs?: string[];
  parentId?: string | null;
  isPivot?: boolean;
  pivotSpec?: Partial<WFHighLevelPivotSpec>;
  // This really doesn't belong here. We are using it to indicate that the
  // filter is frozen and should not be updated by the user. However, this
  // control should really be managed outside of the filter itself.
  frozen?: boolean;
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

  const isEvaluationTable = useCurrentFilterIsEvaluationsFilter(
    filter,
    props.entity,
    props.project
  );

  const title = useMemo(() => {
    if (isEvaluationTable) {
      return 'Evaluations';
    }
    if (filter.opVersionRefs?.length === 1) {
      const opName = opVersionRefOpName(filter.opVersionRefs[0]);
      return opNiceName(opName) + ' Traces';
    }
    return 'Traces';
  }, [filter.opVersionRefs, isEvaluationTable]);

  const {renderExtras} = React.useContext(WeaveHeaderExtrasContext);

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
              hideControls={filter.frozen}
              initialFilter={filter}
              onFilterUpdate={setFilter}
            />
          ),
        },
      ]}
      headerExtra={renderExtras()}
    />
  );
};

const ALL_TRACES_REF_KEY = '__all_traces__';
const ALL_CALLS_REF_KEY = '__all_calls__';
const OP_FILTER_GROUP_HEADER = 'Op';
const ANY_OP_GROUP_HEADER = '';
const ALL_TRACES_TITLE = 'All Ops';
const ALL_CALLS_TITLE = 'All Calls';
const OP_GROUP_HEADER = 'Ops';
const OP_VERSION_GROUP_HEADER = (currentOpId: string) =>
  `Specific Versions of ${opNiceName(currentOpId)}`;
const ALLOW_ALL_CALLS_UNFILTERED = false;

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
    const workingFilter = {...filter, ...props.frozenFilter};
    if (
      !ALLOW_ALL_CALLS_UNFILTERED &&
      !currentFilterShouldUseNonTraceRoots(workingFilter)
    ) {
      // If we are not allowing all calls unfiltered (meaning the totally
      // unfiltered list of all calls is disabled) and the current filter
      // settings do not call for non-trace roots only, then we should force
      // trace roots only.
      workingFilter.traceRootsOnly = true;
    }
    return workingFilter;
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
  const opVersionOptionsWithRoots: {
    [ref: string]: {
      title: string;
      ref: string;
      group: string;
      objectVersion?: OpVersionSchema;
    };
  } = useMemo(() => {
    return {
      [ALL_TRACES_REF_KEY]: {
        title: ALL_TRACES_TITLE,
        ref: '',
        group: ANY_OP_GROUP_HEADER,
      },
      ...(ALLOW_ALL_CALLS_UNFILTERED
        ? {
            [ALL_CALLS_REF_KEY]: {
              title: ALL_CALLS_TITLE,
              ref: '',
              group: ANY_OP_GROUP_HEADER,
            },
          }
        : {}),
      ...opVersionOptions,
    };
  }, [opVersionOptions]);
  const opVersionRef = effectiveFilter.opVersionRefs?.[0] ?? null;
  const opVersionRefOrAllTitle = useMemo(() => {
    return (
      opVersionRef ??
      (effectiveFilter.traceRootsOnly ? ALL_TRACES_REF_KEY : ALL_CALLS_REF_KEY)
    );
  }, [opVersionRef, effectiveFilter.traceRootsOnly]);

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

  const callsKey = useMemo(() => {
    if (calls.loading || calls.result == null) {
      return null;
    }
    return Math.random();
  }, [calls.loading, calls.result]);

  const isEvaluateTable = useCurrentFilterIsEvaluationsFilter(
    effectiveFilter,
    props.entity,
    props.project
  );

  if (calls.loading) {
    return <Loading centered />;
  }

  const spans = calls.result ?? [];
  const isEmpty = spans.length === 0;
  if (isEmpty) {
    if (isEvaluateTable) {
      return <Empty {...EMPTY_PROPS_EVALUATIONS} />;
    } else {
      return <Empty {...EMPTY_PROPS_TRACES} />;
    }
  }

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
          <ListItem sx={{minWidth: '190px'}}>
            <FormControl fullWidth>
              <Autocomplete
                PaperComponent={paperProps => <StyledPaper {...paperProps} />}
                size="small"
                // Temp disable multiple for simplicity - may want to re-enable
                // multiple
                limitTags={1}
                disabled={
                  isPivoting ||
                  Object.keys(props.frozenFilter ?? {}).includes('opVersions')
                }
                value={opVersionRefOrAllTitle}
                onChange={(event, newValue) => {
                  if (newValue === ALL_TRACES_REF_KEY) {
                    setFilter({
                      ...filter,
                      traceRootsOnly: true,
                      opVersionRefs: [],
                    });
                  } else if (newValue === ALL_CALLS_REF_KEY) {
                    setFilter({
                      ...filter,
                      traceRootsOnly: false,
                      opVersionRefs: [],
                    });
                  } else {
                    setFilter({
                      ...filter,
                      opVersionRefs: newValue ? [newValue] : [],
                    });
                  }
                }}
                renderInput={params => (
                  <StyledTextField
                    {...params}
                    label={OP_FILTER_GROUP_HEADER}
                    sx={{maxWidth: '350px'}}
                  />
                )}
                getOptionLabel={option => {
                  return (
                    opVersionOptionsWithRoots[option]?.title ?? 'loading...'
                  );
                }}
                disableClearable={
                  opVersionRefOrAllTitle === ALL_TRACES_REF_KEY ||
                  opVersionRefOrAllTitle === ALL_CALLS_REF_KEY
                }
                groupBy={option => opVersionOptionsWithRoots[option]?.group}
                options={Object.keys(opVersionOptionsWithRoots)}
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
          spans={spans}
          clearFilters={clearFilters}
          ioColumnsOnly={props.ioColumnsOnly}
        />
      )}
    </FilterLayoutTemplate>
  );
};

const currentFilterShouldUseNonTraceRoots = (filter: WFHighLevelCallFilter) => {
  return (
    (filter.inputObjectVersionRefs?.length ?? 0) > 0 ||
    (filter.opVersionRefs?.length ?? 0) > 0 ||
    filter.parentId != null
  );
};

const convertHighLevelFilterToLowLevelFilter = (
  effectiveFilter: WFHighLevelCallFilter
): CallFilter => {
  const forcingNonTraceRootsOnly =
    currentFilterShouldUseNonTraceRoots(effectiveFilter);
  return {
    traceRootsOnly: !forcingNonTraceRootsOnly && effectiveFilter.traceRootsOnly,
    opVersionRefs: effectiveFilter.opVersionRefs,
    inputObjectVersionRefs: effectiveFilter.inputObjectVersionRefs,
    outputObjectVersionRefs: effectiveFilter.outputObjectVersionRefs,
    parentIds: effectiveFilter.parentId
      ? [effectiveFilter.parentId]
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
        group: OP_GROUP_HEADER,
      });
    });

    if (currentOpId) {
      _.sortBy(currentVersions.result ?? [], ov => -ov.versionIndex).forEach(
        ov => {
          const ref = opVersionKeyToRefUri(ov);
          result.push({
            title: opNiceName(ov.opId) + ':v' + ov.versionIndex,
            ref,
            group: OP_VERSION_GROUP_HEADER(currentOpId),
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

export const useEvaluationsFilter = (
  entity: string,
  project: string
): WFHighLevelCallFilter => {
  return useMemo(() => {
    return {
      frozen: true,
      opVersionRefs: [
        opVersionKeyToRefUri({
          entity,
          project,
          opId: EVALUATE_OP_NAME_POST_PYDANTIC,
          versionHash: '*',
        }),
      ],
    };
  }, [entity, project]);
};

export const useCurrentFilterIsEvaluationsFilter = (
  currentFilter: WFHighLevelCallFilter,
  entity: string,
  project: string
) => {
  const evaluationsFilter = useEvaluationsFilter(entity, project);
  return _.isEqual(currentFilter, evaluationsFilter);
};
