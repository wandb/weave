import React, {useEffect, useState} from 'react';

import {
  fetchDatasets,
  fetchEvaluations,
  fetchModelResults,
  fetchModels,
} from '../mockData';
import {
  Dataset,
  EvaluationDefinition as Evaluation,
  EvaluationResult,
  Model,
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
    case 'Models':
      return '🤖';
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

// Main View Component
export const EvalStudioMainView: React.FC<EvalStudioMainViewProps> = ({
  entity,
  project,
}) => {
  // State
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<Dataset | null>(null);
  const [selectedEvaluation, setSelectedEvaluation] =
    useState<Evaluation | null>(null);
  const [selectedModel, setSelectedModel] = useState<Model | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>('new-dataset');

  const [evaluations, setEvaluations] = useState<Evaluation[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [modelResults, setModelResults] = useState<EvaluationResult[]>([]);

  const [loading, setLoading] = useState(true);
  const [loadingEvaluations, setLoadingEvaluations] = useState(false);
  const [loadingModels, setLoadingModels] = useState(false);
  const [loadingResults, setLoadingResults] = useState(false);

  // Data loading effects
  useEffect(() => {
    const loadDatasets = async () => {
      setLoading(true);
      try {
        const data = await fetchDatasets();
        setDatasets(data);
        if (data.length > 0 && !selectedDataset) {
          setSelectedDataset(data[0]);
          setActiveTab('data-preview');
        }
      } catch (error) {
        console.error('Error loading datasets:', error);
      }
      setLoading(false);
    };
    loadDatasets();
  }, [selectedDataset]);

  useEffect(() => {
    if (selectedDataset) {
      const loadEvaluations = async () => {
        setLoadingEvaluations(true);
        try {
          const data = await fetchEvaluations(selectedDataset.id);
          setEvaluations(data);
          if (data.length > 0 && !selectedEvaluation) {
            setSelectedEvaluation(data[0]);
            setActiveTab('evaluation-details');
          }
        } catch (error) {
          console.error('Error loading evaluations:', error);
        }
        setLoadingEvaluations(false);
      };
      loadEvaluations();
    } else {
      setEvaluations([]);
    }
  }, [selectedDataset, selectedEvaluation]);

  useEffect(() => {
    if (selectedEvaluation) {
      const loadModels = async () => {
        setLoadingModels(true);
        try {
          const data = await fetchModels(selectedEvaluation.evaluationRef);
          setModels(data);
          if (data.length > 0 && !selectedModel) {
            setSelectedModel(data[0]);
            setActiveTab('model-report');
          }
        } catch (error) {
          console.error('Error loading models:', error);
        }
        setLoadingModels(false);
      };
      loadModels();
    } else {
      setModels([]);
    }
  }, [selectedEvaluation, selectedModel]);

  useEffect(() => {
    if (selectedModel && selectedEvaluation) {
      const loadResults = async () => {
        setLoadingResults(true);
        try {
          const data = await fetchModelResults(
            selectedEvaluation.evaluationRef,
            selectedModel.id
          );
          setModelResults(data);
        } catch (error) {
          console.error('Error loading model results:', error);
        }
        setLoadingResults(false);
      };
      loadResults();
    } else {
      setModelResults([]);
    }
  }, [selectedModel, selectedEvaluation]);

  // Tab configuration
  const availableTabs = React.useMemo(() => {
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
        label: 'Model Details',
        component: () => <div>Model Details</div>,
        disabled: !selectedModel,
      },
      {
        id: 'model-report',
        label: 'Model Report',
        component: () =>
          loadingResults ? (
            <div style={{padding: '1rem', textAlign: 'center', color: '#666'}}>
              Loading results...
            </div>
          ) : (
            <ModelReport results={modelResults} />
          ),
        disabled: !selectedModel,
      },
    ];

    return tabs;
  }, [
    selectedDataset,
    selectedEvaluation,
    selectedModel,
    modelResults,
    loadingResults,
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

  if (loading) {
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
            onSelectItem={dataset => {
              setSelectedDataset(dataset);
              setSelectedEvaluation(null);
              setSelectedModel(null);
              if (dataset) {
                setActiveTab('data-preview');
              }
            }}
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
                    setSelectedDataset(null);
                    setSelectedEvaluation(null);
                    setSelectedModel(null);
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
                  {dataset.samples.length} samples
                </div>
              </div>
            )}
            renderDetail={() => null}
          />
          <ListDetailView
            items={evaluations}
            selectedItem={selectedEvaluation}
            onSelectItem={evaluation => {
              setSelectedEvaluation(evaluation);
              setSelectedModel(null);
              if (evaluation) {
                setActiveTab('evaluation-details');
              }
            }}
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
                    setSelectedEvaluation(null);
                    setSelectedModel(null);
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
            items={models}
            selectedItem={selectedModel}
            onSelectItem={model => {
              setSelectedModel(model);
              if (model) {
                setActiveTab('model-report');
              }
            }}
            sidebarLabel={
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  width: '100%',
                }}>
                <span>Models</span>
                <div
                  onClick={e => {
                    e.stopPropagation();
                    setSelectedModel(null);
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
            renderListItem={model => (
              <div>
                <div style={{fontWeight: 500}}>{model.name}</div>
                {model.description && (
                  <div style={{fontSize: '0.9em', color: '#666'}}>
                    {model.description}
                  </div>
                )}
              </div>
            )}
            renderDetail={() => null}
          />
        </div>
        <div style={{flex: 1, overflow: 'auto'}}>
          {activeTab === 'new-dataset' && (
            <NewDatasetForm
              onSubmit={dataset => {
                setDatasets([...datasets, dataset]);
                setSelectedDataset(dataset);
                setActiveTab('data-preview');
              }}
            />
          )}
          {activeTab === 'new-evaluation' && selectedDataset && (
            <NewEvaluationForm
              onSubmit={evaluation => {
                setSelectedEvaluation(evaluation);
                setActiveTab('evaluation-details');
              }}
            />
          )}
          {activeTab === 'new-model' && selectedEvaluation && (
            <NewModelForm
              onSubmit={model => {
                setSelectedModel(model);
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
