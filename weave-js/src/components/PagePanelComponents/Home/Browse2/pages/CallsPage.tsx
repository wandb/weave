import {OpenInNew} from '@mui/icons-material';
import {
  Autocomplete,
  Box,
  Checkbox,
  FormControl,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  TextField,
} from '@mui/material';
import React, {useEffect, useMemo, useState} from 'react';
import {useHistory} from 'react-router-dom';

import {CallFilter} from '../callTree';
import {useRunsWithFeedback} from '../callTreeHooks';
import {RunsTable} from '../RunsTable';
import {SimplePageLayout} from './common/SimplePageLayout';
import {useWeaveflowORMContext} from './interface/wf/context';
import {HackyOpCategory} from './interface/wf/types';
import {useWeaveflowRouteContext} from '../context';

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
}> = props => {
  const routerContext = useWeaveflowRouteContext();
  const history = useHistory();
  const orm = useWeaveflowORMContext();
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

  const [filter, setFilter] = useState<WFHighLevelCallFilter>(
    props.initialFilter ?? {}
  );
  useEffect(() => {
    if (props.initialFilter) {
      setFilter(props.initialFilter);
    }
  }, [props.initialFilter]);
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
    <Box
      sx={{
        flex: '1 1 auto',
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'row',
      }}>
      <Box
        sx={{
          flex: '0 0 auto',
          height: '100%',
          width: '240px',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'auto',
        }}>
        <Box
          sx={{
            pl: 2,
            pr: 1,
            height: 57,
            flex: '0 0 auto',
            borderBottom: '1px solid #e0e0e0',
            position: 'sticky',
            top: 0,
            zIndex: 1,
            backgroundColor: 'white',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}>
          Filters
          {Object.keys(props.frozenFilter ?? {}).length > 0 && (
            <IconButton
              size="small"
              onClick={() => {
                // TODO: use the route context
                history.push(
                  routerContext.callsUIUrl(
                    props.entity,
                    props.project,
                    effectiveFilter
                  )
                );
              }}>
              <OpenInNew />
            </IconButton>
          )}
        </Box>
        <List
          // dense
          sx={{width: '100%', maxWidth: 360, bgcolor: 'background.paper'}}>
          <ListItem
            secondaryAction={
              <Checkbox
                edge="end"
                checked={effectiveFilter.traceRootsOnly}
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
                // disablePortal
                // disableClearable
                // options={projects}
                // value={props.project}
                // onChange={(event, newValue) => {
                //   props.navigateToProject(newValue);
                // }}
                disabled={Object.keys(props.frozenFilter ?? {}).includes(
                  'opCategory'
                )}
                renderInput={params => (
                  <TextField {...params} label="Op Category" />
                )}
                value={effectiveFilter.opCategory}
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
                // disablePortal
                multiple
                disabled={Object.keys(props.frozenFilter ?? {}).includes(
                  'opVersions'
                )}
                // disableClearable
                // options={projects}
                value={effectiveFilter.opVersions ?? []}
                onChange={(event, newValue) => {
                  setFilter({
                    ...filter,
                    opVersions: newValue,
                  });
                }}
                // open={true}
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
                // disablePortal
                // disableClearable
                // options={projects}
                // value={props.project}
                // onChange={(event, newValue) => {
                //   props.navigateToProject(newValue);
                // }}
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
        </List>
      </Box>
      <RunsTable loading={runs.loading} spans={runs.result} />
    </Box>
  );
};
