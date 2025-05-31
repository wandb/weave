import {Alert, Box} from '@mui/material';
import {MOON_100, MOON_250} from '@wandb/weave/common/css/color.styles';
import {useViewerInfo} from '@wandb/weave/common/hooks/useViewerInfo';
import {Button} from '@wandb/weave/components/Button';
import {WaveLoader} from '@wandb/weave/components/Loaders/WaveLoader';
import {Loading} from '@wandb/weave/components/Loading';
import _ from 'lodash';
import React, {useCallback, useEffect, useMemo, useState} from 'react';
import ReactMarkdown from 'react-markdown';
import {AutoSizer} from 'react-virtualized';
import styled from 'styled-components';

import {NotFoundPanel} from '../../NotFoundPanel';
import {CustomWeaveTypeProjectContext} from '../../typeViews/CustomWeaveTypeDispatcher';
import {
  LeaderboardColumnOrderType,
  LeaderboardGrid,
} from '../../views/Leaderboard/LeaderboardGrid';
import {useSavedLeaderboardData} from '../../views/Leaderboard/query/hookAdapters';
import {LeaderboardObjectVal} from '../../views/Leaderboard/types/leaderboardConfigType';
import {ALL_VALUE} from '../../views/Leaderboard/types/leaderboardConfigType';
import {useShowDeleteButton} from '../common/DeleteModal';
import {EVALUATE_OP_NAME_POST_PYDANTIC} from '../common/heuristics';
import {ResizableDrawer} from '../common/ResizableDrawer';
import {SimplePageLayoutWithHeader} from '../common/SimplePageLayout';
import {
  CompareEvaluationsProvider,
  useCompareEvaluationsState,
} from '../CompareEvaluationsPage/compareEvaluationsContext';
import {STANDARD_PADDING} from '../CompareEvaluationsPage/ecpConstants';
import {EvaluationComparisonState} from '../CompareEvaluationsPage/ecpState';
import {VerticalBox} from '../CompareEvaluationsPage/Layout';
import {ExampleCompareSectionDetailGuarded} from '../CompareEvaluationsPage/sections/ExampleCompareSection/ExampleCompareSectionDetail';
import {ExampleCompareSectionTable} from '../CompareEvaluationsPage/sections/ExampleCompareSection/ExampleCompareSectionTable';
import {ExampleFilterSection} from '../CompareEvaluationsPage/sections/ExampleFilterSection/ExampleFilterSection';
import {ScorecardSection} from '../CompareEvaluationsPage/sections/ScorecardSection/ScorecardSection';
import {SummaryPlotsSection} from '../CompareEvaluationsPage/sections/SummaryPlotsSection/SummaryPlotsSection';
import {DeleteObjectButtonWithModal} from '../ObjectsPage/ObjectDeleteButtons';
import {
  useBaseObjectInstances,
  useCreateBuiltinObjectInstance,
} from '../wfReactInterface/objectClassQuery';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {
  convertTraceServerObjectVersionToSchema,
  projectIdFromParts,
} from '../wfReactInterface/tsDataModelHooks';
import {opVersionKeyToRefUri} from '../wfReactInterface/utilities';
import {ObjectVersionSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {LeaderboardConfigEditor} from './LeaderboardConfigEditor';

type LeaderboardPageProps = {
  entity: string;
  project: string;
  leaderboardName: string;
  openEditorOnMount?: boolean;
};

// Hook to check for running evaluations
const useHasRunningEvaluations = (
  entity: string,
  project: string,
  data: any // The leaderboard data from useSavedLeaderboardData
): boolean => {
  const getClient = useGetTraceServerClientContext();
  const [hasRunning, setHasRunning] = useState<boolean>(false);

  useEffect(() => {
    if (!data || !data.modelGroups) {
      setHasRunning(false);
      return;
    }

    // Extract all unique evaluation call IDs from the data
    const callIds = new Set<string>();
    Object.values(data.modelGroups).forEach((modelGroup: any) => {
      Object.values(modelGroup.datasetGroups).forEach((datasetGroup: any) => {
        Object.values(datasetGroup.scorerGroups).forEach((scorerGroup: any) => {
          Object.values(scorerGroup.metricPathGroups).forEach(
            (records: any) => {
              records.forEach((record: any) => {
                if (record.sourceEvaluationCallId) {
                  callIds.add(record.sourceEvaluationCallId);
                }
              });
            }
          );
        });
      });
    });

    if (callIds.size === 0) {
      setHasRunning(false);
      return;
    }

    const client = getClient();
    const checkForRunningEvaluations = async () => {
      try {
        const callIdsArray = Array.from(callIds);
        const response = await client.callsStreamQuery({
          project_id: projectIdFromParts({entity, project}),
          filter: {
            call_ids: callIdsArray,
          },
          limit: callIdsArray.length,
        });

        // Check if any calls are still running
        const hasRunningCalls = response.calls.some(call => {
          const status =
            call.summary?.status || (call.ended_at ? 'success' : 'running');
          return status === 'running';
        });

        setHasRunning(hasRunningCalls);
      } catch (error) {
        console.error('Error checking for running evaluations:', error);
        setHasRunning(false);
      }
    };

    checkForRunningEvaluations();
  }, [entity, project, data, getClient]);

  return hasRunning;
};

// Hook to resolve evaluation refs to call IDs
const useEvaluationCallIds = (
  entity: string,
  project: string,
  evaluationRefs: string[]
): string[] => {
  const getClient = useGetTraceServerClientContext();
  const [callIds, setCallIds] = useState<string[]>([]);

  useEffect(() => {
    if (evaluationRefs.length === 0) {
      setCallIds([]);
      return;
    }

    const client = getClient();
    const fetchCallIds = async () => {
      try {
        // Construct the proper op name reference
        const evaluateOpRef = opVersionKeyToRefUri({
          entity,
          project,
          opId: EVALUATE_OP_NAME_POST_PYDANTIC,
          versionHash: ALL_VALUE,
        });

        // Query for evaluation.evaluate calls that use these evaluation objects
        // Based on the pattern in useMetrics, we need to look for calls
        // where the evaluation ref is in the input_refs
        const response = await client.callsStreamQuery({
          project_id: projectIdFromParts({entity, project}),
          filter: {
            op_names: [evaluateOpRef],
            input_refs: evaluationRefs, // This is the key - evaluation refs are in inputs
          },
          limit: 1000,
        });

        // Get all the call IDs from the matching calls
        const matchingCallIds = response.calls.map(call => call.id);

        setCallIds(matchingCallIds);
      } catch (error) {
        console.error('Error fetching evaluation call IDs:', error);
        setCallIds([]);
      }
    };

    fetchCallIds();
  }, [entity, project, evaluationRefs, getClient]);

  return callIds;
};

export const LeaderboardPage: React.FC<LeaderboardPageProps> = props => {
  const [name, setName] = useState(props.leaderboardName);
  const {isEditor} = useIsEditor(props.entity);
  const showDeleteButton = useShowDeleteButton(props.entity);
  const [isEditing, setIsEditing] = useState(false);
  const [leaderboardObjectVersion, setLeaderboardObjectVersion] =
    useState<ObjectVersionSchema | null>(null);
  const [leaderboardVal, setLeaderboardVal] =
    useState<LeaderboardObjectVal | null>(null);
  const [selectedMetrics, setSelectedMetrics] = useState<Record<
    string,
    boolean
  > | null>(null);
  const [evaluationCallIds, setEvaluationCallIds] = useState<string[]>([]);

  // Reset state when leaderboardName changes
  useEffect(() => {
    setName(props.leaderboardName);
    setLeaderboardObjectVersion(null);
    setLeaderboardVal(null);
    setSelectedMetrics(null);
    setEvaluationCallIds([]);
    setIsEditing(false);
  }, [props.leaderboardName]);

  useEffect(() => {
    if (isEditor && props.openEditorOnMount) {
      setIsEditing(true);
    }
  }, [isEditor, props.openEditorOnMount]);

  // Create header extra content with action buttons that will appear in the header bar
  const headerExtra = useMemo(() => {
    if (!leaderboardObjectVersion || isEditing) {
      return undefined;
    }

    // Use the actual display name from the leaderboard object, falling back to objectId
    const displayName =
      leaderboardObjectVersion.val?.name || leaderboardObjectVersion.objectId;

    return (
      <div style={{display: 'flex', gap: '8px', alignItems: 'center'}}>
        {isEditor && (
          <Button
            title="Edit leaderboard"
            tooltip="Edit leaderboard"
            variant="ghost"
            size="medium"
            icon="pencil-edit"
            onClick={() => setIsEditing(true)}
          />
        )}
        {showDeleteButton && (
          <DeleteObjectButtonWithModal
            objVersionSchema={leaderboardObjectVersion}
            overrideDisplayStr={displayName}
          />
        )}
      </div>
    );
  }, [leaderboardObjectVersion, isEditing, isEditor, showDeleteButton]);

  // Use consistent display name for title
  const displayTitle = leaderboardObjectVersion?.val?.name || name;

  return (
    <SimplePageLayoutWithHeader
      key={props.leaderboardName} // Force remount when leaderboard changes
      title={displayTitle}
      hideTabsIfSingle={false}
      headerContent={undefined}
      tabs={[
        {
          label: 'Leaderboard',
          content: (
            <Box
              sx={{backgroundColor: MOON_100, height: '100%', width: '100%'}}>
              <LeaderboardPageContent
                {...props}
                setName={setName}
                isEditing={isEditing}
                setIsEditing={setIsEditing}
                showDeleteButton={showDeleteButton}
                setLeaderboardObjectVersion={setLeaderboardObjectVersion}
                setLeaderboardVal={setLeaderboardVal}
                setEvaluationCallIds={setEvaluationCallIds}
              />
            </Box>
          ),
        },
        {
          label: 'Trace results',
          content:
            leaderboardVal && evaluationCallIds.length > 0 ? (
              <Box
                sx={{backgroundColor: MOON_100, height: '100%', width: '100%'}}>
                <LeaderboardResultsTab
                  entity={props.entity}
                  project={props.project}
                  leaderboardVal={leaderboardVal}
                  evaluationCallIds={evaluationCallIds}
                  selectedMetrics={selectedMetrics}
                  setSelectedMetrics={setSelectedMetrics}
                />
              </Box>
            ) : (
              <Box
                sx={{
                  padding: STANDARD_PADDING,
                  backgroundColor: MOON_100,
                  height: '100%',
                }}>
                <Alert severity="info">
                  No evaluation data available. Make sure the leaderboard is
                  configured with evaluations.
                </Alert>
              </Box>
            ),
        },
      ]}
      headerExtra={headerExtra}
    />
  );
};

export const LeaderboardPageContent: React.FC<
  LeaderboardPageProps & {
    setName: (name: string) => void;
    isEditing: boolean;
    setIsEditing: (isEditing: boolean) => void;
    showDeleteButton?: boolean;
    setLeaderboardObjectVersion?: (version: ObjectVersionSchema) => void;
    setLeaderboardVal?: (val: LeaderboardObjectVal) => void;
    setEvaluationCallIds?: (ids: string[]) => void;
    onLeaderboardSaved?: () => void;
  }
> = props => {
  const {
    entity,
    project,
    setLeaderboardObjectVersion,
    setLeaderboardVal,
    setEvaluationCallIds,
  } = props;
  const leaderboardInstances = useBaseObjectInstances('Leaderboard', {
    project_id: projectIdFromParts({entity, project}),
    filter: {object_ids: [props.leaderboardName], latest_only: true},
  });

  // Calculate the object version if we have results
  const leaderboardObjectVersion = useMemo(() => {
    if (
      leaderboardInstances.result &&
      leaderboardInstances.result.length === 1
    ) {
      return convertTraceServerObjectVersionToSchema(
        leaderboardInstances.result[0]
      );
    }
    return null;
  }, [leaderboardInstances.result]);

  // Get the leaderboard value safely
  const leaderboardVal = useMemo(() => {
    if (
      leaderboardInstances.result &&
      leaderboardInstances.result.length === 1
    ) {
      return leaderboardInstances.result[0].val;
    }
    return null;
  }, [leaderboardInstances.result]);

  // Set the object version in the parent component
  useEffect(() => {
    if (setLeaderboardObjectVersion && leaderboardObjectVersion) {
      setLeaderboardObjectVersion(leaderboardObjectVersion);
    }
  }, [setLeaderboardObjectVersion, leaderboardObjectVersion]);

  // Extract unique evaluation refs from the leaderboard columns
  const evaluationRefs = useMemo(() => {
    if (leaderboardVal?.columns) {
      return [
        ...new Set(
          leaderboardVal.columns
            .map(col => col.evaluation_object_ref)
            .filter(ref => ref != null)
        ),
      ];
    }
    return [];
  }, [leaderboardVal]);

  // Use hook to resolve evaluation refs to call IDs
  const evaluationCallIds = useEvaluationCallIds(
    props.entity,
    props.project,
    evaluationRefs
  );

  // Update parent component state
  useEffect(() => {
    if (setLeaderboardVal && leaderboardVal) {
      setLeaderboardVal(leaderboardVal);
    }
  }, [setLeaderboardVal, leaderboardVal]);

  useEffect(() => {
    if (setEvaluationCallIds) {
      // Always set the evaluation call IDs, even if empty
      setEvaluationCallIds(evaluationCallIds);
    }
  }, [setEvaluationCallIds, evaluationCallIds]);

  // Callback to handle when leaderboard is saved
  // Must be defined before any early returns to maintain consistent hook order
  const handleLeaderboardSaved = useCallback(() => {
    // Refetch the leaderboard instances to get the latest data
    leaderboardInstances.refetch();
    
    // Call parent callback if provided
    if (props.onLeaderboardSaved) {
      props.onLeaderboardSaved();
    }
  }, [leaderboardInstances, props]);

  if (leaderboardInstances.loading) {
    return <Loading centered />;
  }

  if (
    leaderboardInstances.result == null ||
    leaderboardInstances.result.length !== 1
  ) {
    return (
      <NotFoundPanel
        title={`Leaderboard (${props.leaderboardName}) not found`}
      />
    );
  }

  if (leaderboardVal == null) {
    return (
      <NotFoundPanel
        title={`Leaderboard (${props.leaderboardName}) had invalid data`}
      />
    );
  }

  return (
    <LeaderboardPageContentInner
      {...props}
      leaderboardVal={leaderboardVal}
      leaderboardObjectVersion={leaderboardObjectVersion!}
      setIsEditing={props.setIsEditing}
      setLeaderboardVal={setLeaderboardVal}
      onLeaderboardSaved={handleLeaderboardSaved}
    />
  );
};

const useUpdateLeaderboard = (
  entity: string,
  project: string,
  objectId: string
) => {
  const createLeaderboard = useCreateBuiltinObjectInstance('Leaderboard');

  const updateLeaderboard = async (leaderboardVal: LeaderboardObjectVal) => {
    return await createLeaderboard({
      obj: {
        project_id: projectIdFromParts({entity, project}),
        object_id: objectId,
        val: leaderboardVal,
      },
    });
  };

  return updateLeaderboard;
};

export const LeaderboardPageContentInner: React.FC<
  LeaderboardPageProps & {
    setName: (name: string) => void;
    isEditing: boolean;
    setIsEditing: (isEditing: boolean) => void;
    showDeleteButton?: boolean;
    setLeaderboardVal?: (val: LeaderboardObjectVal) => void;
    onLeaderboardSaved?: () => void;
  } & {
    leaderboardVal: LeaderboardObjectVal;
    leaderboardObjectVersion: ObjectVersionSchema;
  }
> = props => {
  const {isEditing, setIsEditing} = props;
  const updateLeaderboard = useUpdateLeaderboard(
    props.entity,
    props.project,
    props.leaderboardName
  );
  const [leaderboardVal, setLeaderboardVal] = useState(props.leaderboardVal);
  const [workingLeaderboardValCopy, setWorkingLeaderboardValCopy] =
    useState(leaderboardVal);
  const [drawerWidth, setDrawerWidth] = useState(800);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [selectedMetrics, setSelectedMetrics] = useState<Record<
    string,
    boolean
  > | null>(null);

  // Reset state when props.leaderboardVal changes (when a new leaderboard is selected)
  useEffect(() => {
    setLeaderboardVal(props.leaderboardVal);
    setWorkingLeaderboardValCopy(props.leaderboardVal);
    setSelectedMetrics(null);
  }, [props.leaderboardVal]);

  // Extract evaluation refs and get call IDs for charts
  const evaluationRefs = useMemo(() => {
    return [
      ...new Set(
        workingLeaderboardValCopy.columns
          .map(col => col.evaluation_object_ref)
          .filter(ref => ref != null)
      ),
    ];
  }, [workingLeaderboardValCopy.columns]);

  const evaluationCallIds = useEvaluationCallIds(
    props.entity,
    props.project,
    evaluationRefs
  );

  useEffect(() => {
    props.setName(workingLeaderboardValCopy.name ?? '');
  }, [props, workingLeaderboardValCopy.name]);
  const {loading, data, evalData} = useSavedLeaderboardData(
    props.entity,
    props.project,
    workingLeaderboardValCopy.columns
  );
  const hasRunningEvaluations = useHasRunningEvaluations(
    props.entity,
    props.project,
    data
  );
  const [saving, setSaving] = useState(false);
  const discardChanges = useCallback(() => {
    setWorkingLeaderboardValCopy(leaderboardVal);
    props.setIsEditing(false);
  }, [leaderboardVal, props]);
  const commitChanges = useCallback(() => {
    const mounted = true;
    setSaving(true);
    updateLeaderboard(workingLeaderboardValCopy)
      .then(() => {
        if (mounted) {
          props.setIsEditing(false);
          // Update the local state with the new values
          setLeaderboardVal(workingLeaderboardValCopy);
          setWorkingLeaderboardValCopy(workingLeaderboardValCopy);
          setSaving(false);
          
          // Update the parent component's state if the setter functions are available
          if (props.setLeaderboardVal) {
            props.setLeaderboardVal(workingLeaderboardValCopy);
          }
          if (props.setName) {
            props.setName(workingLeaderboardValCopy.name ?? '');
          }
          
          // Trigger the saved callback to refresh data
          if (props.onLeaderboardSaved) {
            // Small delay to ensure the server has updated
            setTimeout(() => {
              props.onLeaderboardSaved();
            }, 500);
          }
        }
      })
      .catch(e => {
        console.error(e);
        if (mounted) {
          setWorkingLeaderboardValCopy(leaderboardVal);
          setSaving(false);
        }
      });
  }, [leaderboardVal, props, updateLeaderboard, workingLeaderboardValCopy]);
  const isDirty = useMemo(() => {
    return !_.isEqual(leaderboardVal, workingLeaderboardValCopy);
  }, [leaderboardVal, workingLeaderboardValCopy]);
  const columnOrder = useMemo(() => {
    return workingLeaderboardValCopy.columns
      .map(col => {
        const datasetGroup = evalData[col.evaluation_object_ref]?.datasetGroup;
        const scorerGroup =
          evalData[col.evaluation_object_ref]?.scorers[col.scorer_name];
        const metricGroup = col.summary_metric_path;

        if (datasetGroup && scorerGroup && metricGroup) {
          return {
            datasetGroup,
            scorerGroup,
            metricGroup,
            minimize: col.should_minimize ?? false,
          };
        }
        return null;
      })
      .filter(c => c != null) as LeaderboardColumnOrderType;
  }, [workingLeaderboardValCopy, evalData]);

  const handleToggleFullscreen = useCallback(() => {
    setIsFullscreen(!isFullscreen);
  }, [isFullscreen]);

  const drawerHeaderContent = useMemo(() => {
    if (!isEditing) return null;

    return (
      <Box
        sx={{
          position: 'sticky',
          top: 0,
          zIndex: 20,
          backgroundColor: 'white',
          borderBottom: `1px solid ${MOON_250}`,
          padding: '16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
        <Box sx={{display: 'flex', alignItems: 'center', gap: 2}}>
          <Button
            variant="ghost"
            size="medium"
            icon="chevron-back"
            onClick={() => setIsEditing(false)}
            tooltip="Close editor"
          />
          <Box sx={{fontSize: '16px', fontWeight: 600}}>Edit Leaderboard</Box>
        </Box>
        <Button
          variant="ghost"
          size="medium"
          icon={isFullscreen ? 'minimize-mode' : 'full-screen-mode-expand'}
          onClick={handleToggleFullscreen}
          tooltip={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
        />
      </Box>
    );
  }, [isEditing, setIsEditing, isFullscreen, handleToggleFullscreen]);

  return (
    <>
      <Box
        display="flex"
        flexDirection="column"
        height="100%"
        flexGrow={1}
        overflow="auto">
        {workingLeaderboardValCopy.description ? (
          <Box
            display="block"
            width="100%"
            sx={{
              padding: '12px 16px 12px 16px',
              backgroundColor: 'white',
            }}>
            <StyledReactMarkdown>
              {workingLeaderboardValCopy.description}
            </StyledReactMarkdown>
          </Box>
        ) : (
          <Box height="0px" />
        )}
        <Box display="block">
          {/* Running Evaluations Banner */}
          {hasRunningEvaluations && (
            <Box
              sx={{
                padding: '12px 16px',
                backgroundColor: 'white',
                marginBottom: '1px',
              }}>
              <Alert severity="info" sx={{margin: 0}}>
                Some models have evaluations currently running. Results will
                update automatically when evaluations complete.
              </Alert>
            </Box>
          )}

          {/* Leaderboard Table */}
          <Box sx={{backgroundColor: 'white', paddingBottom: '4px'}}>
            <LeaderboardGrid
              entity={props.entity}
              project={props.project}
              loading={loading}
              data={data}
              columnOrder={columnOrder}
              hideFooter={true}
            />
          </Box>

          {/* Charts Section - Only show if we have evaluation call IDs */}
          {evaluationCallIds.length > 0 && (
            <Box sx={{marginBottom: '16px'}}>
              <CompareEvaluationsProvider
                entity={props.entity}
                project={props.project}
                initialEvaluationCallIds={evaluationCallIds}
                selectedMetrics={selectedMetrics}
                setSelectedMetrics={setSelectedMetrics}
                onEvaluationCallIdsUpdate={() => {}}
                setComparisonDimensions={() => {}}
                setSelectedInputDigest={() => {}}
                filterToLatestEvaluationsPerModel={true}>
                <CustomWeaveTypeProjectContext.Provider
                  value={{entity: props.entity, project: props.project}}>
                  <LeaderboardChartsSection
                    leaderboardColumns={workingLeaderboardValCopy.columns}
                  />
                </CustomWeaveTypeProjectContext.Provider>
              </CompareEvaluationsProvider>
            </Box>
          )}
        </Box>
      </Box>

      <ResizableDrawer
        open={props.isEditing}
        onClose={() => props.setIsEditing(false)}
        defaultWidth={isFullscreen ? window.innerWidth - 73 : drawerWidth}
        setWidth={width => !isFullscreen && setDrawerWidth(width)}
        headerContent={drawerHeaderContent}
        hideBackdrop
        disableScrollLock
        ModalProps={{
          keepMounted: true,
        }}>
        <Box
          sx={{
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
          }}>
          {/* Main content area */}
          <Box sx={{flex: 1, overflowY: 'auto', overflowX: 'hidden'}}>
            <LeaderboardConfigEditor
              entity={props.entity}
              project={props.project}
              leaderboardVal={workingLeaderboardValCopy}
              setWorkingCopy={setWorkingLeaderboardValCopy}
            />
          </Box>

          {/* Sticky footer with actions */}
          <Box
            sx={{
              borderTop: `1px solid ${MOON_250}`,
              backgroundColor: 'white',
              padding: '16px',
              display: 'flex',
              justifyContent: 'flex-end',
              gap: 2,
              position: 'sticky',
              bottom: 0,
              zIndex: 10,
            }}>
            <Button
              variant="secondary"
              onClick={discardChanges}
              disabled={saving}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={commitChanges}
              disabled={!isDirty || saving}>
              {saving ? 'Saving...' : 'Save Changes'}
            </Button>
          </Box>
        </Box>
      </ResizableDrawer>
    </>
  );
};

export const ToggleLeaderboardConfig: React.FC<{
  isOpen: boolean;
  onClick: () => void;
}> = ({isOpen, onClick}) => {
  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        alignItems: 'center',
      }}>
      <Button
        variant="ghost"
        size="small"
        onClick={onClick}
        tooltip={isOpen ? 'Discard Changes' : 'Configure Leaderboard'}
        icon={isOpen ? 'close' : 'settings'}
      />
    </Box>
  );
};

export const useIsEditor = (entity: string) => {
  const {loading: loadingUserInfo, userInfo} = useViewerInfo();
  return useMemo(() => {
    if (loadingUserInfo) {
      return {
        loading: true,
        isEditor: false,
      };
    }
    const viewer = userInfo ? userInfo.id : null;

    return {
      loading: false,
      isEditor: viewer && userInfo?.teams.includes(entity),
    };
  }, [entity, loadingUserInfo, userInfo]);
};

const StyledReactMarkdown = styled(ReactMarkdown)`
  > *:first-child {
    margin-top: 0;
  }
  h1 {
    font-weight: 600;
    font-size: 1.2rem;
  }
  h2 {
    font-weight: 600;
    font-size: 1.15rem;
  }
  h3 {
    font-weight: 600;
    font-size: 1.1rem;
  }
  h4 {
    font-weight: 600;
    font-size: 1.05rem;
  }
  h5 {
    font-weight: 600;
    font-size: 1rem;
  }
  h6 {
    font-weight: 600;
    font-size: 1rem;
  }
`;

// New component for the Results tab
const LeaderboardResultsTab: React.FC<{
  entity: string;
  project: string;
  leaderboardVal: LeaderboardObjectVal;
  evaluationCallIds: string[];
  selectedMetrics: Record<string, boolean> | null;
  setSelectedMetrics: (newModel: Record<string, boolean>) => void;
}> = props => {
  const [comparisonDimensions, setComparisonDimensions] =
    React.useState<ComparisonDimensionsType | null>(null);
  const [selectedInputDigest, setSelectedInputDigest] = React.useState<
    string | null
  >(null);

  // Reset local state when evaluation call IDs change
  useEffect(() => {
    setComparisonDimensions(null);
    setSelectedInputDigest(null);
  }, [props.evaluationCallIds]);

  const setComparisonDimensionsAndClearInputDigest = useCallback(
    (
      dimensions:
        | ComparisonDimensionsType
        | null
        | ((
            prev: ComparisonDimensionsType | null
          ) => ComparisonDimensionsType | null)
    ) => {
      if (typeof dimensions === 'function') {
        dimensions = dimensions(comparisonDimensions);
      }
      setComparisonDimensions(dimensions);
      setSelectedInputDigest(null);
    },
    [comparisonDimensions]
  );

  return (
    <CompareEvaluationsProvider
      entity={props.entity}
      project={props.project}
      initialEvaluationCallIds={props.evaluationCallIds}
      selectedMetrics={props.selectedMetrics}
      setSelectedMetrics={props.setSelectedMetrics}
      comparisonDimensions={comparisonDimensions ?? undefined}
      onEvaluationCallIdsUpdate={() => {}} // We don't update call IDs from the results tab
      setComparisonDimensions={setComparisonDimensionsAndClearInputDigest}
      selectedInputDigest={selectedInputDigest ?? undefined}
      setSelectedInputDigest={setSelectedInputDigest}
      filterToLatestEvaluationsPerModel={true}>
      <CustomWeaveTypeProjectContext.Provider
        value={{entity: props.entity, project: props.project}}>
        <LeaderboardResultsContent
          leaderboardColumns={props.leaderboardVal.columns}
        />
      </CustomWeaveTypeProjectContext.Provider>
    </CompareEvaluationsProvider>
  );
};

const LeaderboardResultsContent: React.FC<{
  leaderboardColumns: LeaderboardObjectVal['columns'];
}> = ({leaderboardColumns}) => {
  const {state} = useCompareEvaluationsState();
  const showExamples =
    Object.keys(state.loadableComparisonResults.result?.resultRows ?? {})
      .length > 0;
  const resultsLoading = state.loadableComparisonResults.loading;

  // Create the set of visible scorers based on leaderboard columns
  const visibleScorers = useMemo(() => {
    const scorers = new Set<string>();

    // Extract all scorer names from leaderboard columns and create scorer prefixes
    // This will show ALL metrics for any scorer that appears in the leaderboard
    leaderboardColumns.forEach(column => {
      if (column.scorer_name) {
        // Add the scorer prefix so we can match against any column that starts with "scores.{scorerName}"
        scorers.add(`scores.${column.scorer_name}`);
      }
    });

    return scorers;
  }, [leaderboardColumns]);

  if (resultsLoading) {
    return (
      <Box
        sx={{
          width: '100%',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '200px',
        }}>
        <WaveLoader size="small" />
      </Box>
    );
  }

  if (!showExamples) {
    return (
      <Box sx={{padding: STANDARD_PADDING}}>
        <Alert severity="info">
          The selected evaluations' datasets have 0 rows in common, try
          comparing evaluations with datasets that have at least one row in
          common.
        </Alert>
      </Box>
    );
  }

  return (
    <VerticalBox
      sx={{
        height: '100%',
        width: '100%',
        overflow: 'auto',
      }}>
      <AutoSizer style={{height: '100%', width: '100%'}}>
        {({height}) => {
          return (
            <ResultExplorer
              state={state}
              height={height}
              defaultHiddenScorerMetrics={visibleScorers}
            />
          );
        }}
      </AutoSizer>
    </VerticalBox>
  );
};

const ResultExplorer: React.FC<{
  state: EvaluationComparisonState;
  height: number;
  defaultHiddenScorerMetrics?: Set<string>;
}> = ({state, height, defaultHiddenScorerMetrics}) => {
  const [viewMode, setViewMode] = useState<'detail' | 'table' | 'split'>(
    'table'
  );
  const regressionFinderEnabled = state.evaluationCallIdsOrdered.length === 2;

  return (
    <VerticalBox
      sx={{
        height: '100%',
        width: '100%',
        overflow: 'auto',
      }}>
      {regressionFinderEnabled && <ExampleFilterSection state={state} />}
      <Box
        style={{
          display: 'flex',
          flexDirection: 'row',
          height: height,
          borderTop: '1px solid #e0e0e0',
        }}>
        <Box
          style={{
            flex: 1,
            width: '50%',
            display: viewMode !== 'detail' ? 'block' : 'none',
          }}>
          <ExampleCompareSectionTable
            state={state}
            shouldHighlightSelectedRow={viewMode === 'split'}
            onShowSplitView={() => setViewMode('split')}
            defaultHiddenScorerMetrics={defaultHiddenScorerMetrics}
          />
        </Box>

        <Box
          style={{
            flex: 1,
            width: '50%',
            borderLeft: '1px solid #e0e0e0',
            display: viewMode !== 'table' ? 'block' : 'none',
          }}>
          <ExampleCompareSectionDetailGuarded
            state={state}
            onClose={() => setViewMode('table')}
            onExpandToggle={() =>
              setViewMode(viewMode === 'detail' ? 'split' : 'detail')
            }
            isExpanded={viewMode === 'detail'}
          />
        </Box>
      </Box>
    </VerticalBox>
  );
};

type ComparisonDimensionsType = Array<{
  metricId: string;
  rangeSelection?: {[evalCallId: string]: {min: number; max: number}};
}>;

// Component to display charts below the leaderboard
const LeaderboardChartsSection: React.FC<{
  leaderboardColumns: LeaderboardObjectVal['columns'];
}> = ({leaderboardColumns}) => {
  const {state, setSelectedMetrics} = useCompareEvaluationsState();

  // Create a function to match actual metrics against leaderboard config
  const getMatchingMetrics = useCallback(
    (availableMetrics: string[]): Set<string> => {
      const allowedMetrics = new Set<string>();

      leaderboardColumns.forEach(column => {
        if (column.summary_metric_path) {
          const metricPath = column.summary_metric_path;

          // Look for exact matches in available metrics
          availableMetrics.forEach(availableMetric => {
            // Check if this metric matches our leaderboard column
            const isMatch =
              // Exact match for the metric path
              availableMetric === metricPath ||
              // Ends with the metric path (for scorer-prefixed metrics)
              availableMetric.endsWith(`.${metricPath}`) ||
              // For nested paths, check if it contains the metric path
              (metricPath.includes('.') &&
                availableMetric.includes(metricPath)) ||
              // Check if this is a scorer-only metric (no sub-path)
              (column.scorer_name && availableMetric === column.scorer_name) ||
              // Check if scorer name is part of the available metric
              (column.scorer_name &&
                availableMetric.startsWith(`${column.scorer_name}.`));

            if (isMatch) {
              allowedMetrics.add(availableMetric);
            }
          });
        }
      });

      return allowedMetrics;
    },
    [leaderboardColumns]
  );

  // Filter selectedMetrics to only include metrics shown in leaderboard
  const filteredSetSelectedMetrics = useCallback(
    (newMetrics: Record<string, boolean>) => {
      const availableMetricKeys = Object.keys(newMetrics);
      const allowedMetrics = getMatchingMetrics(availableMetricKeys);
      const filtered: Record<string, boolean> = {};

      // Only include metrics that match the leaderboard configuration
      // But allow toggling any metric that was already present
      Object.keys(newMetrics).forEach(metricKey => {
        if (allowedMetrics.has(metricKey)) {
          filtered[metricKey] = newMetrics[metricKey];
        } else if (
          state.selectedMetrics &&
          state.selectedMetrics[metricKey] !== undefined
        ) {
          // Allow toggling metrics that were already in the state (to fix toggle issue)
          const isInAllowed = getMatchingMetrics([metricKey]).has(metricKey);
          if (isInAllowed) {
            filtered[metricKey] = newMetrics[metricKey];
          }
        }
      });

      setSelectedMetrics(filtered);
    },
    [setSelectedMetrics, getMatchingMetrics, state.selectedMetrics]
  );

  // Override the initial selected metrics when state changes
  useEffect(() => {
    if (
      state.selectedMetrics &&
      Object.keys(state.selectedMetrics).length > 0
    ) {
      const availableMetricKeys = Object.keys(state.selectedMetrics);
      const allowedMetrics = getMatchingMetrics(availableMetricKeys);
      const filtered: Record<string, boolean> = {};

      // Filter existing metrics to only show those that match leaderboard
      Object.keys(state.selectedMetrics).forEach(metricKey => {
        if (allowedMetrics.has(metricKey)) {
          filtered[metricKey] = state.selectedMetrics![metricKey];
        }
      });

      // Only update if the filtered metrics are different
      if (!_.isEqual(filtered, state.selectedMetrics)) {
        setSelectedMetrics(filtered);
      }
    }
  }, [state.selectedMetrics, getMatchingMetrics, setSelectedMetrics]);

  if (state.loadableComparisonResults.loading) {
    return (
      <Box sx={{textAlign: 'center', py: 4}}>
        <WaveLoader size="small" />
      </Box>
    );
  }

  return (
    <div>
      <SummaryPlotsSection
        state={state}
        setSelectedMetrics={filteredSetSelectedMetrics}
        initialExpanded={true}
      />
      <ScorecardSection state={state} initialExpanded={false} />
    </div>
  );
};
