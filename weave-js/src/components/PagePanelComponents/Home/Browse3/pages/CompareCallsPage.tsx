import {Box, FormControl, ListItem, TextField, Typography} from '@mui/material';
import {Autocomplete} from '@mui/material';
import _ from 'lodash';
import React, {useCallback, useMemo} from 'react';

import {parseRef} from '../../../../../react';
import {Call} from '../../Browse2/callTree';
import {objectRefDisplayName} from '../../Browse2/SmallRef';
import {StyledDataGrid} from '../StyledDataGrid';
import {
  getValueAtNestedKey,
  PivotRunsTable,
  PivotRunsView,
  WFHighLevelPivotSpec,
} from './CallsPage/PivotRunsTable';
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

  const objectVersionOptions = useMemo(() => {
    if (props.secondaryDim == null) {
      return {};
    }
    return Object.fromEntries(
      _.uniq(
        calls.map(call =>
          getValueAtNestedKey(call.rawCallSpan(), props.secondaryDim!)
        )
      )
        .filter(item => item != null)
        .map(item => {
          if (
            typeof item === 'string' &&
            item.startsWith('wandb-artifact://')
          ) {
            return [item, objectRefDisplayName(parseRef(item)).label];
          }
          return [item, item];
        })

      // .map(item => [item!.version(), item!])
    );
  }, [calls, props.secondaryDim]);

  // const opVersionOptions = useMemo(() => {
  //   return Object.fromEntries(
  //     calls[0].opVersion()
  //   )
  // }, []);
  // console.log(objectVersionOptions);

  const [selectedObjectVersion, setSelectedObjectVersion] = React.useState<
    string | null
  >(Object.keys(objectVersionOptions)?.[0] ?? null);

  const filteredCalls = useMemo(() => {
    return calls.filter(
      call =>
        getValueAtNestedKey(call.rawCallSpan(), props.secondaryDim!) ===
        selectedObjectVersion
    );
  }, [calls, props.secondaryDim, selectedObjectVersion]);

  const subOpVersionOptions = useMemo(() => {
    return Object.fromEntries(
      filteredCalls[0]
        .childCalls()
        .map(call => call.opVersion())
        .filter(opVersion => opVersion != null)
        .map(opVersion => [opVersion!.version(), opVersion!])
    );
  }, [filteredCalls]);

  const [selectedOpVersion, setSelectedOpVersion] = React.useState<
    string | null
  >(Object.keys(subOpVersionOptions)?.[0] ?? null);

  const subruns = useMemo(() => {
    return filteredCalls.flatMap(call =>
      call
        .childCalls()
        .filter(item => item.opVersion()?.version() === selectedOpVersion)
        .map(call => call.rawCallSpan())
    );
  }, [filteredCalls, selectedOpVersion]);
  // console.log(subruns);

  const getOptionLabel = useCallback(
    option => {
      // console.log(option, objectVersionOptions);
      const version = objectVersionOptions[option];
      if (version == null) {
        return option;
      }
      return version;
      // return version.op().name() + ':' + version.version().slice(0, 6);
    },
    [objectVersionOptions]
  );

  const getOpOptionLabel = useCallback(
    option => {
      // console.log(option, objectVersionOptions);
      const version = subOpVersionOptions[option];
      if (version == null) {
        return option;
      }
      return version;
      // return version.op().name() + ':' + version.version().slice(0, 6);
    },
    [subOpVersionOptions]
  );

  const [pivotSpec, setPivotSpec] = React.useState<
    Partial<WFHighLevelPivotSpec>
  >({
    colDim: props.primaryDim,
  });

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
                // p: 2,
                pb: 0,
                display: 'flex',
                flexDirection: 'column',
                height: '100%',
                maxHeight: '100%',
                overflow: 'auto',
              }}>
              <Box
                sx={{
                  flex: '0 0 auto',
                  width: '100%',
                  transition: 'width 0.1s ease-in-out',
                  display: 'flex',
                  flexDirection: 'row',
                  overflowX: 'auto',
                  overflowY: 'hidden',
                  alignItems: 'center',
                  gap: '8px',
                  p: 1,
                  '& li': {
                    padding: 0,
                    minWidth: '150px',
                  },
                  '& input, & label, & .MuiTypography-root': {
                    fontSize: '0.875rem',
                  },
                }}>
                <Typography
                  style={{
                    width: '38px',
                    textAlign: 'center',
                    flex: '0 0 auto',
                  }}>
                  Select
                </Typography>
                <ListItem>
                  <FormControl fullWidth>
                    <Autocomplete
                      size="small"
                      renderInput={params => (
                        <TextField {...params} label="Object" />
                      )}
                      value={selectedObjectVersion ?? null}
                      onChange={(event, newValue) => {
                        setSelectedObjectVersion(newValue);
                      }}
                      getOptionLabel={getOptionLabel}
                      options={Object.keys(objectVersionOptions)}
                    />
                  </FormControl>
                </ListItem>
                <ListItem>
                  <FormControl fullWidth>
                    <Autocomplete
                      size="small"
                      renderInput={params => (
                        <TextField {...params} label="Sub Op" />
                      )}
                      value={selectedObjectVersion ?? null}
                      onChange={(event, newValue) => {
                        setSelectedOpVersion(newValue);
                      }}
                      getOptionLabel={getOpOptionLabel}
                      options={Object.keys(subOpVersionOptions)}
                    />
                  </FormControl>
                </ListItem>
              </Box>
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
                  colDimAtLeafMode
                  pivotSpec={pivotSpec}
                  onPivotSpecChange={pivotSpec => {
                    console.log(pivotSpec);
                    setPivotSpec(pivotSpec);
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
