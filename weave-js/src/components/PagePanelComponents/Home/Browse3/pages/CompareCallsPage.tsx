import {Box, FormControl, ListItem, TextField} from '@mui/material';
import {Autocomplete} from '@mui/material';
import _ from 'lodash';
import React, {FC, useCallback, useEffect, useMemo, useState} from 'react';

import {
  constBoolean,
  constFunction,
  constString,
  opArray,
  opJoin,
  opPick,
  typedDict,
} from '../../../../../core';
import {parseRef, useNodeValue} from '../../../../../react';
import {Span} from '../../Browse2/callTree';
import {objectRefDisplayName} from '../../Browse2/SmallRef';
import {
  getValueAtNestedKey,
  PivotRunsView,
  WFHighLevelPivotSpec,
} from './CallsPage/PivotRunsTable';
import {SimplePageLayout} from './common/SimplePageLayout';
import {callsNode, spanToCallSchema} from './wfReactInterface/interface';

export const CompareCallsPage: FC<{
  entity: string;
  project: string;
  callIds?: string[];
  primaryDim?: string;
  secondaryDim?: string;
}> = props => {
  const [selectedOpVersionRef, setSelectedOpVersionRef] = useState<
    string | null
  >(null);

  const [selectedObjectVersionRef, setSelectedObjectVersionRef] = useState<
    string | null
  >(null);

  const {loading, result: subRuns} = useSubRunsFromWeaveQuery(
    props.entity,
    props.project,
    props.callIds,
    props.secondaryDim,
    selectedOpVersionRef,
    selectedObjectVersionRef
  );

  const childRunsFilteredToOpVersion = useMemo(() => {
    return subRuns.map(subRun => {
      return spanToCallSchema(props.entity, props.project, subRun.child);
    });
  }, [props.entity, props.project, subRuns]);

  const parentCallChildCallsNode = callsNode(props.entity, props.project, {
    parentIds: props.callIds ?? [],
  });
  const parentCallsValue = useNodeValue(parentCallChildCallsNode, {
    skip: !props.callIds,
  });

  const objectVersionOptions = useMemo(() => {
    if (
      props.secondaryDim == null ||
      parentCallsValue.loading ||
      parentCallsValue.result.length === 0
    ) {
      return {};
    }
    return Object.fromEntries(
      _.uniq(
        parentCallsValue.result.map((parent: Span) =>
          getValueAtNestedKey(parent, props.secondaryDim!)
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
    if (parentCallsValue.loading || parentCallsValue.result.length === 0) {
      return {};
    }
    const uniqueOpRefs = _.uniq(
      parentCallsValue.result.map((r: any) => r.name) as string[]
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

const useSubRunsFromWeaveQuery = (
  entity: string,
  project: string,
  parentCallIds: string[] | undefined,
  secondaryDim: string | undefined,
  selectedOpVersionRef: string | null,
  selectedObjectVersionRef: string | null
): {
  loading: boolean;
  result: Array<{
    parent: Span;
    child: Span;
  }>;
} => {
  const parentRunsNode = selectedObjectVersionRef
    ? callsNode(entity, project, {
        callIds: parentCallIds,
        inputObjectVersionRefs: [selectedObjectVersionRef],
      })
    : opArray({} as any);
  const childRunsNode = selectedOpVersionRef
    ? callsNode(entity, project, {
        opVersionRefs: [selectedOpVersionRef],
      })
    : opArray({} as any);
  const joinedRuns = opJoin({
    arr1: parentRunsNode,
    arr2: childRunsNode,
    join1Fn: constFunction({row: typedDict({span_id: 'string'})}, ({row}) => {
      return opPick({obj: row, key: constString('span_id')});
    }) as any,
    join2Fn: constFunction({row: typedDict({parent_id: 'string'})}, ({row}) => {
      return opPick({obj: row, key: constString('parent_id')});
    }) as any,
    alias1: constString('parent'),
    alias2: constString('child'),
    leftOuter: constBoolean(true),
    rightOuter: constBoolean(false),
  });
  const nodeValue = useNodeValue(joinedRuns, {
    skip: !selectedObjectVersionRef || !selectedOpVersionRef,
  });
  return useMemo(() => {
    return {
      loading: nodeValue.loading,
      result: nodeValue.result ?? [],
    };
  }, [nodeValue.loading, nodeValue.result]);
};
