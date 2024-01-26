import {Box, FormControl, ListItem, TextField} from '@mui/material';
import {Autocomplete} from '@mui/material';
import React, {useMemo} from 'react';

import {Call} from '../../Browse2/callTree';
import {StyledDataGrid} from '../StyledDataGrid';
import {PivotRunsTable, PivotRunsView} from './CallsPage/PivotRunsTable';
import {SimplePageLayout} from './common/SimplePageLayout';
import {useWeaveflowORMContext} from './wfInterface/context';
import {WFCall} from './wfInterface/types';

export const CompareCallsPage: React.FC<{
  entity: string;
  project: string;
  callIds?: string[];
  primaryDim?: string;
  secondaryDim?: string;
}> = props => {
  // TODO: filter initial calls to only the correct dim
  // TODO: filter the subcalls to only the correct dim
  const orm = useWeaveflowORMContext(props.entity, props.project);
  const calls = useMemo(() => {
    return (
      (props.callIds
        ?.map(cid => orm.projectConnection.call(cid))
        ?.filter(item => item != null) as WFCall[]) ?? []
    );
  }, [orm.projectConnection, props.callIds]);
  const runs = useMemo(() => {
    return calls.map(call => call.rawCallSpan()).filter(item => item != null);
  }, [calls]);

  const subruns = useMemo(() => {
    return calls.flatMap(call =>
      call
        .childCalls()
        .filter(item => item.opVersion()?.version() === '860d744d3df917b00191')
        .map(call => call.rawCallSpan())
    );
  }, [calls]);
  console.log(subruns);

  if (!props.callIds || props.callIds.length < 2) {
    return <>Need more calls</>;
  }
  if (!props.primaryDim) {
    return <>Need a primary dimension</>;
  }
  if (!props.secondaryDim) {
    return <>Need a secondary dimension</>;
  }

  return (
    <SimplePageLayout
      title={`Compare`}
      hideTabsIfSingle
      tabs={[
        {
          label: '',
          content: (
            <Box
              sx={{
                p: 2,
                pb: 0,
                display: 'flex',
                flexDirection: 'column',
                height: '100%',
                maxHeight: '100%',
                overflow: 'auto',
                gap: '16px',
              }}>
              {/* <Box
                sx={{
                  display: 'flex',
                  flexDirection: 'row',
                  overflow: 'hidden',
                  flex: '0 0 auto',
                  height: '75px',
                }}>
                Comparing calls in
                <Autocomplete
                  size={'small'}
                  renderInput={params => (
                    <TextField {...params} label="TODO MAKE THIS WORK" />
                  )}
                  // value={effectiveFilter.parentId ?? null}
                  // onChange={(event, newValue) => {
                  //   setFilter({
                  //     ...filter,
                  //     parentId: newValue,
                  //   });
                  // }}
                  // getOptionLabel={option => {
                  //   return parentIdOptions[option] ?? option;
                  // }}
                  options={['a', 'b', 'c']}
                />
              </Box> */}
              {/* <Box sx={{minHeight: '300px', flex: '0 0 auto'}}>
                <PivotRunsTable
                  loading={false}
                  runs={runs}
                  entity={props.entity}
                  project={props.project}
                  pivotSpec={{
                    rowDim: props.primaryDim,
                    colDim: props.secondaryDim,
                  }}
                  extraDataGridProps={
                    {
                      hideFooter: true,
                    } as any
                  }
                />
              </Box> */}
              {/* <Box
                sx={{
                  display: 'flex',
                  flexDirection: 'row',
                  overflow: 'hidden',
                  flex: '0 0 auto',
                }}>
                Comparing child calls for op
                <Autocomplete
                  size={'small'}
                  renderInput={params => (
                    <TextField {...params} label="TODO MAKE THIS WORK" />
                  )}
                  // value={effectiveFilter.parentId ?? null}
                  // onChange={(event, newValue) => {
                  //   setFilter({
                  //     ...filter,
                  //     parentId: newValue,
                  //   });
                  // }}
                  // getOptionLabel={option => {
                  //   return parentIdOptions[option] ?? option;
                  // }}
                  options={['a', 'b', 'c']}
                />
              </Box> */}
              <Box sx={{minHeight: '300px', flex: '1 1 auto'}}>
                <PivotRunsView
                  loading={false}
                  runs={subruns}
                  entity={props.entity}
                  project={props.project}
                  pivotSpec={{
                    // TODO: remove hardcoding
                    rowDim: 'inputs.example', //props.secondaryDim,
                    colDim: props.primaryDim,
                  }}
                  onPivotSpecChange={pivotSpec => {
                    // TODO: Make this work
                  }}
                  // extraDataGridProps={
                  //   {
                  //     hideFooter: true,
                  //   } as any
                  // }
                />
              </Box>
            </Box>
          ),
        },
      ]}
    />
  );
};
