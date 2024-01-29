import {Box, FormControl, ListItem, TextField} from '@mui/material';
import {Autocomplete} from '@mui/material';
import _ from 'lodash';
import React, {useCallback, useEffect, useMemo} from 'react';

import {parseRef} from '../../../../../react';
import {objectRefDisplayName} from '../../Browse2/SmallRef';
import {
  getValueAtNestedKey,
  PivotRunsView,
  WFHighLevelPivotSpec,
} from './CallsPage/PivotRunsTable';
import {CenteredAnimatedLoader} from './common/Loader';
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
    );
  }, [calls, props.secondaryDim]);

  const [selectedObjectVersion, setSelectedObjectVersion] = React.useState<
    string | null
  >(null);

  const initialSelectedObjectVersion = Object.keys(objectVersionOptions)?.[0];
  useEffect(() => {
    if (selectedObjectVersion == null && initialSelectedObjectVersion != null) {
      setSelectedObjectVersion(initialSelectedObjectVersion);
    }
  }, [initialSelectedObjectVersion, selectedObjectVersion]);

  const callsFilteredToSecondaryDim = useMemo(() => {
    return calls.filter(
      call =>
        getValueAtNestedKey(call.rawCallSpan(), props.secondaryDim!) ===
        selectedObjectVersion
    );
  }, [calls, props.secondaryDim, selectedObjectVersion]);

  const subOpVersionOptions = useMemo(() => {
    if (callsFilteredToSecondaryDim.length === 0) {
      return {};
    }
    return Object.fromEntries(
      callsFilteredToSecondaryDim[0]
        .childCalls()
        .map(call => call.opVersion())
        .filter(opVersion => opVersion != null)
        .map(opVersion => [opVersion!.version(), opVersion!])
    );
  }, [callsFilteredToSecondaryDim]);

  const [selectedOpVersion, setSelectedOpVersion] = React.useState<
    string | null
  >(null);

  const initialSelectedOpVersion = Object.keys(subOpVersionOptions)?.[0];
  useEffect(() => {
    if (selectedOpVersion == null && initialSelectedOpVersion != null) {
      setSelectedOpVersion(initialSelectedOpVersion);
    }
  }, [initialSelectedOpVersion, selectedOpVersion]);

  const subcalls = useMemo(() => {
    return callsFilteredToSecondaryDim.flatMap(call =>
      call
        .childCalls()
        .filter(item => item.opVersion()?.version() === selectedOpVersion)
    );
  }, [callsFilteredToSecondaryDim, selectedOpVersion]);

  const subruns = useMemo(() => {
    return subcalls.map(call => call.rawCallSpan());
  }, [subcalls]);

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
      return version.op().name() + ':' + version.version().slice(0, 6);
    },
    [subOpVersionOptions]
  );

  const [pivotSpec, setPivotSpec] = React.useState<
    Partial<WFHighLevelPivotSpec>
  >({
    colDim: props.primaryDim,
  });

  // Since we have a very constrained pivot, we can hide
  // the controls for now as there is no need to change them.
  const showSubOpSelection = false;

  const pageDetails = useMemo(() => {
    if (calls.length === 0) {
      return <CenteredAnimatedLoader />;
    }
    if (!props.primaryDim) {
      return <>Need a primary dimension</>;
    }
    if (!props.secondaryDim) {
      return <>Need a secondary dimension</>;
    }
    if (!props.callIds || props.callIds.length < 1) {
      return <>Need more calls</>;
    }

    return (
      <PivotRunsView
        loading={false}
        runs={subruns}
        entity={props.entity}
        project={props.project}
        colDimAtLeafMode
        pivotSpec={pivotSpec}
        onPivotSpecChange={newPivotSpec => {
          setPivotSpec(newPivotSpec);
        }}
        // Since we have a very constrained pivot, we can hide
        // the controls for now as there is no need to change them.
        // Punting on design
        hideControls
        // extraDataGridProps={
        //   {
        //     hideFooter: true,
        //   } as any
        // }
      />
    );
  }, [
    calls.length,
    pivotSpec,
    props.callIds,
    props.entity,
    props.primaryDim,
    props.project,
    props.secondaryDim,
    subruns,
  ]);

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
                  display: calls.length === 0 ? 'none' : 'flex',
                  flexDirection: 'row',
                  overflowX: 'auto',
                  overflowY: 'hidden',
                  alignItems: 'center',
                  gap: '8px',
                  p: 1.5,
                  '& li': {
                    padding: 0,
                    minWidth: '150px',
                  },
                  '& input, & label, & .MuiTypography-root': {
                    fontSize: '0.875rem',
                  },
                }}>
                {/* <Typography
                  style={{
                    width: '38px',
                    textAlign: 'center',
                    flex: '0 0 auto',
                  }}>
                  Select
                </Typography> */}
                <ListItem>
                  <FormControl fullWidth>
                    <Autocomplete
                      size="small"
                      renderInput={params => (
                        <TextField {...params} label="Input" />
                      )}
                      value={selectedObjectVersion ?? null}
                      onChange={(event, newValue) => {
                        setSelectedObjectVersion(newValue);
                      }}
                      getOptionLabel={getOptionLabel}
                      options={Object.keys(objectVersionOptions)}
                      disableClearable={selectedObjectVersion != null}
                    />
                  </FormControl>
                </ListItem>
                {showSubOpSelection && (
                  <ListItem>
                    <FormControl fullWidth>
                      <Autocomplete
                        size="small"
                        renderInput={params => (
                          <TextField {...params} label="Sub Op" />
                        )}
                        value={selectedOpVersion ?? null}
                        onChange={(event, newValue) => {
                          setSelectedOpVersion(newValue);
                        }}
                        getOptionLabel={getOpOptionLabel}
                        options={Object.keys(subOpVersionOptions)}
                        disableClearable={selectedOpVersion != null}
                      />
                    </FormControl>
                  </ListItem>
                )}
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
                {pageDetails}
              </Box>
            </Box>
          ),
        },
      ]}
    />
  );
};
