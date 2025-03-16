import React, {useCallback, useEffect, useMemo, useState} from 'react';

import {useGetTraceServerClientContext} from '../../wfReactInterface/traceServerClientContext';
import {fetchDatasets, fetchEvaluationResults, fetchEvaluations} from '../api';
import {
  Dataset,
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
}: ListDetailViewProps<T>) => {
  const [isCollapsed, setIsCollapsed] = React.useState(false);

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
          {items.map((item, index) => (
            <div
              key={index}
              style={{
                ...styles.listItemContainer,
                padding: isCollapsed ? '8px' : '8px 16px',
                backgroundColor:
                  item === selectedItem ? '#f5f5f5' : 'transparent',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.backgroundColor = '#fafafa';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.backgroundColor =
                  item === selectedItem ? '#f5f5f5' : 'transparent';
              }}
              onClick={() => onSelectItem(item)}>
              {isCollapsed ? (
                <div style={styles.collapsedIcon}>{getInitial(item)}</div>
              ) : (
                renderListItem(item)
              )}
            </div>
          ))}
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

// Cache management hook
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

// Custom hooks for data fetching and state management
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

const useEvaluations = (
  getClient: () => any,
  entity: string,
  project: string,
  selectedDataset: Dataset | null
) => {
  const [loading, setLoading] = useState(false);
  const cacheKey = `${entity}/${project}/evaluations`;
  const {updateCache, getCached} = useDataCache<Evaluation[]>(
    cacheKey,
    makeList
  );

  const fetchData = useCallback(async () => {
    if (!selectedDataset) {
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
  }, [getClient, entity, project, selectedDataset, updateCache, cacheKey]);

  useEffect(() => {
    if (!getCached(cacheKey).length) {
      fetchData();
    }
  }, [fetchData, getCached, cacheKey]);

  const evaluations = useMemo(() => {
    if (!selectedDataset) {
      return [];
    }
    const allEvaluations = getCached(cacheKey);
    return allEvaluations.filter(
      e => e.datasetRef === selectedDataset.objectRef
    );
  }, [getCached, cacheKey, selectedDataset]);

  return {
    evaluations,
    loading,
    refetch: fetchData,
  };
};

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

// Selection management hook
const useSelection = () => {
  const [selectedDataset, setSelectedDataset] = useState<Dataset | null>(null);
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
    resetEvaluation();
  }, [resetEvaluation]);

  const selectDataset = useCallback(
    (dataset: Dataset | null) => {
      setSelectedDataset(dataset);
      resetEvaluation();
      if (dataset) {
        setActiveTab('data-preview');
      }
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

// Main View Component
export const EvalStudioMainView: React.FC<EvalStudioMainViewProps> = ({
  entity,
  project,
}) => {
  const getClient = useGetTraceServerClientContext();

  const {
    selectedDataset,
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
    selectedDataset
  );
  const {evaluationRuns, loading: loadingRuns} = useEvaluationRuns(
    getClient,
    entity,
    project,
    selectedEvaluation
  );

  // Set initial selections when data is loaded
  useEffect(() => {
    if (datasets.length > 0 && !selectedDataset) {
      selectDataset(datasets[0]);
    }
  }, [datasets, selectedDataset, selectDataset]);

  useEffect(() => {
    if (evaluations.length > 0 && !selectedEvaluation) {
      selectEvaluation(evaluations[0]);
    }
  }, [evaluations, selectedEvaluation, selectEvaluation]);

  useEffect(() => {
    if (evaluationRuns.length > 0 && !selectedRun) {
      selectRun(evaluationRuns[0]);
    }
  }, [evaluationRuns, selectedRun, selectRun]);

  // Tab configuration
  const availableTabs = useMemo(() => {
    const tabs: TabConfig[] = [
      {
        id: 'data-preview',
        label: 'Data Preview',
        component: () => <div>Data Preview Content</div>,
        disabled: !selectedDataset,
      },
      {
        id: 'evaluation-details',
        label: 'Evaluation Details',
        component: () => <div>Evaluation Details</div>,
        disabled: !selectedEvaluation,
      },
      {
        id: 'model-details',
        label: 'Run Details',
        component: () => <div>Run Details</div>,
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
          ) : (
            <ModelReport results={[selectedRun!]} />
          ),
        disabled: !selectedRun,
      },
    ];

    return tabs;
  }, [selectedDataset, selectedEvaluation, selectedRun, loadingRuns]);

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

  // Render
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
              <div>
                <div style={{fontWeight: 500}}>{dataset.name}</div>
                <div style={{fontSize: '0.9em', color: '#666'}}>
                  N/A samples
                </div>
              </div>
            )}
            renderDetail={() => null}
          />
          <ListDetailView
            items={evaluations}
            selectedItem={selectedEvaluation}
            onSelectItem={selectEvaluation}
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
                    resetEvaluation();
                    setActiveTab('new-evaluation');
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
                    selectRun(null);
                    setActiveTab('new-model');
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
