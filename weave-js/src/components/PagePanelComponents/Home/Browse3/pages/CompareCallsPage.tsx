import {Box, FormControl, ListItem, TextField} from '@mui/material';
import {Autocomplete} from '@mui/material';
import _ from 'lodash';
import React, {FC, useCallback, useEffect, useMemo, useState} from 'react';

import {parseRef} from '../../../../../react';
import {objectRefDisplayName} from '../../Browse2/SmallRef';
import {
  getValueAtNestedKey,
  PivotRunsView,
  WFHighLevelPivotSpec,
} from './CallsPage/PivotRunsTable';
import {SimplePageLayout} from './common/SimplePageLayout';
import {useWFHooks} from './wfReactInterface/context';
import {spanToCallSchema} from './wfReactInterface/utilities';

export const CompareCallsPage: FC<{
  entity: string;
  project: string;
  callIds?: string[];
  primaryDim?: string;
  secondaryDim?: string;
}> = props => {
  const {
    useCalls,
    derived: {useChildCallsForCompare},
  } = useWFHooks();
  const [selectedOpVersionRef, setSelectedOpVersionRef] = useState<
    string | null
  >(null);

  const [selectedObjectVersionRef, setSelectedObjectVersionRef] = useState<
    string | null
  >(null);

  const {loading, result: subRuns} = useChildCallsForCompare(
    props.entity,
    props.project,
    props.callIds ?? [],
    selectedOpVersionRef,
    selectedObjectVersionRef
  );

  const childRunsFilteredToOpVersion = useMemo(() => {
    return (subRuns ?? []).map(subRun => {
      return spanToCallSchema(props.entity, props.project, subRun.child);
    });
  }, [props.entity, props.project, subRuns]);

  const parentCallsValue = useCalls(
    props.entity,
    props.project,
    {
      parentIds: props.callIds ?? [],
    },
    undefined,
    {
      skip: !props.callIds,
    }
  );

  const objectVersionOptions = useMemo(() => {
    if (
      props.secondaryDim == null ||
      parentCallsValue.loading ||
      parentCallsValue.result == null ||
      parentCallsValue.result.length === 0
    ) {
      return {};
    }
    return Object.fromEntries(
      _.uniq(
        parentCallsValue.result.map(parent =>
          getValueAtNestedKey(parent.rawSpan, props.secondaryDim!)
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
  }, [parentCallsValue.loading, parentCallsValue.result, props.secondaryDim]);

  const initialSelectedObjectVersionRef =
    Object.keys(objectVersionOptions)?.[0];
  useEffect(() => {
    if (
      selectedObjectVersionRef == null &&
      initialSelectedObjectVersionRef != null
    ) {
      setSelectedObjectVersionRef(initialSelectedObjectVersionRef);
    }
  }, [initialSelectedObjectVersionRef, selectedObjectVersionRef]);

  const subOpVersionOptions = useMemo(() => {
    if (
      parentCallsValue.loading ||
      parentCallsValue.result == null ||
      parentCallsValue.result.length === 0
    ) {
      return {};
    }
    const uniqueOpRefs = _.uniq(
      parentCallsValue.result.map(r => r.rawSpan.name) as string[]
    );
    return Object.fromEntries(
      uniqueOpRefs.map(opRef => {
        if (opRef == null || !opRef.startsWith('wandb-artifact://')) {
          throw new Error('opVersionRef is null');
        }
        const parsed = parseRef(opRef);
        return [
          opRef,
          parsed.artifactName + ':' + parsed.artifactVersion.slice(0, 6),
        ];
      })
    );
  }, [parentCallsValue.loading, parentCallsValue.result]);

  const initialSelectedOpVersionRef = Object.keys(subOpVersionOptions)?.[0];

  useEffect(() => {
    if (selectedOpVersionRef == null && initialSelectedOpVersionRef != null) {
      setSelectedOpVersionRef(initialSelectedOpVersionRef);
    }
  }, [initialSelectedOpVersionRef, selectedOpVersionRef]);

  const getOptionLabel = useCallback(
    option => {
      const version = objectVersionOptions[option];
      if (version == null) {
        return 'loading...';
      }
      return version;
    },
    [objectVersionOptions]
  );

  const getOpOptionLabel = useCallback(
    option => {
      const version = subOpVersionOptions[option];
      if (version == null) {
        return option;
      }
      return version;
    },
    [subOpVersionOptions]
  );

  const [pivotSpec, setPivotSpec] = useState<Partial<WFHighLevelPivotSpec>>({
    colDim: props.primaryDim,
  });

  // Since we have a very constrained pivot, we can hide
  // the controls for now as there is no need to change them.
  // Punting on design
  const hideControls = true;

  const pageDetails = useMemo(() => {
    if (!loading) {
      if (!props.primaryDim) {
        return <>Need a primary dimension</>;
      }
      if (!props.secondaryDim) {
        return <>Need a secondary dimension</>;
      }
      if (!props.callIds || props.callIds.length < 1) {
        return <>Need more calls</>;
      }
    }

    return (
      <PivotRunsView
        loading={loading}
        runs={childRunsFilteredToOpVersion}
        entity={props.entity}
        project={props.project}
        colDimAtLeafMode
        pivotSpec={pivotSpec}
        onPivotSpecChange={newPivotSpec => {
          setPivotSpec(newPivotSpec);
        }}
        hideControls={hideControls}
      />
    );
  }, [
    hideControls,
    loading,
    pivotSpec,
    props.callIds,
    props.entity,
    props.primaryDim,
    props.project,
    props.secondaryDim,
    childRunsFilteredToOpVersion,
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
                <ListItem>
                  <FormControl fullWidth>
                    <Autocomplete
                      size="small"
                      renderInput={params => (
                        <TextField {...params} label="Input" />
                      )}
                      value={selectedObjectVersionRef ?? null}
                      onChange={(event, newValue) => {
                        setSelectedObjectVersionRef(newValue);
                      }}
                      getOptionLabel={getOptionLabel}
                      options={Object.keys(objectVersionOptions)}
                      disableClearable={selectedObjectVersionRef != null}
                    />
                  </FormControl>
                </ListItem>
                {!hideControls && (
                  <ListItem>
                    <FormControl fullWidth>
                      <Autocomplete
                        size="small"
                        renderInput={params => (
                          <TextField {...params} label="Sub Op" />
                        )}
                        value={selectedOpVersionRef ?? null}
                        onChange={(event, newValue) => {
                          setSelectedOpVersionRef(newValue);
                        }}
                        getOptionLabel={getOpOptionLabel}
                        options={Object.keys(subOpVersionOptions)}
                        disableClearable={selectedOpVersionRef != null}
                      />
                    </FormControl>
                  </ListItem>
                )}
              </Box>
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
