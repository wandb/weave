import {CircularProgress, IconButton} from '@material-ui/core';
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
import _ from 'lodash';
import React, {useCallback, useMemo} from 'react';

import {CallFilter} from '../../../Browse2/callTree';
import {fnRunsNode, useRunsWithFeedback} from '../../../Browse2/callTreeHooks';
import {RunsTable} from '../../../Browse2/RunsTable';
import {useWeaveflowRouteContext} from '../../context';
import {useMakeNewBoard} from '../common/hooks';
import {opNiceName} from '../common/Links';
import {FilterLayoutTemplate} from '../common/SimpleFilterableDataTable';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {truncateID, useInitializingFilter} from '../util';
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
import {PivotRunsView, WFHighLevelPivotSpec} from './PivotRunsTable';

export type WFHighLevelCallFilter = {
  traceRootsOnly?: boolean;
  opCategory?: HackyOpCategory | null;
  opVersions?: string[];
  inputObjectVersions?: string[];
  parentId?: string | null;
  traceId?: string | null;
  isPivot?: boolean;
  pivotSpec?: Partial<WFHighLevelPivotSpec>;
};

export const CallsPage: React.FC<{
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
    if (filter.opCategory) {
      return _.capitalize(filter.opCategory) + ' Calls';
    }
    return 'Calls';
  }, [filter.opCategory]);

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

  const {filter, setFilter} = useInitializingFilter(
    props.initialFilter,
    props.onFilterUpdate
  );

  const effectiveFilter = useMemo(() => {
    return {...filter, ...props.frozenFilter};
  }, [filter, props.frozenFilter]);

  const lowLevelFilter: CallFilter = useMemo(() => {
    return convertHighLevelFilterToLowLevelFilter(orm, effectiveFilter);
  }, [effectiveFilter, orm]);

  const runsWithFeedbackQuery = useRunsWithFeedback(
    {
      entityName: props.entity,
      projectName: props.project,
      streamName: 'stream',
    },
    lowLevelFilter
  );

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
    // return true;
    const shownSpanNames = _.uniq(
      runsWithFeedbackQuery.result.map(span => span.name)
    );
    // Super restrictive for now - just showing pivot when
    // there is only one span name and it is the evaluation.
    return (
      shownSpanNames.length === 1 &&
      shownSpanNames[0].includes('Evaluation-evaluate')
    );
  }, [runsWithFeedbackQuery.result]);

  const isPivoting = userEnabledPivot && qualifiesForPivoting;

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
        pb: isPivoting ? 0 : 1,
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
      }>
      {isPivoting ? (
        <PivotRunsView
          loading={runsWithFeedbackQuery.loading}
          runs={runsWithFeedbackQuery.result}
          pivotSpec={effectiveFilter.pivotSpec ?? {}}
          onPivotSpecChange={setPivotDims}
          entity={props.entity}
          project={props.project}
          showCompareButton
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
