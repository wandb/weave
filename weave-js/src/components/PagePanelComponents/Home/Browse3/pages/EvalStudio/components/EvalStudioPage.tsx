/**
 * EvalStudioPage Component
 *
 * A comprehensive UI for managing datasets, evaluations, and evaluation runs.
 * The component follows a three-panel layout where each panel represents a different
 * level in the hierarchy: Datasets -> Evaluations -> Evaluation Runs.
 *
 * Key features:
 * - Dataset version management
 * - Evaluation creation and monitoring
 * - Model evaluation runs and results
 * - Automatic selection of most recent evaluation context
 */

// External imports
import {parseRef} from '@wandb/weave/react';
import React, {useCallback, useEffect, useMemo, useState} from 'react';

// Internal imports - components
import {DatasetEditProvider} from '../../../datasets/DatasetEditorContext';
import {DatasetVersionPage} from '../../../datasets/DatasetVersionPage';
// Internal imports - utilities
import {flattenObjectPreservingWeaveTypes} from '../../../flattenObject';
import {CallPage} from '../../CallPage/CallPage';
import {CompareEvaluationsPageContent} from '../../CompareEvaluationsPage/CompareEvaluationsPage';
import {ObjectVersionPage} from '../../ObjectsPage/ObjectVersionPage';
import {useWFHooks} from '../../wfReactInterface/context';
import {useGetTraceServerClientContext} from '../../wfReactInterface/traceServerClientContext';
import {traceCallStatusCode} from '../../wfReactInterface/tsDataModelHooks';
// Internal imports - API and types
import {
  fetchDatasets,
  fetchDatasetVersions,
  fetchEvaluationResults,
  fetchEvaluations,
  fetchLastEvaluationContext,
} from '../api';
import {
  Dataset,
  DatasetVersion,
  EvaluationDefinition as Evaluation,
  EvaluationResult,
} from '../types';
import {NewDatasetForm} from './forms/NewDatasetForm';
import {NewEvaluationForm} from './forms/NewEvaluationForm';
import {NewModelForm} from './forms/NewModelForm';
import {ModelReport} from './ModelReport';

// Types
type TabId =
  | 'data-preview'
  | 'evaluation-details'
  | 'model-details'
  | 'model-report'
  | 'new-dataset'
  | 'new-evaluation'
  | 'new-model';

interface TabConfig {
  id: TabId;
  label: string;
  component: React.FC<any>;
  disabled?: boolean;
}

interface ListDetailViewProps<T> {
  items: T[];
  selectedItem: T | null;
  onSelectItem: (item: T | null) => void;
  renderListItem: (item: T) => React.ReactNode;
  renderDetail: () => React.ReactNode;
  sidebarLabel?: React.ReactNode;
  /** Function to get a unique key for an item. Used for selection comparison. */
  getItemKey?: (item: T) => string;
}

interface HeaderProps {
  tabs: TabConfig[];
  activeTab: TabId;
  onTabChange: (tabId: TabId) => void;
}

interface EvalStudioMainViewProps {
  entity: string;
  project: string;
}

// Reusable styles
const styles = {
  listItemContainer: {
    padding: '8px 16px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    height: '48px',
    boxSizing: 'border-box' as const,
  },
  collapsedIcon: {
    width: '32px',
    height: '32px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: '#eee',
    borderRadius: '4px',
    fontSize: '14px',
    fontWeight: 500,
    color: '#666',
  },
  addButton: {
    cursor: 'pointer',
    width: '24px',
    height: '24px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: '4px',
    color: '#00A4EF',
    fontSize: '1.2em',
    fontWeight: 'bold',
  },
  addButtonDisabled: {
    cursor: 'not-allowed',
    width: '24px',
    height: '24px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: '4px',
    color: '#ccc',
    fontSize: '1.2em',
    fontWeight: 'bold',
  },
};

// Helper functions
const getHeaderIcon = (label: string): string => {
  switch (label) {
    case 'Datasets':
      return '📊';
    case 'Evaluations':
      return '📋';
    case 'Evaluation Runs':
      return '🎯';
    default:
      return '📄';
  }
};

const getInitial = (item: any): string => {
  if (item.displayName?.startsWith('ML ')) {
    return item.displayName.split(' ')[1]?.charAt(0) || '';
  }
  return item.name?.charAt(0) || item.displayName?.charAt(0) || '#';
};

// Components
const ListDetailView = <T,>({
  items,
  selectedItem,
  onSelectItem,
  renderListItem,
  renderDetail,
  sidebarLabel,
  getItemKey = (item: T) => JSON.stringify(item),
}: ListDetailViewProps<T>) => {
  const [isCollapsed, setIsCollapsed] = React.useState(false);

  // Get the key of the selected item for comparison
  const selectedKey = selectedItem ? getItemKey(selectedItem) : null;

  return (
    <div style={{display: 'flex', height: '100%', position: 'relative'}}>
      <div
        style={{
          width: isCollapsed ? '48px' : '250px',
          borderRight: '1px solid #eee',
          transition: 'width 0.2s ease-in-out',
          display: 'flex',
          flexDirection: 'column',
        }}>
        {/* Header */}
        <div
          style={{
            padding: isCollapsed ? '8px' : '8px 16px',
            borderBottom: '1px solid #eee',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            height: '40px',
            boxSizing: 'border-box',
          }}>
          {isCollapsed ? (
            <div style={styles.collapsedIcon}>
              {getHeaderIcon(
                typeof sidebarLabel === 'string'
                  ? sidebarLabel
                  : (sidebarLabel as any)?.props?.children?.[0]?.props
                      ?.children || ''
              )}
            </div>
          ) : (
            sidebarLabel
          )}
        </div>

        {/* List */}
        <div style={{flex: 1, overflowY: 'auto'}}>
          {items.map((item, index) => {
            const itemKey = getItemKey(item);
            return (
              <div
                key={itemKey}
                style={{
                  ...styles.listItemContainer,
                  padding: isCollapsed ? '8px' : '8px 16px',
                  backgroundColor:
                    itemKey === selectedKey ? '#f5f5f5' : 'transparent',
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.backgroundColor = '#fafafa';
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.backgroundColor =
                    itemKey === selectedKey ? '#f5f5f5' : 'transparent';
                }}
                onClick={() => onSelectItem(item)}>
                {isCollapsed ? (
                  <div style={styles.collapsedIcon}>{getInitial(item)}</div>
                ) : (
                  renderListItem(item)
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Collapse/Expand Button */}
      <div
        style={{
          position: 'absolute',
          right: '-12px',
          top: '50%',
          transform: 'translateY(-50%)',
          width: '24px',
          height: '24px',
          background: 'white',
          border: '1px solid #eee',
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          zIndex: 1,
        }}
        onClick={() => setIsCollapsed(!isCollapsed)}>
        {isCollapsed ? '→' : '←'}
      </div>

      {/* Detail View */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}>
        {renderDetail()}
      </div>
    </div>
  );
};

const Header: React.FC<HeaderProps> = ({tabs, activeTab, onTabChange}) => (
  <div
    style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      borderBottom: '1px solid #eee',
      background: 'white',
      padding: '0 1rem',
      height: '56px',
    }}>
    <div
      style={{
        fontSize: '1.2em',
        fontWeight: 500,
        color: '#333',
      }}>
      Evaluation Studio
    </div>
    <div style={{display: 'flex', height: '100%'}}>
      {tabs.map(tab => (
        <div
          key={tab.id}
          onClick={() => !tab.disabled && onTabChange(tab.id)}
          style={{
            padding: '1rem',
            cursor: tab.disabled ? 'not-allowed' : 'pointer',
            color: tab.disabled
              ? '#ccc'
              : activeTab === tab.id
              ? '#00A4EF'
              : '#666',
            opacity: tab.disabled ? 0.7 : 1,
            borderBottom:
              activeTab === tab.id
                ? '2px solid #00A4EF'
                : '2px solid transparent',
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            boxSizing: 'border-box',
          }}>
          {tab.label}
        </div>
      ))}
    </div>
  </div>
);

/**
 * Cache management hook for storing and retrieving data.
 * Provides a simple key-value store with update and retrieval methods.
 */
const useDataCache = <T,>(key: string, getDefaultData: () => T) => {
  const [cache, setCache] = useState<{[key: string]: T}>({
    [key]: getDefaultData(),
  });

  const updateCache = useCallback((k: string, data: T) => {
    setCache(prev => ({...prev, [k]: data}));
  }, []);

  const getCached = useCallback(
    (k: string) => cache[k] || getDefaultData(),
    [cache, getDefaultData]
  );

  return {updateCache, getCached};
};

const makeList = () => {
  return [];
};

/**
 * Hook for managing datasets. Handles loading, caching, and refreshing dataset data.
 */
const useDatasets = (getClient: () => any, entity: string, project: string) => {
  const [loading, setLoading] = useState(true);
  const cacheKey = `${entity}/${project}/datasets`;
  const {updateCache, getCached} = useDataCache<Dataset[]>(cacheKey, makeList);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchDatasets(getClient(), entity, project);
      updateCache(cacheKey, data);
    } catch (error) {
      console.error('Error loading datasets:', error);
    }
    setLoading(false);
  }, [getClient, entity, project, updateCache, cacheKey]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const datasets = useMemo(() => getCached(cacheKey), [getCached, cacheKey]);

  return {
    datasets,
    loading,
    refetch: fetchData,
  };
};

/**
 * Hook for managing selection state across datasets, versions, evaluations, and runs.
 * Handles the relationships between these entities and their selection behaviors.
 */
const useSelection = () => {
  const [selectedDataset, setSelectedDataset] = useState<Dataset | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<DatasetVersion | null>(
    null
  );
  const [selectedEvaluation, setSelectedEvaluation] =
    useState<Evaluation | null>(null);
  const [selectedRun, setSelectedRun] = useState<EvaluationResult | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>('new-dataset');

  const resetEvaluation = useCallback(() => {
    setSelectedEvaluation(null);
    setSelectedRun(null);
  }, []);

  const resetAll = useCallback(() => {
    setSelectedDataset(null);
    setSelectedVersion(null);
    resetEvaluation();
  }, [resetEvaluation]);

  const selectDataset = useCallback(
    (dataset: Dataset | null) => {
      setSelectedDataset(dataset);
      // Don't reset version when selecting a dataset
      resetEvaluation();
      if (dataset) {
        setActiveTab('data-preview');
      }
    },
    [resetEvaluation]
  );

  // Update version selection to be the primary reference
  const selectVersion = useCallback(
    (version: DatasetVersion | null) => {
      setSelectedVersion(version);
      if (version) {
        // Update selectedDataset to match the version since DatasetVersion extends Dataset
        setSelectedDataset(version);
      }
      resetEvaluation();
    },
    [resetEvaluation]
  );

  const selectEvaluation = useCallback((evaluation: Evaluation | null) => {
    setSelectedEvaluation(evaluation);
    setSelectedRun(null);
    if (evaluation) {
      setActiveTab('evaluation-details');
    }
  }, []);

  const selectRun = useCallback((run: EvaluationResult | null) => {
    setSelectedRun(run);
    if (run) {
      setActiveTab('model-report');
    }
  }, []);

  return {
    selectedDataset,
    selectedVersion,
    setSelectedVersion: selectVersion,
    selectedEvaluation,
    selectedRun,
    activeTab,
    setActiveTab,
    selectDataset,
    selectEvaluation,
    selectRun,
    resetEvaluation,
    resetAll,
  };
};

/**
 * Hook for managing evaluations. Filters evaluations based on the selected dataset version.
 */
const useEvaluations = (
  getClient: () => any,
  entity: string,
  project: string,
  selectedVersion: DatasetVersion | null
) => {
  const [loading, setLoading] = useState(false);
  const cacheKey = `${entity}/${project}/evaluations`;
  const {updateCache, getCached} = useDataCache<Evaluation[]>(
    cacheKey,
    makeList
  );

  const fetchData = useCallback(async () => {
    if (!selectedVersion) {
      return;
    }
    setLoading(true);
    try {
      const data = await fetchEvaluations(getClient(), entity, project);
      updateCache(cacheKey, data);
    } catch (error) {
      console.error('Error loading evaluations:', error);
    }
    setLoading(false);
  }, [getClient, entity, project, selectedVersion, updateCache, cacheKey]);

  useEffect(() => {
    if (!getCached(cacheKey).length) {
      fetchData();
    }
  }, [fetchData, getCached, cacheKey]);

  const evaluations = useMemo(() => {
    if (!selectedVersion) {
      return [];
    }
    console.log('selectedVersion', selectedVersion.objectRef);
    const allEvaluations = getCached(cacheKey);
    return allEvaluations.filter(
      e => e.datasetRef === selectedVersion.objectRef
    );
  }, [getCached, cacheKey, selectedVersion]);

  return {
    evaluations,
    loading,
    refetch: fetchData,
  };
};

/**
 * Hook for managing evaluation runs. Loads and caches runs for the selected evaluation.
 */
const useEvaluationRuns = (
  getClient: () => any,
  entity: string,
  project: string,
  selectedEvaluation: Evaluation | null
) => {
  const [loading, setLoading] = useState(false);
  const cacheKey = selectedEvaluation
    ? `${entity}/${project}/evaluations/${selectedEvaluation.evaluationRef}/runs`
    : '';
  const {updateCache, getCached} = useDataCache<EvaluationResult[]>(
    cacheKey,
    makeList
  );

  const fetchData = useCallback(async () => {
    if (!selectedEvaluation || !cacheKey) {
      return;
    }
    setLoading(true);
    try {
      const data = await fetchEvaluationResults(
        getClient(),
        entity,
        project,
        selectedEvaluation.evaluationRef
      );
      updateCache(cacheKey, data);
    } catch (error) {
      console.error('Error loading evaluation runs:', error);
    }
    setLoading(false);
  }, [getClient, entity, project, selectedEvaluation, updateCache, cacheKey]);

  useEffect(() => {
    if (cacheKey && !getCached(cacheKey)?.length) {
      fetchData();
    }
  }, [fetchData, getCached, cacheKey]);

  const evaluationRuns = useMemo(() => {
    if (!cacheKey) {
      return [];
    }
    return getCached(cacheKey);
  }, [getCached, cacheKey]);

  return {
    evaluationRuns,
    loading,
    refetch: fetchData,
  };
};

/**
 * Hook for managing dataset versions. Handles loading, caching, and identifying the latest version.
 */
const useDatasetVersions = (
  getClient: () => any,
  entity: string,
  project: string,
  dataset: Dataset | null
) => {
  const cacheKey = dataset
    ? `${entity}/${project}/datasets/${dataset.name}/versions`
    : '';
  const {updateCache, getCached} = useDataCache<DatasetVersion[]>(
    cacheKey,
    makeList
  );
  const [loading, setLoading] = useState(false);

  const fetchVersions = useCallback(async () => {
    if (!dataset || !cacheKey) {
      return;
    }
    setLoading(true);
    try {
      const vs = await fetchDatasetVersions(
        getClient(),
        entity,
        project,
        dataset.name
      );
      updateCache(cacheKey, vs);
    } catch (error) {
      console.error('Error loading dataset versions:', error);
    }
    setLoading(false);
  }, [getClient, entity, project, dataset, updateCache, cacheKey]);

  useEffect(() => {
    if (cacheKey && !getCached(cacheKey).length) {
      fetchVersions();
    }
  }, [fetchVersions, getCached, cacheKey]);

  const versions = useMemo(() => {
    if (!cacheKey) {
      return [];
    }
    return getCached(cacheKey);
  }, [getCached, cacheKey]);

  // Get the latest version
  const latestVersion = useMemo(() => {
    if (!versions.length) {
      return null;
    }
    return versions.find(v => v.isLatest) || versions[0];
  }, [versions]);

  return {
    versions,
    latestVersion,
    loading,
    refetch: fetchVersions,
  };
};

// Dataset list item component with version selector
const DatasetListItem: React.FC<{
  dataset: Dataset;
  selectedVersion: DatasetVersion | null;
  onVersionSelect: (version: DatasetVersion) => void;
  entity: string;
  project: string;
}> = ({dataset, selectedVersion, onVersionSelect, entity, project}) => {
  const getClient = useGetTraceServerClientContext();
  const {versions, loading} = useDatasetVersions(
    getClient,
    entity,
    project,
    dataset
  );
  const [isOpen, setIsOpen] = useState(false);

  // Sort versions by version number, newest first
  const sortedVersions = useMemo(() => {
    return [...versions].sort((a, b) => b.version - a.version);
  }, [versions]);

  // Get the selected version's ref for comparison
  const selectedVersionRef = selectedVersion?.objectRef;

  return (
    <div style={{width: '100%'}}>
      <div style={{display: 'flex', flexDirection: 'column', gap: '2px'}}>
        <div style={{fontWeight: 500}}>{dataset.name}</div>
        <div
          style={{
            position: 'relative',
            fontSize: '0.85em',
            color: '#666',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            padding: '2px 6px',
            borderRadius: '4px',
            background: '#f5f5f5',
            width: 'fit-content',
          }}
          onClick={e => {
            e.stopPropagation();
            setIsOpen(!isOpen);
          }}
          onMouseEnter={e => {
            e.currentTarget.style.background = '#ebebeb';
          }}
          onMouseLeave={e => {
            e.currentTarget.style.background = '#f5f5f5';
          }}>
          {loading ? (
            'Loading...'
          ) : selectedVersion ? (
            <>
              <span style={{color: '#333'}}>v{selectedVersion.version}</span>
              {selectedVersion.isLatest && (
                <span style={{color: '#00A4EF', fontWeight: 500}}>latest</span>
              )}
              <span style={{fontSize: '0.8em', marginLeft: '2px'}}>▼</span>
            </>
          ) : (
            <span style={{color: '#666'}}>Select version ▼</span>
          )}
          {isOpen && (
            <div
              style={{
                position: 'absolute',
                top: 'calc(100% + 4px)',
                left: 0,
                background: 'white',
                border: '1px solid #eee',
                borderRadius: '6px',
                boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                zIndex: 1000,
                maxHeight: '200px',
                overflowY: 'auto',
                minWidth: '120px',
              }}>
              {sortedVersions.map(version => (
                <div
                  key={version.objectRef}
                  style={{
                    padding: '6px 12px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    backgroundColor:
                      version.objectRef === selectedVersionRef
                        ? '#f5f5f5'
                        : 'white',
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.backgroundColor = '#f0f0f0';
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.backgroundColor =
                      version.objectRef === selectedVersionRef
                        ? '#f5f5f5'
                        : 'white';
                  }}
                  onClick={e => {
                    e.stopPropagation();
                    onVersionSelect(version);
                    setIsOpen(false);
                  }}>
                  <span style={{color: '#333'}}>v{version.version}</span>
                  {version.isLatest && (
                    <span
                      style={{
                        color: '#00A4EF',
                        fontSize: '0.85em',
                        fontWeight: 500,
                      }}>
                      latest
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// Main View Component
export const EvalStudioMainView: React.FC<EvalStudioMainViewProps> = ({
  entity,
  project,
}) => {
  const getClient = useGetTraceServerClientContext();
  const [selectedMetrics, setSelectedMetrics] = useState<Record<
    string,
    boolean
  > | null>(null);
  const [lastRunContext, setLastRunContext] = useState<{
    datasetRefUri: string;
    evaluationRefUri: string;
    run: any;
  } | null>(null);

  const {
    selectedDataset,
    selectedVersion,
    setSelectedVersion,
    selectedEvaluation,
    selectedRun,
    activeTab,
    setActiveTab,
    selectDataset,
    selectEvaluation,
    selectRun,
    resetAll,
    resetEvaluation,
  } = useSelection();

  const {datasets, loading: loadingDatasets} = useDatasets(
    getClient,
    entity,
    project
  );
  const {evaluations, loading: loadingEvaluations} = useEvaluations(
    getClient,
    entity,
    project,
    selectedVersion
  );
  const {evaluationRuns, loading: loadingRuns} = useEvaluationRuns(
    getClient,
    entity,
    project,
    selectedEvaluation
  );

  // Step 1: Get the latest run info
  useEffect(() => {
    const loadLastRun = async () => {
      try {
        const context = await fetchLastEvaluationContext(
          getClient(),
          entity,
          project
        );
        if (context) {
          setLastRunContext(context);
        }
      } catch (error) {
        console.error('Error loading last run context:', error);
      }
    };
    loadLastRun();
  }, [getClient, entity, project]);

  // Step 2 & 3: Once datasets are loaded, select the one matching the last run
  useEffect(() => {
    if (!lastRunContext || loadingDatasets || !datasets.length) {
      return;
    }

    const ref = parseRef(lastRunContext.datasetRefUri);
    const datasetName = ref.artifactName;
    const dataset = datasets.find(d => d.name === datasetName);

    if (dataset) {
      // First select the dataset
      selectDataset(dataset);

      // Then load and select the correct version
      const loadAndSelectVersion = async () => {
        try {
          const versions = await fetchDatasetVersions(
            getClient(),
            entity,
            project,
            dataset.name
          );
          const matchingVersion = versions.find(
            v => v.objectRef === lastRunContext.datasetRefUri
          );
          if (matchingVersion) {
            setSelectedVersion(matchingVersion);
          }
        } catch (error) {
          console.error('Error loading dataset versions:', error);
        }
      };
      loadAndSelectVersion();
    } else {
      // Fallback to first dataset if no match
      selectDataset(datasets[0]);
    }
  }, [
    lastRunContext,
    loadingDatasets,
    datasets,
    selectDataset,
    getClient,
    entity,
    project,
    setSelectedVersion,
  ]);

  // Step 4 & 5: Once evaluations are loaded, select the one matching the last run
  useEffect(() => {
    if (!lastRunContext || loadingEvaluations || !evaluations.length) {
      return;
    }

    const matchingEvaluation = evaluations.find(
      e => e.evaluationRef === lastRunContext.evaluationRefUri
    );
    if (matchingEvaluation) {
      selectEvaluation(matchingEvaluation);
    }
  }, [lastRunContext, loadingEvaluations, evaluations, selectEvaluation]);

  // Step 6 & 7: Once runs are loaded, select the matching run
  useEffect(() => {
    if (!lastRunContext || loadingRuns) {
      return;
    }

    const run: EvaluationResult = {
      entity,
      project,
      callId: lastRunContext.run.id,
      evaluationRef: lastRunContext.evaluationRefUri,
      modelRef: lastRunContext.run.inputs.model,
      createdAt: new Date(lastRunContext.run.started_at),
      metrics: lastRunContext.run.output
        ? flattenObjectPreservingWeaveTypes(lastRunContext.run.output)
        : {},
      status: traceCallStatusCode(lastRunContext.run),
    };
    selectRun(run);
    setActiveTab('model-report');
  }, [lastRunContext, loadingRuns, entity, project, selectRun, setActiveTab]);

  const {useObjectVersion} = useWFHooks();
  const objectVersion = useObjectVersion({
    scheme: 'weave',
    entity,
    project,
    weaveKind: 'object',
    objectId: selectedVersion?.name ?? '',
    versionHash: selectedVersion?.digest ?? '',
    path: '',
  });

  // Tab configuration
  const availableTabs = useMemo(() => {
    const tabs: TabConfig[] = [
      {
        id: 'data-preview',
        label: 'Data Preview',
        component: () => (
          <div style={{height: '100%', width: '100%', overflow: 'auto'}}>
            {objectVersion.result && (
              <DatasetEditProvider>
                <DatasetVersionPage objectVersion={objectVersion.result} />
              </DatasetEditProvider>
            )}
          </div>
        ),
        disabled: !selectedDataset,
      },
      {
        id: 'evaluation-details',
        label: 'Evaluation Details',
        component: () => (
          <div style={{height: '100%', width: '100%', overflow: 'auto'}}>
            {selectedEvaluation ? (
              <ObjectVersionPage
                entity={entity}
                project={project}
                objectName={selectedEvaluation.objectId}
                version={selectedEvaluation.objectDigest}
                filePath={''}
              />
            ) : (
              <div>No evaluation selected</div>
            )}
          </div>
        ),
        disabled: !selectedEvaluation,
      },
      {
        id: 'model-details',
        label: 'Run Details',
        component: () => (
          <div style={{height: '100%', width: '100%', overflow: 'auto'}}>
            {selectedRun ? (
              <CallPage
                entity={entity}
                project={project}
                callId={selectedRun.callId}
              />
            ) : (
              <div>No run selected</div>
            )}
          </div>
        ),
        disabled: !selectedRun,
      },
      {
        id: 'model-report',
        label: 'Run Report',
        component: () =>
          loadingRuns ? (
            <div style={{padding: '1rem', textAlign: 'center', color: '#666'}}>
              Loading results...
            </div>
          ) : selectedRun ? (
            <CompareEvaluationsPageContent
              entity={entity}
              project={project}
              evaluationCallIds={[selectedRun.callId!]}
              onEvaluationCallIdsUpdate={() => {}}
              selectedMetrics={selectedMetrics}
              setSelectedMetrics={setSelectedMetrics}
            />
          ) : (
            <div>No run selected</div>
          ),
        disabled: !selectedRun,
      },
    ];

    return tabs;
  }, [
    selectedDataset,
    selectedEvaluation,
    selectedRun,
    objectVersion.result,
    loadingRuns,
    entity,
    project,
    selectedMetrics,
    setSelectedMetrics,
  ]);

  // Render helpers
  const renderDetailView = () => {
    const Component = availableTabs.find(t => t.id === activeTab)?.component;
    if (!Component) {
      return (
        <div style={{padding: '1rem', color: '#666', textAlign: 'center'}}>
          Select a tab to view content
        </div>
      );
    }
    return <Component />;
  };

  if (loadingDatasets) {
    return <div>Loading datasets...</div>;
  }

  return (
    <div style={{height: '100%', display: 'flex', flexDirection: 'column'}}>
      <Header
        tabs={availableTabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />
      <div style={{flex: 1, display: 'flex', overflow: 'hidden'}}>
        <div style={{display: 'flex', borderRight: '1px solid #eee'}}>
          <ListDetailView
            items={datasets}
            selectedItem={selectedDataset}
            onSelectItem={selectDataset}
            getItemKey={dataset => dataset.name}
            sidebarLabel={
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  width: '100%',
                }}>
                <span>Datasets</span>
                <div
                  onClick={e => {
                    e.stopPropagation();
                    resetAll();
                    setActiveTab('new-dataset');
                  }}
                  style={styles.addButton}
                  onMouseEnter={e => {
                    e.currentTarget.style.backgroundColor = '#f0f0f0';
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.backgroundColor = 'transparent';
                  }}>
                  +
                </div>
              </div>
            }
            renderListItem={dataset => (
              <DatasetListItem
                dataset={dataset}
                selectedVersion={selectedVersion}
                onVersionSelect={version => {
                  setSelectedVersion(version);
                }}
                entity={entity}
                project={project}
              />
            )}
            renderDetail={() => null}
          />
          <ListDetailView
            items={evaluations}
            selectedItem={selectedEvaluation}
            onSelectItem={selectEvaluation}
            getItemKey={evaluation => evaluation.evaluationRef}
            sidebarLabel={
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  width: '100%',
                }}>
                <span>Evaluations</span>
                <div
                  onClick={e => {
                    e.stopPropagation();
                    if (selectedVersion) {
                      resetEvaluation();
                      setActiveTab('new-evaluation');
                    }
                  }}
                  style={
                    selectedVersion
                      ? styles.addButton
                      : styles.addButtonDisabled
                  }
                  onMouseEnter={e => {
                    if (selectedVersion) {
                      e.currentTarget.style.backgroundColor = '#f0f0f0';
                    }
                  }}
                  onMouseLeave={e => {
                    if (selectedVersion) {
                      e.currentTarget.style.backgroundColor = 'transparent';
                    }
                  }}>
                  +
                </div>
              </div>
            }
            renderListItem={evaluation => (
              <div>
                <div style={{fontWeight: 500}}>{evaluation.displayName}</div>
                <div style={{fontSize: '0.9em', color: '#666'}}>
                  {evaluation.scorerRefs.length} scorer
                  {evaluation.scorerRefs.length !== 1 ? 's' : ''}
                </div>
              </div>
            )}
            renderDetail={() => null}
          />
          <ListDetailView
            items={evaluationRuns}
            selectedItem={selectedRun}
            onSelectItem={selectRun}
            getItemKey={run => run.callId}
            sidebarLabel={
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  width: '100%',
                }}>
                <span>Evaluation Runs</span>
                <div
                  onClick={e => {
                    e.stopPropagation();
                    if (selectedEvaluation) {
                      selectRun(null);
                      setActiveTab('new-model');
                    }
                  }}
                  style={
                    selectedEvaluation
                      ? styles.addButton
                      : styles.addButtonDisabled
                  }
                  onMouseEnter={e => {
                    if (selectedEvaluation) {
                      e.currentTarget.style.backgroundColor = '#f0f0f0';
                    }
                  }}
                  onMouseLeave={e => {
                    if (selectedEvaluation) {
                      e.currentTarget.style.backgroundColor = 'transparent';
                    }
                  }}>
                  +
                </div>
              </div>
            }
            renderListItem={run => (
              <div>
                <div style={{fontWeight: 500}}>
                  {run.modelRef ? run.modelRef.split('/').pop() : 'Unnamed Run'}
                </div>
                <div style={{fontSize: '0.9em', color: '#666'}}>
                  Status: {run.status}
                </div>
              </div>
            )}
            renderDetail={() => null}
          />
        </div>
        <div style={{flex: 1, overflow: 'auto'}}>
          {activeTab === 'new-dataset' && (
            <NewDatasetForm
              onSubmit={dataset => {
                selectDataset(dataset);
              }}
            />
          )}
          {activeTab === 'new-evaluation' && selectedDataset && (
            <NewEvaluationForm
              onSubmit={evaluation => {
                selectEvaluation(evaluation);
              }}
            />
          )}
          {activeTab === 'new-model' && selectedEvaluation && (
            <NewModelForm
              onSubmit={model => {
                // TODO: Implement creating new evaluation run
                setActiveTab('model-report');
              }}
            />
          )}
          {!['new-dataset', 'new-evaluation', 'new-model'].includes(
            activeTab
          ) && renderDetailView()}
        </div>
      </div>
    </div>
  );
};
