import {Box, FormControl, ListItem, TextField} from '@mui/material';
import {Autocomplete} from '@mui/material';
import _ from 'lodash';
import React, {FC, useCallback, useEffect, useMemo, useState} from 'react';

import {parseRef} from '../../../../../react';
import {Call} from '../../Browse2/callTree';
import {useRuns} from '../../Browse2/callTreeHooks';
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

  const {
    parentRuns,
    parentRunsFilteredToInputSelection,
    childRunsOfFilteredParents,
    childRunsFilteredToOpVersion,
    loading,
  } = useSubRunsFromFastestEngine(
    props.entity,
    props.project,
    props.callIds,
    props.secondaryDim,
    selectedOpVersionRef,
    selectedObjectVersionRef
  );

  const objectVersionOptions = useMemo(() => {
    if (props.secondaryDim == null) {
      return {};
    }
    return Object.fromEntries(
      _.uniq(
        parentRuns.map(call => getValueAtNestedKey(call, props.secondaryDim!))
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
  }, [parentRuns, props.secondaryDim]);

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
    if (parentRunsFilteredToInputSelection.length === 0) {
      return {};
    }
    return Object.fromEntries(
      childRunsOfFilteredParents.map(call => {
        const opRef = call.name;
        const parsed = parseRef(opRef);
        return [
          opRef,
          parsed.artifactName + ':' + parsed.artifactVersion.slice(0, 6),
        ];
      })
    );
  }, [parentRunsFilteredToInputSelection.length, childRunsOfFilteredParents]);

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
        return option;
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
    if (loading) {
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
                  display:
                    childRunsFilteredToOpVersion.length === 0 ? 'none' : 'flex',
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

type SubRunsReturnType = {
  parentRuns: Call[];
  parentRunsFilteredToInputSelection: Call[];
  childRunsOfFilteredParents: Call[];
  childRunsFilteredToOpVersion: Call[];
  loading: boolean;
};

const useSubRunsFromWeaveQuery = (
  entity: string,
  project: string,
  parentCallIds: string[] | undefined,
  secondaryDim: string | undefined,
  selectedOpVersionRef: string | null,
  selectedObjectVersionRef: string | null
): SubRunsReturnType => {
  const parentRunsQuery = useRuns(
    {
      entityName: entity,
      projectName: project,
      streamName: 'stream',
    },
    {
      callIds: parentCallIds,
    }
  );
  const parentRuns = parentRunsQuery.result;

  const parentRunsFilteredToInputSelection = useMemo(() => {
    return parentRuns.filter(
      call =>
        secondaryDim &&
        getValueAtNestedKey(call, secondaryDim) === selectedObjectVersionRef
    );
  }, [parentRuns, secondaryDim, selectedObjectVersionRef]);

  const childCallsQuery = useRuns(
    {
      entityName: entity,
      projectName: project,
      streamName: 'stream',
    },
    {
      parentIds: parentRunsFilteredToInputSelection.map(call => call.span_id),
    }
  );

  const childRunsOfFilteredParents = childCallsQuery.result;

  const childRunsFilteredToOpVersion = useMemo(() => {
    return childRunsOfFilteredParents.filter(
      call => selectedOpVersionRef && call.name.includes(selectedOpVersionRef)
    );
  }, [childRunsOfFilteredParents, selectedOpVersionRef]);

  return {
    parentRuns,
    parentRunsFilteredToInputSelection,
    childRunsOfFilteredParents,
    childRunsFilteredToOpVersion,
    loading: parentRunsQuery.loading || childCallsQuery.loading,
  };
};

const useSubRunsFromORM = (
  entity: string,
  project: string,
  parentCallIds: string[] | undefined,
  secondaryDim: string | undefined,
  selectedOpVersionRef: string | null,
  selectedObjectVersionRef: string | null
): SubRunsReturnType => {
  const orm = useWeaveflowORMContext(entity, project);

  const parentCalls = useMemo(() => {
    return (
      (parentCallIds
        ?.map(cid => orm.projectConnection.call(cid))
        ?.filter(item => item != null) as WFCall[]) ?? []
    );
  }, [orm.projectConnection, parentCallIds]);

  const parentCallsFilteredToInputSelection = useMemo(() => {
    return parentCalls.filter(
      call =>
        secondaryDim &&
        getValueAtNestedKey(call.rawCallSpan(), secondaryDim) ===
          selectedObjectVersionRef
    );
  }, [parentCalls, secondaryDim, selectedObjectVersionRef]);

  const childCallsOfFilteredParents = useMemo(() => {
    return parentCallsFilteredToInputSelection.flatMap(call =>
      call.childCalls()
    );
  }, [parentCallsFilteredToInputSelection]);

  const childCallsFilteredToOpVersion = useMemo(() => {
    return childCallsOfFilteredParents.filter(
      item => item.opVersion()?.refUri() === selectedOpVersionRef
    );
  }, [childCallsOfFilteredParents, selectedOpVersionRef]);

  const parentRuns = useMemo(() => {
    return parentCalls.map(c => c.rawCallSpan());
  }, [parentCalls]);

  const parentRunsFilteredToInputSelection = useMemo(() => {
    return parentCallsFilteredToInputSelection.map(c => c.rawCallSpan());
  }, [parentCallsFilteredToInputSelection]);

  const childRunsOfFilteredParents = useMemo(() => {
    return childCallsOfFilteredParents.map(call => call.rawCallSpan());
  }, [childCallsOfFilteredParents]);

  const childRunsFilteredToOpVersion = useMemo(() => {
    return childCallsFilteredToOpVersion.map(call => call.rawCallSpan());
  }, [childCallsFilteredToOpVersion]);

  return {
    parentRuns,
    parentRunsFilteredToInputSelection,
    childRunsOfFilteredParents,
    childRunsFilteredToOpVersion,
    loading: parentRuns.length === 0,
  };
};

const useSubRunsFromFastestEngine = (
  entity: string,
  project: string,
  parentCallIds: string[] | undefined,
  secondaryDim: string | undefined,
  selectedOpVersionRef: string | null,
  selectedObjectVersionRef: string | null
): SubRunsReturnType => {
  const weaveQueryResults = useSubRunsFromWeaveQuery(
    entity,
    project,
    parentCallIds,
    secondaryDim,
    selectedOpVersionRef,
    selectedObjectVersionRef
  );

  const ormResults = useSubRunsFromORM(
    entity,
    project,
    parentCallIds,
    secondaryDim,
    selectedOpVersionRef,
    selectedObjectVersionRef
  );

  if (!weaveQueryResults.loading && !ormResults.loading) {
    if (weaveQueryResults.parentRuns.length !== ormResults.parentRuns.length) {
      console.error(
        'parentRuns mismatch',
        weaveQueryResults.parentRuns,
        ormResults.parentRuns
      );
    } else if (
      weaveQueryResults.parentRunsFilteredToInputSelection.length !==
      ormResults.parentRunsFilteredToInputSelection.length
    ) {
      console.error(
        'parentRunsFilteredToInputSelection mismatch',
        weaveQueryResults.parentRunsFilteredToInputSelection,
        ormResults.parentRunsFilteredToInputSelection
      );
    } else if (
      weaveQueryResults.childRunsOfFilteredParents.length !==
      ormResults.childRunsOfFilteredParents.length
    ) {
      console.error(
        'childRunsOfFilteredParents mismatch',
        weaveQueryResults.childRunsOfFilteredParents,
        ormResults.childRunsOfFilteredParents
      );
    } else if (
      weaveQueryResults.childRunsFilteredToOpVersion.length !==
      ormResults.childRunsFilteredToOpVersion.length
    ) {
      console.error(
        'childRunsFilteredToOpVersion mismatch',
        weaveQueryResults.childRunsFilteredToOpVersion,
        ormResults.childRunsFilteredToOpVersion
      );
    }
  }

  // We don't want to switch between ORM and weave query results
  // as they result in the table reloading. Just choose one for a
  // given render and stick with it.
  const [usingORM, setUsingORM] = useState<boolean | undefined>(undefined);

  return useMemo(() => {
    if (!ormResults.loading && usingORM !== false) {
      if (usingORM !== true) {
        setUsingORM(true);
      }
      return ormResults;
    } else {
      if (
        usingORM !== false &&
        weaveQueryResults.childRunsFilteredToOpVersion.length > 0
      ) {
        setUsingORM(false);
      }
      return weaveQueryResults;
    }
  }, [ormResults, usingORM, weaveQueryResults]);
};
