import {Box, Alert} from '@mui/material';
import {MOON_250, MOON_100} from '@wandb/weave/common/css/color.styles';
import {useViewerInfo} from '@wandb/weave/common/hooks/useViewerInfo';
import {Button} from '@wandb/weave/components/Button';
import {Loading} from '@wandb/weave/components/Loading';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {WaveLoader} from '@wandb/weave/components/Loaders/WaveLoader';
import _ from 'lodash';
import React, {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';
import ReactMarkdown from 'react-markdown';
import {AutoSizer} from 'react-virtualized';
import styled from 'styled-components';

import {ResizableDrawer} from '../common/ResizableDrawer';

import {NotFoundPanel} from '../../NotFoundPanel';
import {
  LeaderboardColumnOrderType,
  LeaderboardGrid,
} from '../../views/Leaderboard/LeaderboardGrid';
import {useSavedLeaderboardData} from '../../views/Leaderboard/query/hookAdapters';
import {LeaderboardObjectVal} from '../../views/Leaderboard/types/leaderboardConfigType';
import {useShowDeleteButton} from '../common/DeleteModal';
import {SimplePageLayoutWithHeader} from '../common/SimplePageLayout';
import {DeleteObjectButtonWithModal} from '../ObjectsPage/ObjectDeleteButtons';
import {
  useBaseObjectInstances,
  useCreateBuiltinObjectInstance,
} from '../wfReactInterface/objectClassQuery';
import {
  convertTraceServerObjectVersionToSchema,
  projectIdFromParts,
} from '../wfReactInterface/tsDataModelHooks';
import {ObjectVersionSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {LeaderboardConfigEditor} from './LeaderboardConfigEditor';
import {
  CompareEvaluationsProvider,
  useCompareEvaluationsState,
} from '../CompareEvaluationsPage/compareEvaluationsContext';
import {CustomWeaveTypeProjectContext} from '../../typeViews/CustomWeaveTypeDispatcher';
import {STANDARD_PADDING} from '../CompareEvaluationsPage/ecpConstants';
import {VerticalBox} from '../CompareEvaluationsPage/Layout';
import {ExampleFilterSection} from '../CompareEvaluationsPage/sections/ExampleFilterSection/ExampleFilterSection';
import {ExampleCompareSectionTable} from '../CompareEvaluationsPage/sections/ExampleCompareSection/ExampleCompareSectionTable';
import {ExampleCompareSectionDetailGuarded} from '../CompareEvaluationsPage/sections/ExampleCompareSection/ExampleCompareSectionDetail';
import {EvaluationComparisonState} from '../CompareEvaluationsPage/ecpState';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {opVersionKeyToRefUri} from '../wfReactInterface/utilities';
import {EVALUATE_OP_NAME_POST_PYDANTIC} from '../common/heuristics';
import {ALL_VALUE} from '../../views/Leaderboard/types/leaderboardConfigType';
import {SummaryPlotsSection} from '../CompareEvaluationsPage/sections/SummaryPlotsSection/SummaryPlotsSection';
import {ScorecardSection} from '../CompareEvaluationsPage/sections/ScorecardSection/ScorecardSection';

type LeaderboardPageProps = {
  entity: string;
  project: string;
  leaderboardName: string;
  openEditorOnMount?: boolean;
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
  const [leaderboardObjectVersion, setLeaderboardObjectVersion] = useState<ObjectVersionSchema | null>(null);
  const [leaderboardVal, setLeaderboardVal] = useState<LeaderboardObjectVal | null>(null);
  const [selectedMetrics, setSelectedMetrics] = useState<Record<string, boolean> | null>(null);
  const [evaluationCallIds, setEvaluationCallIds] = useState<string[]>([]);
  
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
    const displayName = leaderboardObjectVersion.val?.name || leaderboardObjectVersion.objectId;
    
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
      title={displayTitle}
      hideTabsIfSingle={false}
      headerContent={undefined}
      tabs={[
        {
          label: 'Leaderboard',
          content: (
            <Box sx={{backgroundColor: MOON_100, height: '100%', width: '100%'}}>
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
          content: leaderboardVal && evaluationCallIds.length > 0 ? (
            <Box sx={{backgroundColor: MOON_100, height: '100%', width: '100%'}}>
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
            <Box sx={{padding: STANDARD_PADDING, backgroundColor: MOON_100, height: '100%'}}>
              <Alert severity="info">
                No evaluation data available. Make sure the leaderboard is configured with evaluations.
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
  }
> = props => {
  const {entity, project} = props;
  const leaderboardInstances = useBaseObjectInstances('Leaderboard', {
    project_id: projectIdFromParts({entity, project}),
    filter: {object_ids: [props.leaderboardName], latest_only: true},
  });

  // Calculate the object version if we have results
  const leaderboardObjectVersion = useMemo(() => {
    if (leaderboardInstances.result && leaderboardInstances.result.length === 1) {
      return convertTraceServerObjectVersionToSchema(leaderboardInstances.result[0]);
    }
    return null;
  }, [leaderboardInstances.result]);

  // Get the leaderboard value safely
  const leaderboardVal = useMemo(() => {
    if (leaderboardInstances.result && leaderboardInstances.result.length === 1) {
      return leaderboardInstances.result[0].val;
    }
    return null;
  }, [leaderboardInstances.result]);

  // Set the object version in the parent component
  useEffect(() => {
    if (props.setLeaderboardObjectVersion && leaderboardObjectVersion) {
      props.setLeaderboardObjectVersion(leaderboardObjectVersion);
    }
  }, [props.setLeaderboardObjectVersion, leaderboardObjectVersion]);

  // Extract unique evaluation refs from the leaderboard columns
  const evaluationRefs = useMemo(() => {
    if (leaderboardVal?.columns) {
      return [...new Set(
        leaderboardVal.columns
          .map(col => col.evaluation_object_ref)
          .filter(ref => ref != null)
      )];
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
    if (props.setLeaderboardVal && leaderboardVal) {
      props.setLeaderboardVal(leaderboardVal);
    }
  }, [props.setLeaderboardVal, leaderboardVal]);

  useEffect(() => {
    if (props.setEvaluationCallIds) {
      // Always set the evaluation call IDs, even if empty
      props.setEvaluationCallIds(evaluationCallIds);
    }
  }, [props.setEvaluationCallIds, evaluationCallIds]);

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
  } & {
    leaderboardVal: LeaderboardObjectVal;
    leaderboardObjectVersion: ObjectVersionSchema;
  }
> = props => {
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
  const [selectedMetrics, setSelectedMetrics] = useState<Record<string, boolean> | null>(null);
  
  // Extract evaluation refs and get call IDs for charts
  const evaluationRefs = useMemo(() => {
    return [...new Set(
      workingLeaderboardValCopy.columns
        .map(col => col.evaluation_object_ref)
        .filter(ref => ref != null)
    )];
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
          setLeaderboardVal(workingLeaderboardValCopy);
          setWorkingLeaderboardValCopy(workingLeaderboardValCopy);
          setSaving(false);
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
    if (!props.isEditing) return null;
    
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
            onClick={() => props.setIsEditing(false)}
            tooltip="Close editor"
          />
          <Box sx={{fontSize: '16px', fontWeight: 600}}>
            Edit Leaderboard
          </Box>
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
  }, [props.isEditing, props.setIsEditing, isFullscreen, handleToggleFullscreen]);

  return (
    <>
      <Box display="flex" flexDirection="column" height="100%" flexGrow={1}>
        {workingLeaderboardValCopy.description ? (
          <Box
            display="flex"
            flexDirection="row"
            maxHeight="35%"
            width="100%"
            sx={{
              flex: '1 1 auto',
              alignItems: 'flex-start',
              padding: '12px 96px 12px 16px',
              marginTop: '-8px',
              gap: '12px',
              overflowY: 'auto',
            }}>
            <StyledReactMarkdown>
              {workingLeaderboardValCopy.description}
            </StyledReactMarkdown>
          </Box>
        ) : (
          <Box height="38px" />
        )}
        <Box
          display="flex"
          flexDirection="column"
          overflow="auto"
          sx={{
            flex: '1 1 auto',
          }}>
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
                  <LeaderboardChartsSection />
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
        <LeaderboardResultsContent />
      </CustomWeaveTypeProjectContext.Provider>
    </CompareEvaluationsProvider>
  );
};

const LeaderboardResultsContent: React.FC = () => {
  const {state} = useCompareEvaluationsState();
  const showExamples =
    Object.keys(state.loadableComparisonResults.result?.resultRows ?? {})
      .length > 0;
  const resultsLoading = state.loadableComparisonResults.loading;

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
          The selected evaluations' datasets have 0 rows in common,
          try comparing evaluations with datasets that have at least
          one row in common.
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
          return <ResultExplorer state={state} height={height} />;
        }}
      </AutoSizer>
    </VerticalBox>
  );
};

const ResultExplorer: React.FC<{
  state: EvaluationComparisonState;
  height: number;
}> = ({state, height}) => {
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
const LeaderboardChartsSection: React.FC = () => {
  const {state, setSelectedMetrics} = useCompareEvaluationsState();
  
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
        setSelectedMetrics={setSelectedMetrics}
        initialExpanded={false}
      />
      <ScorecardSection 
        state={state} 
        initialExpanded={true}
      />
    </div>
  );
};
