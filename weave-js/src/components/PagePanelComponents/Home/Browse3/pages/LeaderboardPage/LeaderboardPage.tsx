import {Box} from '@mui/material';
import {MOON_250} from '@wandb/weave/common/css/color.styles';
import {useViewerInfo} from '@wandb/weave/common/hooks/useViewerInfo';
import {Button} from '@wandb/weave/components/Button';
import * as DropdownMenu from '@wandb/weave/components/DropdownMenu';
import {Icon} from '@wandb/weave/components/Icon';
import {Loading} from '@wandb/weave/components/Loading';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {parseRefMaybe} from '@wandb/weave/react';
import _ from 'lodash';
import React, {
  FC,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import ReactMarkdown from 'react-markdown';
import {useHistory} from 'react-router-dom';
import styled from 'styled-components';

import {useWeaveflowRouteContext, WeaveflowPeekContext} from '../../context';
import {NotFoundPanel} from '../../NotFoundPanel';
import {SmallRef} from '../../smallRef/SmallRef';
import {
  LeaderboardColumnOrderType,
  LeaderboardGrid,
} from '../../views/Leaderboard/LeaderboardGrid';
import {useSavedLeaderboardData} from '../../views/Leaderboard/query/hookAdapters';
import {
  GroupedLeaderboardData,
  LeaderboardValueRecord,
} from '../../views/Leaderboard/query/leaderboardQuery';
import {LeaderboardObjectVal} from '../../views/Leaderboard/types/leaderboardConfigType';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {
  useBaseObjectInstances,
  useCreateBuiltinObjectInstance,
} from '../wfReactInterface/objectClassQuery';
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';
import {LeaderboardConfigEditor} from './LeaderboardConfigEditor';

// Utility function to flatten all evaluation records from grouped data
const getAllEvaluationRecords = (
  data: GroupedLeaderboardData
): LeaderboardValueRecord[] => {
  const records: LeaderboardValueRecord[] = [];
  Object.values(data.modelGroups).forEach(modelGroup => {
    Object.values(modelGroup.datasetGroups).forEach(datasetGroup => {
      Object.values(datasetGroup.scorerGroups).forEach(scorerGroup => {
        Object.values(scorerGroup.metricPathGroups).forEach(metricPathGroup => {
          records.push(...metricPathGroup);
        });
      });
    });
  });
  return records;
};

type LeaderboardPageProps = {
  entity: string;
  project: string;
  leaderboardName: string;
  openEditorOnMount?: boolean;
};

export const LeaderboardPage: React.FC<LeaderboardPageProps> = props => {
  const [name, setName] = useState(props.leaderboardName);
  const {isPeeking} = useContext(WeaveflowPeekContext);
  const {isEditor} = useIsEditor(props.entity);
  const [isEditing, setIsEditing] = useState(false);
  useEffect(() => {
    if (isEditor && props.openEditorOnMount) {
      setIsEditing(true);
    }
  }, [isEditor, props.openEditorOnMount]);
  return (
    <SimplePageLayout
      title={name}
      hideTabsIfSingle
      tabs={[
        {
          label: 'Leaderboard',
          content: (
            <LeaderboardPageContent
              {...props}
              setName={setName}
              isEditing={isEditing}
              setIsEditing={setIsEditing}
            />
          ),
        },
      ]}
      headerExtra={
        !isPeeking &&
        !isEditing &&
        isEditor && (
          <EditLeaderboardButton
            isEditing={isEditing}
            setIsEditing={setIsEditing}
          />
        )
      }
    />
  );
};

export const LeaderboardPageContent: React.FC<
  LeaderboardPageProps & {
    setName: (name: string) => void;
    isEditing: boolean;
    setIsEditing: (isEditing: boolean) => void;
  }
> = props => {
  const {entity, project} = props;
  const leaderboardInstances = useBaseObjectInstances('Leaderboard', {
    project_id: projectIdFromParts({entity, project}),
    filter: {object_ids: [props.leaderboardName], latest_only: true},
  });

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

  const leaderboardVal = leaderboardInstances.result[0].val;

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
  } & {
    leaderboardVal: LeaderboardObjectVal;
  }
> = props => {
  const updateLeaderboard = useUpdateLeaderboard(
    props.entity,
    props.project,
    props.leaderboardName
  );
  const history = useHistory();
  const {peekingRouter} = useWeaveflowRouteContext();
  const [leaderboardVal, setLeaderboardVal] = useState(props.leaderboardVal);
  const [workingLeaderboardValCopy, setWorkingLeaderboardValCopy] =
    useState(leaderboardVal);
  const [selectedEvaluations, setSelectedEvaluations] = useState<string[]>([]);

  useEffect(() => {
    props.setName(workingLeaderboardValCopy.name ?? '');
  }, [props, workingLeaderboardValCopy.name]);

  // Clear selections when editing mode changes
  useEffect(() => {
    if (props.isEditing) {
      setSelectedEvaluations([]);
    }
  }, [props.isEditing]);
  const {loading, data, evalData} = useSavedLeaderboardData(
    props.entity,
    props.project,
    workingLeaderboardValCopy.columns
  );
  const [saving, setSaving] = useState(false);
  const discardChanges = useCallback(() => {
    setWorkingLeaderboardValCopy(leaderboardVal);
    props.setIsEditing(false);
    setSelectedEvaluations([]);
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

  // Memoize expensive getAllEvaluationRecords
  const allRecords = useMemo(() => {
    if (!data) return [];
    return getAllEvaluationRecords(data);
  }, [data]);

  // Calculate the number of selected models (rows) based on selectedEvaluations
  const selectedModelsCount = useMemo(() => {
    if (!data || selectedEvaluations.length === 0) {
      return 0;
    }

    // Get unique model names from selected evaluations
    const selectedModelNames = new Set(
      allRecords
        .filter(
          record =>
            record.sourceEvaluationCallId &&
            selectedEvaluations.includes(record.sourceEvaluationCallId)
        )
        .map(record => record.modelName)
    );

    return selectedModelNames.size;
  }, [data, allRecords, selectedEvaluations]);

  // Calculate available datasets based on selected evaluations
  const availableDatasets = useMemo(() => {
    if (!data || selectedEvaluations.length === 0) {
      return [];
    }

    // Get filtered records for selected evaluations
    const filteredRecords = allRecords.filter(
      record =>
        record.sourceEvaluationCallId &&
        selectedEvaluations.includes(record.sourceEvaluationCallId)
    );

    // Get unique dataset name+version combinations from selected evaluations
    const datasetsWithSelectedEvaluations = new Map();
    filteredRecords.forEach(record => {
      const key = `${record.datasetName}:${record.datasetVersion}`;
      if (!datasetsWithSelectedEvaluations.has(key)) {
        datasetsWithSelectedEvaluations.set(key, {
          name: record.datasetName,
          version: record.datasetVersion,
          fullName: `${record.datasetName}:${record.datasetVersion}`,
        });
      }
    });

    // Convert to array and sort for consistent ordering
    return Array.from(datasetsWithSelectedEvaluations.values())
      .sort((a, b) => a.fullName.localeCompare(b.fullName))
      .map(dataset => ({
        id: dataset.name, // Use just the name as ID for filtering (backward compatible)
        name: dataset.fullName, // Full name with version for display
        datasetName: dataset.name,
        datasetVersion: dataset.version,
      }));
  }, [data, allRecords, selectedEvaluations]);

  return (
    <Box display="flex" flexDirection="row" height="100%" flexGrow={1}>
      <Box
        flex={1}
        display="flex"
        flexDirection="column"
        height="100%"
        minWidth="50%">
        {selectedEvaluations.length > 0 && (
          <Tailwind>
            <div className="bg-gray-50 flex items-center gap-8 border-b border-moon-250 px-16 py-8">
              <Button
                variant="ghost"
                size="small"
                icon="close"
                onClick={() => setSelectedEvaluations([])}
                tooltip="Clear selection"
              />
              <div className="text-sm">
                {selectedModelsCount}{' '}
                {selectedModelsCount === 1 ? 'model' : 'models'} selected:
              </div>
              <CompareEvaluationsDropdownButton
                entity={props.entity}
                project={props.project}
                selectedEvaluations={selectedEvaluations}
                onDatasetSelect={datasetFullName => {
                  // Handle "Compare all evaluations" option
                  if (datasetFullName === '__all__') {
                    history.push(
                      peekingRouter.compareEvaluationsUri(
                        props.entity,
                        props.project,
                        selectedEvaluations,
                        null
                      )
                    );
                    return;
                  }

                  // For single evaluation, we can skip the complex filtering and just use the selected evaluation
                  if (selectedEvaluations.length === 1) {
                    history.push(
                      peekingRouter.compareEvaluationsUri(
                        props.entity,
                        props.project,
                        selectedEvaluations,
                        null
                      )
                    );
                    return;
                  }

                  // For multiple evaluations, filter to only include those for the selected dataset+version
                  // Parse the dataset name and version from the full name
                  const selectedDataset = availableDatasets.find(
                    d => d.name === datasetFullName
                  );
                  if (!selectedDataset) return;

                  const uniqueFilteredEvaluations = [
                    ...new Set(
                      allRecords
                        .filter(
                          record =>
                            record.sourceEvaluationCallId &&
                            selectedEvaluations.includes(
                              record.sourceEvaluationCallId
                            ) &&
                            record.datasetName ===
                              selectedDataset.datasetName &&
                            record.datasetVersion ===
                              selectedDataset.datasetVersion
                        )
                        .map(record => record.sourceEvaluationCallId)
                    ),
                  ];

                  if (uniqueFilteredEvaluations.length > 0) {
                    history.push(
                      peekingRouter.compareEvaluationsUri(
                        props.entity,
                        props.project,
                        uniqueFilteredEvaluations,
                        null
                      )
                    );
                  }
                }}
                availableDatasets={availableDatasets}
                loading={loading}
                disabled={selectedEvaluations.length === 0}
              />
            </div>
          </Tailwind>
        )}
        {workingLeaderboardValCopy.description && (
          <Box
            display="flex"
            flexDirection="row"
            maxHeight="35%"
            width="100%"
            sx={{
              flex: '1 1 auto',
              alignItems: 'flex-start',
              padding: '12px 16px',
              gap: '12px',
              overflowY: 'auto',
            }}>
            <StyledReactMarkdown>
              {workingLeaderboardValCopy.description}
            </StyledReactMarkdown>
          </Box>
        )}
        <Box
          display="flex"
          flexDirection="row"
          overflow="hidden"
          sx={{
            flex: '1 1 auto',
          }}>
          <LeaderboardGrid
            entity={props.entity}
            project={props.project}
            loading={loading}
            data={data}
            columnOrder={columnOrder}
            selectedEvaluations={selectedEvaluations}
            onSelectedEvaluationsChange={setSelectedEvaluations}
            allRecords={allRecords}
          />
        </Box>
      </Box>
      {props.isEditing && (
        <Box
          flex={1}
          display="flex"
          flexDirection="column"
          height="100%"
          minWidth="50%"
          sx={{
            borderLeft: `1px solid ${MOON_250}`,
          }}>
          <LeaderboardConfigEditor
            entity={props.entity}
            project={props.project}
            saving={saving}
            isDirty={isDirty}
            leaderboardVal={workingLeaderboardValCopy}
            setWorkingCopy={setWorkingLeaderboardValCopy}
            discardChanges={discardChanges}
            commitChanges={commitChanges}
          />
        </Box>
      )}
    </Box>
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

const EditLeaderboardButton: FC<{
  isEditing: boolean;
  setIsEditing: (isEditing: boolean) => void;
}> = ({isEditing, setIsEditing}) => {
  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        alignItems: 'center',
      }}>
      <Button
        className="mx-16"
        style={{
          marginLeft: '0px',
        }}
        size="medium"
        variant="secondary"
        onClick={() => setIsEditing(!isEditing)}
        icon={isEditing ? 'close' : 'pencil-edit'}>
        {isEditing ? 'Discard Changes' : 'Edit'}
      </Button>
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

// Dropdown button component for selecting datasets
const CompareEvaluationsDropdownButton: FC<{
  entity: string;
  project: string;
  selectedEvaluations: string[];
  onDatasetSelect: (datasetId: string) => void;
  availableDatasets?: Array<{
    id: string;
    name: string;
    datasetName: string;
    datasetVersion: string;
  }>;
  disabled?: boolean;
  loading?: boolean;
}> = ({
  entity,
  project,
  selectedEvaluations,
  onDatasetSelect,
  availableDatasets = [],
  disabled,
  loading,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const buttonText = selectedEvaluations.length === 1 ? 'View' : 'Compare';
  const isSingleEvaluation = selectedEvaluations.length === 1;

  // For single evaluation, directly navigate to first available dataset
  const handleSingleEvaluationClick = () => {
    if (availableDatasets.length > 0) {
      onDatasetSelect(availableDatasets[0].name);
    }
  };

  // If there's only one dataset, show a simple button instead of dropdown
  if (availableDatasets.length === 1) {
    return (
      <Box
        sx={{
          height: '100%',
          display: 'flex',
          alignItems: 'center',
        }}>
        <Button
          size="medium"
          variant="primary"
          disabled={disabled || loading}
          icon="chart-scatterplot"
          onClick={() => onDatasetSelect(availableDatasets[0].name)}
          tooltip="Compare evaluations">
          <div className="flex items-center gap-2">
            {loading ? <Loading size={16} /> : buttonText}
          </div>
        </Button>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        alignItems: 'center',
      }}>
      {isSingleEvaluation ? (
        // Direct button for single evaluation
        <Button
          size="medium"
          variant="primary"
          disabled={disabled || loading || availableDatasets.length === 0}
          icon="chart-scatterplot"
          onClick={handleSingleEvaluationClick}
          tooltip="View evaluation">
          <div className="flex items-center gap-2">
            {loading ? <Loading size={16} /> : buttonText}
          </div>
        </Button>
      ) : (
        // Dropdown for multiple evaluations
        <DropdownMenu.Root open={isOpen} onOpenChange={setIsOpen}>
          <DropdownMenu.Trigger asChild>
            <Button
              size="medium"
              variant="primary"
              disabled={disabled || loading}
              icon="chart-scatterplot"
              active={isOpen}
              tooltip="Select dataset to compare evaluations">
              <div className="flex items-center gap-2">
                {loading ? (
                  <Loading size={16} />
                ) : (
                  <>
                    {buttonText}
                    <Icon width={16} height={16} name="chevron-down" />
                  </>
                )}
              </div>
            </Button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content
              align="start"
              sideOffset={4}
              className="min-w-[200px]">
              {availableDatasets.length === 0 ? (
                <DropdownMenu.Item disabled>
                  <div className="flex items-center gap-2 text-moon-500">
                    <Icon name="info" width={16} height={16} />
                    No datasets available
                  </div>
                </DropdownMenu.Item>
              ) : (
                <>
                  {/* Decorative subheader */}
                  <DropdownMenu.Item disabled>
                    <div className="py-0.5 px-2 text-sm font-medium text-moon-500">
                      Compare evals in:
                    </div>
                  </DropdownMenu.Item>

                  {/* Dataset options */}
                  {availableDatasets.map(dataset => (
                    <DropdownMenu.Item
                      key={dataset.name}
                      onClick={() => {
                        onDatasetSelect(dataset.name);
                        setIsOpen(false);
                      }}>
                      <div className="flex items-center gap-2">
                        {(() => {
                          // Construct ref with version if we have it
                          const refString = dataset.name.startsWith('weave:///')
                            ? dataset.name
                            : `weave:///${entity}/${project}/object/${dataset.datasetName}:${dataset.datasetVersion}`;
                          const ref = parseRefMaybe(refString);
                          return ref ? (
                            <SmallRef
                              objRef={ref}
                              iconOnly={false}
                              noLink={true}
                            />
                          ) : (
                            <span>{dataset.name}</span>
                          );
                        })()}
                      </div>
                    </DropdownMenu.Item>
                  ))}
                  <DropdownMenu.Separator />
                  {/* Compare all evaluations option */}
                  <DropdownMenu.Item
                    onClick={() => {
                      onDatasetSelect('__all__');
                      setIsOpen(false);
                    }}>
                    <div className="flex items-center gap-2">
                      <Icon name="chart-scatterplot" width={16} height={16} />
                      <span className="ml-6 font-semibold">
                        Compare all evaluations
                      </span>
                    </div>
                  </DropdownMenu.Item>
                </>
              )}
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      )}
    </Box>
  );
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
