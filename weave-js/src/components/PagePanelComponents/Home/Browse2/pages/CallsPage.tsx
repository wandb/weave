import {
  Autocomplete,
  Box,
  Checkbox,
  FormControl,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  TextField,
} from '@mui/material';
import React, {useMemo, useState} from 'react';

import {CallFilter} from '../callTree';
import {useRunsWithFeedback} from '../callTreeHooks';
import {RunsTable} from '../RunsTable';
import {SimplePageLayout} from './common/SimplePageLayout';

export type WFHighLevelCallFilter = {
  traceRootsOnly?: boolean;
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
  const [filter, setFilter] = useState<WFHighLevelCallFilter>(
    props.initialFilter ?? {}
  );
  const effectiveFilter = useMemo(() => {
    return {...filter, ...props.frozenFilter};
  }, [filter, props.frozenFilter]);
  const runs = useRunsWithFeedback(
    {
      entityName: props.entity,
      projectName: props.project,
      streamName: 'stream',
    },
    effectiveFilter
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
            p: 2,
            height: 57,
            flex: '0 0 auto',
            borderBottom: '1px solid #e0e0e0',
            position: 'sticky',
            top: 0,
            zIndex: 1,
            backgroundColor: 'white',
          }}>
          Filters
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
                renderInput={params => (
                  <TextField {...params} label="Op Category" />
                )}
                options={[]}
              />
            </FormControl>
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
                renderInput={params => (
                  <TextField {...params} label="Op Version" />
                )}
                options={[]}
              />
            </FormControl>
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
                renderInput={params => (
                  <TextField {...params} label="Consumes Objects" />
                )}
                options={[]}
              />
            </FormControl>
          </ListItem>
        </List>
      </Box>
      <RunsTable loading={runs.loading} spans={runs.result} />
    </Box>
  );
};
