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
import React, {useEffect, useMemo, useState} from 'react';

import {CallFilter} from '../../Browse2/callTree';
import {useRunsWithFeedback} from '../../Browse2/callTreeHooks';
import {RunsTable} from '../../Browse2/RunsTable';
import {useWeaveflowRouteContext} from '../context';
import {FilterLayoutTemplate} from './common/SimpleFilterableDataTable';
import {SimplePageLayout} from './common/SimplePageLayout';
import {useWeaveflowORMContext} from './wfInterface/context';
import {HackyOpCategory} from './wfInterface/types';

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
    return {
      traceRootsOnly: effectiveFilter.traceRootsOnly,
      opUris: Array.from(
        new Set([...opUrisFromVersions, ...opUrisFromCategory])
      ),
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
  }, [
    effectiveFilter.inputObjectVersions,
    effectiveFilter.opCategory,
    effectiveFilter.opVersions,
    effectiveFilter.parentId,
    effectiveFilter.traceId,
    effectiveFilter.traceRootsOnly,
    orm.projectConnection,
  ]);
  const runs = useRunsWithFeedback(
    {
      entityName: props.entity,
      projectName: props.project,
      streamName: 'stream',
    },
    lowLevelFilter
  );

  // # TODO: All of these need to be handled much more logically since
  // we need to calculate the options based on everything except a specific filter.
  const opVersionOptions = useMemo(() => {
    if (runs.loading) {
      const versions = orm.projectConnection.opVersions();
      // Note: this excludes the named ones without op versions
      const options = versions.map(v => v.op().name() + ':' + v.version());
      return options;
    }
    return _.uniq(
      runs.result.map(r => {
        const version = orm.projectConnection.call(r.span_id)?.opVersion();
        if (!version) {
          return null;
        }
        return version.op().name() + ':' + version.version();
      })
    ).filter(v => v != null) as string[];
  }, [orm.projectConnection, runs.loading, runs.result]);
  const consumesObjectVersionOptions = useMemo(() => {
    if (runs.loading) {
      const versions = orm.projectConnection.objectVersions();
      const options = versions.map(v => v.object().name() + ':' + v.version());
      return options;
    }
    return _.uniq(
      runs.result.flatMap(r => {
        const inputs = orm.projectConnection.call(r.span_id)?.inputs();
        if (!inputs) {
          return null;
        }
        return inputs.map(i => i.object().name() + ':' + i.version());
      })
    ).filter(v => v != null);
  }, [orm.projectConnection, runs.loading, runs.result]);
  const parentIdOptions = useMemo(() => {
    if (runs.loading) {
      const calls = orm.projectConnection.calls();
      const options = calls
        .map(v => v.parentCall()?.callID())
        .filter(v => v != null);
      return options;
    }
    return _.uniq(
      runs.result.map(r =>
        orm.projectConnection.call(r.span_id)?.parentCall()?.callID()
      )
    ).filter(v => v != null);
  }, [orm.projectConnection, runs.loading, runs.result]);
  const traceIdOptions = useMemo(() => {
    if (runs.loading) {
      const calls = orm.projectConnection.calls();
      const options = Array.from(
        new Set(calls.map(v => v.traceID()).filter(v => v != null))
      );
      return options;
    }
    return _.uniq(
      runs.result.map(r => orm.projectConnection.call(r.span_id)?.traceID())
    ).filter(v => v != null);
  }, [orm.projectConnection, runs.loading, runs.result]);
  const opCategoryOptions = useMemo(() => {
    if (runs.loading) {
      return orm.projectConnection.opCategories();
    }
    return _.uniq(
      runs.result.map(r =>
        orm.projectConnection.call(r.span_id)?.opVersion()?.opCategory()
      )
    ).filter(v => v != null);
  }, [orm.projectConnection, runs.loading, runs.result]);
  const traceRootsEnabled = useMemo(() => {
    if (runs.loading) {
      return true;
    }
    return runs.result.some(r => r.parent_id == null);
  }, [runs.loading, runs.result]);

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
          <ListItem>
            <FormControl fullWidth>
              <Autocomplete
                size={'small'}
                disabled={Object.keys(props.frozenFilter ?? {}).includes(
                  'opCategory'
                )}
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
                multiple
                limitTags={1}
                disabled={Object.keys(props.frozenFilter ?? {}).includes(
                  'opVersions'
                )}
                value={effectiveFilter.opVersions ?? []}
                onChange={(event, newValue) => {
                  setFilter({
                    ...filter,
                    opVersions: newValue,
                  });
                }}
                renderInput={params => (
                  <TextField {...params} label="Op" />
                  // <TextField {...params} label="Op Version" />
                )}
                options={opVersionOptions}
              />
            </FormControl>
          </ListItem>
          <ListItem>
            <FormControl fullWidth>
              <Autocomplete
                size={'small'}
                limitTags={1}
                multiple
                disabled={Object.keys(props.frozenFilter ?? {}).includes(
                  'inputObjectVersions'
                )}
                renderInput={params => (
                  <TextField {...params} label="Inputs" />
                  // <TextField {...params} label="Consumes Objects" />
                )}
                value={effectiveFilter.inputObjectVersions ?? []}
                onChange={(event, newValue) => {
                  setFilter({
                    ...filter,
                    inputObjectVersions: newValue,
                  });
                }}
                options={consumesObjectVersionOptions}
              />
            </FormControl>
          </ListItem>
          <ListItem>
            <FormControl fullWidth>
              <Autocomplete
                size={'small'}
                disabled={Object.keys(props.frozenFilter ?? {}).includes(
                  'traceId'
                )}
                renderInput={params => <TextField {...params} label="Trace" />}
                value={effectiveFilter.traceId ?? null}
                onChange={(event, newValue) => {
                  setFilter({
                    ...filter,
                    traceId: newValue,
                  });
                }}
                options={traceIdOptions}
              />
            </FormControl>
          </ListItem>
          <ListItem>
            <FormControl fullWidth>
              <Autocomplete
                size={'small'}
                disabled={Object.keys(props.frozenFilter ?? {}).includes(
                  'parentId'
                )}
                renderInput={params => <TextField {...params} label="Parent" />}
                value={effectiveFilter.parentId ?? null}
                onChange={(event, newValue) => {
                  setFilter({
                    ...filter,
                    parentId: newValue,
                  });
                }}
                options={parentIdOptions}
              />
            </FormControl>
          </ListItem>
          <ListItem
            secondaryAction={
              <Checkbox
                edge="end"
                checked={!!effectiveFilter.traceRootsOnly}
                onChange={() => {
                  setFilter({
                    ...filter,
                    traceRootsOnly: !effectiveFilter.traceRootsOnly,
                  });
                }}
              />
            }
            disabled={
              !traceRootsEnabled ||
              Object.keys(props.frozenFilter ?? {}).includes('traceRootsOnly')
            }
            disablePadding>
            <ListItemButton>
              <ListItemText primary={`Trace Roots Only`} />
            </ListItemButton>
          </ListItem>
        </>
      }>
      <RunsTable loading={runs.loading} spans={runs.result} />
    </FilterLayoutTemplate>
  );
};
