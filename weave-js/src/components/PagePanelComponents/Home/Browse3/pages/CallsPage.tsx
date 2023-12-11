import {
  Autocomplete,
  Checkbox,
  FormControl,
  ListItem,
  ListItemButton,
  ListItemText,
  TextField,
} from '@mui/material';
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
  const routerContext = useWeaveflowRouteContext();
  const orm = useWeaveflowORMContext(props.entity, props.project);
  const opVersionOptions = useMemo(() => {
    const versions = orm.projectConnection.opVersions();
    // Note: this excludes the named ones without op versions
    const options = versions.map(v => v.op().name() + ':' + v.version());
    return options;
  }, [orm.projectConnection]);
  const objectVersionOptions = useMemo(() => {
    const versions = orm.projectConnection.objectVersions();
    const options = versions.map(v => v.object().name() + ':' + v.version());
    return options;
  }, [orm.projectConnection]);
  const opCategoryOptions = useMemo(() => {
    return orm.projectConnection.opCategories();
  }, [orm.projectConnection]);

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
  const useLowLevelFilter: CallFilter = useMemo(() => {
    const opUrisFromVersions =
      effectiveFilter.opVersions?.map(uri => {
        const [opName, version] = uri.split(':');
        const opVersion = orm.projectConnection.opVersion(opName, version);
        return opVersion.refUri();
      }) ?? [];
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
      inputUris: effectiveFilter.inputObjectVersions?.map(uri => {
        const [objectName, version] = uri.split(':');
        const objectVersion = orm.projectConnection.objectVersion(
          objectName,
          version
        );
        return objectVersion.refUri();
      }),
    };
  }, [
    effectiveFilter.inputObjectVersions,
    effectiveFilter.opCategory,
    effectiveFilter.opVersions,
    effectiveFilter.traceRootsOnly,
    orm.projectConnection,
  ]);
  const runs = useRunsWithFeedback(
    {
      entityName: props.entity,
      projectName: props.project,
      streamName: 'stream',
    },
    useLowLevelFilter
  );

  return (
    <FilterLayoutTemplate
      showPopoutButton={Object.keys(props.frozenFilter ?? {}).length > 0}
      filterPopoutTargetUrl={routerContext.callsUIUrl(
        props.entity,
        props.project,
        effectiveFilter
      )}
      filterListItems={
        <>
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
            disabled={Object.keys(props.frozenFilter ?? {}).includes(
              'traceRootsOnly'
            )}
            disablePadding>
            <ListItemButton>
              <ListItemText primary={`Trace Roots Only`} />
            </ListItemButton>
          </ListItem>
          <ListItem>
            <FormControl fullWidth>
              <Autocomplete
                size={'small'}
                disabled={Object.keys(props.frozenFilter ?? {}).includes(
                  'opCategory'
                )}
                renderInput={params => (
                  <TextField {...params} label="Op Category" />
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
                  <TextField {...params} label="Op Version" />
                )}
                options={opVersionOptions}
              />
            </FormControl>
          </ListItem>
          <ListItem>
            <FormControl fullWidth>
              <Autocomplete
                size={'small'}
                multiple
                disabled={Object.keys(props.frozenFilter ?? {}).includes(
                  'inputObjectVersions'
                )}
                renderInput={params => (
                  <TextField {...params} label="Consumes Objects" />
                )}
                value={effectiveFilter.inputObjectVersions ?? []}
                onChange={(event, newValue) => {
                  setFilter({
                    ...filter,
                    inputObjectVersions: newValue,
                  });
                }}
                options={objectVersionOptions}
              />
            </FormControl>
          </ListItem>
        </>
      }>
      <RunsTable loading={runs.loading} spans={runs.result} />
    </FilterLayoutTemplate>
  );
};
