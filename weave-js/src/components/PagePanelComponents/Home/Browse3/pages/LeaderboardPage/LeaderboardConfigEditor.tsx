import DeleteIcon from '@mui/icons-material/Delete';
import {
  Box,
  Button,
  Checkbox,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Select,
  SelectChangeEvent,
  Tab,
  Tabs,
  Typography,
} from '@mui/material';
import IconButton from '@mui/material/IconButton';
import React, {useEffect, useMemo, useState} from 'react';

import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {
  fetchDatasetNamesForSpec,
  fetchDatasetVersionsForSpecAndName,
  fetchEvaluationNames,
  fetchEvaluationVersionsForName,
  fetchMetricPathsForSpec,
  fetchModelNamesForSpec,
  fetchModelVersionsForSpecAndName,
  fetchScorerNamesForSpec,
  fetchScorerVersionsForSpecAndName,
  VersionDetails,
} from './query/configEditorQuery';
import {
  ALL_VALUE,
  FilterAndGroupDatasetScorerMetricSpec,
  FilterAndGroupDatasetScorerSpec,
  FilterAndGroupDatasetSpec,
  FilterAndGroupSourceEvaluationSpec,
  FilterAndGroupSpec,
  LeaderboardConfigType,
} from './types/leaderboardConfigType';

export const LeaderboardConfigEditor: React.FC<{
  entity: string;
  project: string;
  config: LeaderboardConfigType;
  onCancel: () => void;
  onPersist: () => void;
  setConfig: (
    updater: (config: LeaderboardConfigType) => LeaderboardConfigType
  ) => void;
}> = ({entity, project, config, setConfig, onPersist, onCancel}) => {
  const [activeTab, setActiveTab] = useState(0);

  const handleSave = () => {
    onPersist();
  };

  const handleCancel = () => {
    onCancel();
  };

  const updateConfig = (
    updater: (spec: FilterAndGroupSpec) => FilterAndGroupSpec
  ) => {
    setConfig(prevConfig => ({
      ...prevConfig,
      config: {
        ...prevConfig.config,
        dataSelectionSpec: updater(prevConfig.config.dataSelectionSpec),
      },
    }));
  };

  const updateDescription = (newDescription: string) => {
    setConfig(prevConfig => ({
      ...prevConfig,
      config: {
        ...prevConfig.config,
        description: newDescription,
      },
    }));
  };

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  return (
    <Box
      sx={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        borderLeft: '1px solid #e0e0e0',
      }}>
      <Box sx={{borderBottom: 1, borderColor: 'divider'}}>
        <Tabs value={activeTab} onChange={handleTabChange}>
          <Tab label="Editor" />
          <Tab label="Description" />
          <Tab label="Config Preview" />
        </Tabs>
      </Box>

      <Box sx={{flex: 1, overflowY: 'auto', p: 2}}>
        {activeTab === 0 && (
          <ConfigEditor
            entity={entity}
            project={project}
            config={config.config.dataSelectionSpec}
            updateConfig={updateConfig}
          />
        )}
        {activeTab === 1 && (
          <DescriptionEditor
            description={config.config.description}
            updateDescription={updateDescription}
          />
        )}
        {activeTab === 2 && <ConfigPreview config={config} />}
      </Box>

      <Box
        sx={{
          display: 'flex',
          justifyContent: 'flex-end',
          pt: 1,
          pb: 1,
          pr: 1,
          borderTop: '1px solid #e0e0e0',
          height: '52px',
        }}>
        <Button variant="outlined" onClick={handleCancel} sx={{mr: 2}}>
          Cancel
        </Button>
        <Button variant="contained" onClick={handleSave}>
          Save
        </Button>
      </Box>
    </Box>
  );
};

const ConfigEditor: React.FC<{
  entity: string;
  project: string;
  config: FilterAndGroupSpec;
  updateConfig: (
    updater: (spec: FilterAndGroupSpec) => FilterAndGroupSpec
  ) => void;
}> = ({entity, project, config, updateConfig}) => {
  return (
    <>
      <SourceEvaluationsConfig
        entity={entity}
        project={project}
        sourceEvaluations={config.sourceEvaluations}
        updateConfig={updateConfig}
      />
      <DatasetsConfig
        entity={entity}
        project={project}
        parentSpec={{
          sourceEvaluations: config.sourceEvaluations,
          // Purposely exclude models and datasets
        }}
        datasets={config.datasets}
        updateConfig={updateConfig}
      />
      <ModelsConfig
        entity={entity}
        project={project}
        parentSpec={{
          sourceEvaluations: config.sourceEvaluations,
          datasets: config.datasets,
          // Purposely exclude models
        }}
        models={config.models}
        updateConfig={updateConfig}
      />
    </>
  );
};

const ConfigPreview: React.FC<{
  config: LeaderboardConfigType;
}> = ({config}) => {
  return (
    <Box>
      <pre
        style={{
          backgroundColor: '#f5f5f5',
          padding: '10px',
          borderRadius: '4px',
          overflowX: 'auto',
          maxHeight: 'calc(100vh - 200px)',
          whiteSpace: 'pre-wrap',
          wordWrap: 'break-word',
        }}>
        {JSON.stringify(config, null, 2)}
      </pre>
    </Box>
  );
};

const DescriptionEditor: React.FC<{
  description: string;
  updateDescription: (newDescription: string) => void;
}> = ({description, updateDescription}) => {
  const [localDescription, setLocalDescription] = useState(description);

  const debouncedUpdate = useMemo(
    () =>
      debounce((value: string) => {
        updateDescription(value);
      }, 300),
    [updateDescription]
  );

  useEffect(() => {
    setLocalDescription(description);
  }, [description]);

  const handleChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newValue = event.target.value;
    setLocalDescription(newValue);
    debouncedUpdate(newValue);
  };

  return (
    <Box sx={{height: 'calc(100vh - 200px)'}}>
      <textarea
        value={localDescription}
        onChange={handleChange}
        style={{
          width: '100%',
          height: '100%',
          fontFamily: 'monospace',
          fontSize: '14px',
          padding: '10px',
          border: '1px solid #ccc',
          borderRadius: '4px',
          resize: 'none',
          backgroundColor: '#f5f5f5',
          lineHeight: '1.5',
          whiteSpace: 'pre-wrap',
          overflowWrap: 'break-word',
        }}
        placeholder="Enter markdown description here..."
      />
    </Box>
  );
};

// Debounce function
function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null;
  return (...args: Parameters<T>) => {
    if (timeout) {
      clearTimeout(timeout);
    }
    timeout = setTimeout(() => func(...args), wait);
  };
}

const SourceEvaluationsConfig: React.FC<{
  entity: string;
  project: string;
  sourceEvaluations: FilterAndGroupSourceEvaluationSpec[] | undefined;
  updateConfig: (
    updater: (spec: FilterAndGroupSpec) => FilterAndGroupSpec
  ) => void;
}> = ({sourceEvaluations, updateConfig, entity, project}) => {
  const getTraceServerClient = useGetTraceServerClientContext();
  const [evaluationNames, setEvaluationNames] = useState<string[]>([]);

  useEffect(() => {
    fetchEvaluationNames(getTraceServerClient(), entity, project).then(
      setEvaluationNames
    );
  }, [entity, getTraceServerClient, project]);

  const handleAddSourceEvaluation = () => {
    updateConfig(spec => ({
      ...spec,
      sourceEvaluations: [
        ...(spec.sourceEvaluations || []),
        {name: ALL_VALUE, version: ALL_VALUE},
      ],
    }));
  };

  return (
    <Box sx={{mb: 3}}>
      <Typography variant="h6" gutterBottom>
        Source Evaluations
      </Typography>
      {sourceEvaluations?.map((evaluation, index) => (
        <SourceEvaluationItem
          key={index}
          entity={entity}
          project={project}
          evaluation={evaluation}
          evaluationNames={evaluationNames}
          updateConfig={updateConfig}
          index={index}
        />
      ))}
      <Button variant="outlined" onClick={handleAddSourceEvaluation}>
        Add Source Evaluation
      </Button>
    </Box>
  );
};

const SourceEvaluationItem: React.FC<{
  entity: string;
  project: string;
  evaluation: FilterAndGroupSourceEvaluationSpec;
  evaluationNames: string[];
  updateConfig: (
    updater: (spec: FilterAndGroupSpec) => FilterAndGroupSpec
  ) => void;
  index: number;
}> = ({entity, project, evaluation, evaluationNames, updateConfig, index}) => {
  const getTraceServerClient = useGetTraceServerClientContext();
  const [versions, setVersions] = useState<VersionDetails[]>([]);

  useEffect(() => {
    if (evaluation.name && evaluation.name !== ALL_VALUE) {
      fetchEvaluationVersionsForName(
        getTraceServerClient(),
        entity,
        project,
        evaluation.name
      ).then(setVersions);
    }
  }, [entity, evaluation.name, getTraceServerClient, project]);

  const handleNameChange = (event: SelectChangeEvent<string>) => {
    const newName = event.target.value as string;
    updateConfig(spec => ({
      ...spec,
      sourceEvaluations: spec.sourceEvaluations?.map((e, i) =>
        i === index ? {...e, name: newName, version: ALL_VALUE} : e
      ),
    }));
  };

  const handleVersionChange = (event: SelectChangeEvent<string>) => {
    const newVersion = event.target.value as string;
    updateConfig(spec => ({
      ...spec,
      sourceEvaluations: spec.sourceEvaluations?.map((e, i) =>
        i === index ? {...e, version: newVersion} : e
      ),
    }));
  };

  const handleDelete = () => {
    updateConfig(spec => ({
      ...spec,
      sourceEvaluations: spec.sourceEvaluations?.filter((_, i) => i !== index),
    }));
  };

  return (
    <Box sx={{display: 'flex', gap: 2, mb: 2, alignItems: 'center'}}>
      <FormControl fullWidth>
        <InputLabel>Name</InputLabel>
        <Select
          value={evaluation.name || ALL_VALUE}
          onChange={handleNameChange}>
          <MenuItem value={ALL_VALUE}>All</MenuItem>
          {evaluationNames.map(name => (
            <MenuItem key={name} value={name}>
              {name}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
      <FormControl fullWidth disabled={evaluation.name === ALL_VALUE}>
        <InputLabel>Version</InputLabel>
        <Select
          value={evaluation.version}
          onChange={handleVersionChange}
          disabled={evaluation.name === ALL_VALUE}>
          <MenuItem value={ALL_VALUE}>All</MenuItem>
          {versions.map(version => (
            <MenuItem key={version.digest} value={version.digest}>
              <VersionItem version={version} />
            </MenuItem>
          ))}
        </Select>
      </FormControl>
      <IconButton onClick={handleDelete} size="small">
        <DeleteIcon />
      </IconButton>
    </Box>
  );
};

const DatasetsConfig: React.FC<{
  entity: string;
  project: string;
  parentSpec: FilterAndGroupSpec;
  datasets: FilterAndGroupDatasetSpec[] | undefined;
  updateConfig: (
    updater: (spec: FilterAndGroupSpec) => FilterAndGroupSpec
  ) => void;
}> = ({datasets, updateConfig, entity, project, parentSpec}) => {
  const getTraceServerClient = useGetTraceServerClientContext();
  const [datasetNames, setDatasetNames] = useState<string[]>([]);

  useEffect(() => {
    fetchDatasetNamesForSpec(
      getTraceServerClient(),
      entity,
      project,
      parentSpec
    ).then(setDatasetNames);
  }, [entity, getTraceServerClient, project, parentSpec]);

  const handleAddDataset = () => {
    updateConfig(spec => ({
      ...spec,
      datasets: [
        ...(spec.datasets || []),
        {name: ALL_VALUE, version: ALL_VALUE, groupAllVersions: false},
      ],
    }));
  };

  return (
    <Box sx={{mb: 3}}>
      <Typography variant="h6" gutterBottom>
        Datasets
      </Typography>
      {datasets?.map((dataset, index) => (
        <DatasetItem
          key={index}
          entity={entity}
          project={project}
          parentSpec={{
            sourceEvaluations: parentSpec.sourceEvaluations,
            datasets: [
              {
                name: dataset.name,
                version: ALL_VALUE,
              },
            ],
          }}
          dataset={dataset}
          datasetNames={datasetNames}
          updateConfig={updateConfig}
          index={index}
        />
      ))}
      <Button variant="outlined" onClick={handleAddDataset}>
        Add Dataset
      </Button>
    </Box>
  );
};

const DatasetItem: React.FC<{
  entity: string;
  project: string;
  parentSpec: FilterAndGroupSpec;
  dataset: FilterAndGroupDatasetSpec;
  datasetNames: string[];
  updateConfig: (
    updater: (spec: FilterAndGroupSpec) => FilterAndGroupSpec
  ) => void;
  index: number;
}> = ({
  entity,
  project,
  parentSpec,
  dataset,
  datasetNames,
  updateConfig,
  index,
}) => {
  const getTraceServerClient = useGetTraceServerClientContext();
  const [versions, setVersions] = useState<VersionDetails[]>([]);
  const [scorerNames, setScorerNames] = useState<string[]>([]);

  useEffect(() => {
    if (dataset.name && dataset.name !== ALL_VALUE) {
      fetchDatasetVersionsForSpecAndName(
        getTraceServerClient(),
        entity,
        project,
        parentSpec,
        dataset.name
      ).then(setVersions);
    }
    fetchScorerNamesForSpec(getTraceServerClient(), entity, project, {
      ...parentSpec,
      datasets: [dataset],
    }).then(setScorerNames);
  }, [
    dataset.name,
    entity,
    getTraceServerClient,
    project,
    parentSpec,
    dataset,
  ]);

  const handleNameChange = (event: SelectChangeEvent<string>) => {
    const newName = event.target.value as string;
    updateConfig(spec => ({
      ...spec,
      datasets: spec.datasets?.map((d, i) =>
        i === index ? {...d, name: newName, version: ALL_VALUE} : d
      ),
    }));
  };

  const handleVersionChange = (event: SelectChangeEvent<string>) => {
    const newVersion = event.target.value as string;
    updateConfig(spec => ({
      ...spec,
      datasets: spec.datasets?.map((d, i) =>
        i === index ? {...d, version: newVersion} : d
      ),
    }));
  };

  const handleGroupAllVersionsChange = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const newGroupAllVersions = event.target.checked;
    updateConfig(spec => ({
      ...spec,
      datasets: spec.datasets?.map((d, i) =>
        i === index ? {...d, groupAllVersions: newGroupAllVersions} : d
      ),
    }));
  };

  const handleAddScorer = () => {
    updateConfig(spec => ({
      ...spec,
      datasets: spec.datasets?.map((d, i) =>
        i === index
          ? {
              ...d,
              scorers: [
                ...(d.scorers || []),
                {
                  name: ALL_VALUE,
                  version: ALL_VALUE,
                  groupAllVersions: false,
                  metrics: [],
                },
              ],
            }
          : d
      ),
    }));
  };

  const handleDelete = () => {
    updateConfig(spec => ({
      ...spec,
      datasets: spec.datasets?.filter((_, i) => i !== index),
    }));
  };

  return (
    <Box sx={{display: 'flex', flexDirection: 'column', gap: 2, mb: 2}}>
      <Box sx={{display: 'flex', gap: 2, alignItems: 'center'}}>
        <FormControl fullWidth>
          <InputLabel>Name</InputLabel>
          <Select value={dataset.name || ALL_VALUE} onChange={handleNameChange}>
            <MenuItem value={ALL_VALUE}>All</MenuItem>
            {datasetNames.map(name => (
              <MenuItem key={name} value={name}>
                {name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl fullWidth disabled={dataset.name === ALL_VALUE}>
          <InputLabel>Version</InputLabel>
          <Select
            value={dataset.version}
            onChange={handleVersionChange}
            disabled={dataset.name === ALL_VALUE}>
            <MenuItem value={ALL_VALUE}>All</MenuItem>
            {versions.map(version => (
              <MenuItem key={version.digest} value={version.digest}>
                <VersionItem version={version} />
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <IconButton onClick={handleDelete} size="small">
          <DeleteIcon />
        </IconButton>
      </Box>
      <FormControlLabel
        control={
          <Checkbox
            checked={dataset.groupAllVersions}
            onChange={handleGroupAllVersionsChange}
          />
        }
        label="Group All Versions"
      />
      <Typography variant="subtitle1">Scorers</Typography>
      {dataset.scorers?.map((scorer, scorerIndex) => (
        <ScorerItem
          key={scorerIndex}
          entity={entity}
          project={project}
          parentSpec={{
            sourceEvaluations: parentSpec.sourceEvaluations,
            datasets: [
              {
                ...(parentSpec.datasets?.[0] ?? {
                  name: ALL_VALUE,
                  version: ALL_VALUE,
                }),
              },
            ],
          }}
          scorer={scorer}
          scorerNames={scorerNames}
          updateConfig={updateConfig}
          datasetIndex={index}
          scorerIndex={scorerIndex}
        />
      ))}
      <Button variant="outlined" onClick={handleAddScorer}>
        Add Scorer
      </Button>
    </Box>
  );
};

const ScorerItem: React.FC<{
  entity: string;
  project: string;
  parentSpec: FilterAndGroupSpec;
  scorer: FilterAndGroupDatasetScorerSpec;
  scorerNames: string[];
  updateConfig: (
    updater: (spec: FilterAndGroupSpec) => FilterAndGroupSpec
  ) => void;
  datasetIndex: number;
  scorerIndex: number;
}> = ({
  entity,
  project,
  parentSpec,
  scorer,
  scorerNames,
  updateConfig,
  datasetIndex,
  scorerIndex,
}) => {
  const getTraceServerClient = useGetTraceServerClientContext();
  const [versions, setVersions] = useState<VersionDetails[]>([]);
  const [metricPaths, setMetricPaths] = useState<string[]>([]);

  useEffect(() => {
    if (scorer.name && scorer.name !== ALL_VALUE) {
      fetchScorerVersionsForSpecAndName(
        getTraceServerClient(),
        entity,
        project,
        parentSpec,
        scorer.name
      ).then(setVersions);
    }
    fetchMetricPathsForSpec(getTraceServerClient(), entity, project, {
      ...parentSpec,
      datasets: [
        {
          ...(parentSpec.datasets?.[0] ?? {
            name: ALL_VALUE,
            version: ALL_VALUE,
          }),
          scorers: [
            {
              ...scorer,
              metrics: [],
            },
          ],
        },
      ],
    }).then(setMetricPaths);
  }, [entity, getTraceServerClient, parentSpec, project, scorer, scorer.name]);

  const handleNameChange = (event: SelectChangeEvent<string>) => {
    const newName = event.target.value as string;
    updateConfig(spec => ({
      ...spec,
      datasets: spec.datasets?.map((d, i) =>
        i === datasetIndex
          ? {
              ...d,
              scorers: d.scorers?.map((s, j) =>
                j === scorerIndex
                  ? {...s, name: newName, version: ALL_VALUE}
                  : s
              ),
            }
          : d
      ),
    }));
  };

  const handleVersionChange = (event: SelectChangeEvent<string>) => {
    const newVersion = event.target.value as string;
    updateConfig(spec => ({
      ...spec,
      datasets: spec.datasets?.map((d, i) =>
        i === datasetIndex
          ? {
              ...d,
              scorers: d.scorers?.map((s, j) =>
                j === scorerIndex ? {...s, version: newVersion} : s
              ),
            }
          : d
      ),
    }));
  };

  const handleGroupAllVersionsChange = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const newGroupAllVersions = event.target.checked;
    updateConfig(spec => ({
      ...spec,
      datasets: spec.datasets?.map((d, i) =>
        i === datasetIndex
          ? {
              ...d,
              scorers: d.scorers?.map((s, j) =>
                j === scorerIndex
                  ? {...s, groupAllVersions: newGroupAllVersions}
                  : s
              ),
            }
          : d
      ),
    }));
  };

  const handleAddMetric = () => {
    updateConfig(spec => ({
      ...spec,
      datasets: spec.datasets?.map((d, i) =>
        i === datasetIndex
          ? {
              ...d,
              scorers: d.scorers?.map((s, j) =>
                j === scorerIndex
                  ? {
                      ...s,
                      metrics: [
                        ...(s.metrics || []),
                        {path: ALL_VALUE, shouldMinimize: false},
                      ],
                    }
                  : s
              ),
            }
          : d
      ),
    }));
  };

  const handleDelete = () => {
    updateConfig(spec => ({
      ...spec,
      datasets: spec.datasets?.map((d, i) =>
        i === datasetIndex
          ? {
              ...d,
              scorers: d.scorers?.filter((_, j) => j !== scorerIndex),
            }
          : d
      ),
    }));
  };

  return (
    <Box sx={{display: 'flex', flexDirection: 'column', gap: 2, ml: 2, mb: 2}}>
      <Box sx={{display: 'flex', gap: 2, alignItems: 'center'}}>
        <FormControl fullWidth>
          <InputLabel>Name</InputLabel>
          <Select value={scorer.name || ALL_VALUE} onChange={handleNameChange}>
            <MenuItem value={ALL_VALUE}>All</MenuItem>
            {scorerNames.map(name => (
              <MenuItem key={name} value={name}>
                {name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl fullWidth disabled={scorer.name === ALL_VALUE}>
          <InputLabel>Version</InputLabel>
          <Select
            value={scorer.version}
            onChange={handleVersionChange}
            disabled={scorer.name === ALL_VALUE}>
            <MenuItem value={ALL_VALUE}>All</MenuItem>
            {versions.map(version => (
              <MenuItem key={version.digest} value={version.digest}>
                <VersionItem version={version} />
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <IconButton onClick={handleDelete} size="small">
          <DeleteIcon />
        </IconButton>
      </Box>
      <FormControlLabel
        control={
          <Checkbox
            checked={scorer.groupAllVersions}
            onChange={handleGroupAllVersionsChange}
          />
        }
        label="Group All Versions"
      />
      <Typography variant="subtitle2">Metrics</Typography>
      {scorer.metrics?.map((metric, metricIndex) => (
        <MetricItem
          key={metricIndex}
          metric={metric}
          metricPaths={metricPaths}
          updateConfig={updateConfig}
          datasetIndex={datasetIndex}
          scorerIndex={scorerIndex}
          metricIndex={metricIndex}
        />
      ))}
      <Button variant="outlined" onClick={handleAddMetric}>
        Add Metric
      </Button>
    </Box>
  );
};

const MetricItem: React.FC<{
  metric: FilterAndGroupDatasetScorerMetricSpec;
  metricPaths: string[];
  updateConfig: (
    updater: (spec: FilterAndGroupSpec) => FilterAndGroupSpec
  ) => void;
  datasetIndex: number;
  scorerIndex: number;
  metricIndex: number;
}> = ({
  metric,
  metricPaths,
  updateConfig,
  datasetIndex,
  scorerIndex,
  metricIndex,
}) => {
  const handlePathChange = (event: SelectChangeEvent<string>) => {
    const newPath = event.target.value as string;
    updateConfig(spec => ({
      ...spec,
      datasets: spec.datasets?.map((d, i) =>
        i === datasetIndex
          ? {
              ...d,
              scorers: d.scorers?.map((s, j) =>
                j === scorerIndex
                  ? {
                      ...s,
                      metrics: s.metrics?.map((m, k) =>
                        k === metricIndex ? {...m, path: newPath} : m
                      ),
                    }
                  : s
              ),
            }
          : d
      ),
    }));
  };

  const handleShouldMinimizeChange = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const newShouldMinimize = event.target.checked;
    updateConfig(spec => ({
      ...spec,
      datasets: spec.datasets?.map((d, i) =>
        i === datasetIndex
          ? {
              ...d,
              scorers: d.scorers?.map((s, j) =>
                j === scorerIndex
                  ? {
                      ...s,
                      metrics: s.metrics?.map((m, k) =>
                        k === metricIndex
                          ? {...m, shouldMinimize: newShouldMinimize}
                          : m
                      ),
                    }
                  : s
              ),
            }
          : d
      ),
    }));
  };

  const handleDelete = () => {
    updateConfig(spec => ({
      ...spec,
      datasets: spec.datasets?.map((d, i) =>
        i === datasetIndex
          ? {
              ...d,
              scorers: d.scorers?.map((s, j) =>
                j === scorerIndex
                  ? {
                      ...s,
                      metrics: s.metrics?.filter((_, k) => k !== metricIndex),
                    }
                  : s
              ),
            }
          : d
      ),
    }));
  };

  return (
    <Box sx={{display: 'flex', gap: 2, ml: 2, mb: 2, alignItems: 'center'}}>
      <FormControl fullWidth>
        <InputLabel>Metric Path</InputLabel>
        <Select value={metric.path} onChange={handlePathChange}>
          <MenuItem value={ALL_VALUE}>All</MenuItem>
          {metricPaths.map(path => (
            <MenuItem key={path} value={path}>
              {path}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
      <FormControlLabel
        control={
          <Checkbox
            checked={metric.shouldMinimize}
            onChange={handleShouldMinimizeChange}
          />
        }
        label="Should Minimize"
      />
      <IconButton onClick={handleDelete} size="small">
        <DeleteIcon />
      </IconButton>
    </Box>
  );
};

const ModelsConfig: React.FC<{
  entity: string;
  project: string;
  parentSpec: FilterAndGroupSpec;
  models: FilterAndGroupDatasetSpec[] | undefined;
  updateConfig: (
    updater: (spec: FilterAndGroupSpec) => FilterAndGroupSpec
  ) => void;
}> = ({entity, project, parentSpec, models, updateConfig}) => {
  const getTraceServerClient = useGetTraceServerClientContext();
  const [modelNames, setModelNames] = useState<string[]>([]);

  useEffect(() => {
    fetchModelNamesForSpec(
      getTraceServerClient(),
      entity,
      project,
      parentSpec
    ).then(setModelNames);
  }, [entity, project, getTraceServerClient, parentSpec]);

  const handleAddModel = () => {
    updateConfig(spec => ({
      ...spec,
      models: [
        ...(spec.models || []),
        {name: ALL_VALUE, version: ALL_VALUE, groupAllVersions: false},
      ],
    }));
  };

  return (
    <Box sx={{mb: 3}}>
      <Typography variant="h6" gutterBottom>
        Models
      </Typography>
      {models?.map((model, index) => (
        <ModelItem
          key={index}
          entity={entity}
          project={project}
          parentSpec={{
            sourceEvaluations: parentSpec.sourceEvaluations,
            datasets: parentSpec.datasets,
            models: [
              {
                name: model.name,
                version: ALL_VALUE,
              },
            ],
          }}
          model={model}
          modelNames={modelNames}
          updateConfig={updateConfig}
          index={index}
        />
      ))}
      <Button variant="outlined" onClick={handleAddModel}>
        Add Model
      </Button>
    </Box>
  );
};

const ModelItem: React.FC<{
  entity: string;
  project: string;
  parentSpec: FilterAndGroupSpec;
  model: FilterAndGroupDatasetSpec;
  modelNames: string[];
  updateConfig: (
    updater: (spec: FilterAndGroupSpec) => FilterAndGroupSpec
  ) => void;
  index: number;
}> = ({
  entity,
  project,
  parentSpec,
  model,
  modelNames,
  updateConfig,
  index,
}) => {
  const getTraceServerClient = useGetTraceServerClientContext();

  const [versions, setVersions] = useState<VersionDetails[]>([]);

  useEffect(() => {
    if (model.name && model.name !== ALL_VALUE) {
      fetchModelVersionsForSpecAndName(
        getTraceServerClient(),
        entity,
        project,
        parentSpec,
        model.name
      ).then(setVersions);
    }
  }, [model.name, entity, project, getTraceServerClient, parentSpec]);

  const handleNameChange = (event: SelectChangeEvent<string>) => {
    const newName = event.target.value as string;
    updateConfig(spec => ({
      ...spec,
      models: spec.models?.map((m, i) =>
        i === index ? {...m, name: newName, version: ALL_VALUE} : m
      ),
    }));
  };

  const handleVersionChange = (event: SelectChangeEvent<string>) => {
    const newVersion = event.target.value as string;
    updateConfig(spec => ({
      ...spec,
      models: spec.models?.map((m, i) =>
        i === index ? {...m, version: newVersion} : m
      ),
    }));
  };

  const handleGroupAllVersionsChange = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const newGroupAllVersions = event.target.checked;
    updateConfig(spec => ({
      ...spec,
      models: spec.models?.map((m, i) =>
        i === index ? {...m, groupAllVersions: newGroupAllVersions} : m
      ),
    }));
  };

  const handleDelete = () => {
    updateConfig(spec => ({
      ...spec,
      models: spec.models?.filter((_, i) => i !== index),
    }));
  };

  return (
    <Box sx={{display: 'flex', flexDirection: 'column', gap: 2, mb: 2}}>
      <Box sx={{display: 'flex', gap: 2, alignItems: 'center'}}>
        <FormControl fullWidth>
          <InputLabel>Name</InputLabel>
          <Select value={model.name || ALL_VALUE} onChange={handleNameChange}>
            <MenuItem value={ALL_VALUE}>All</MenuItem>
            {modelNames.map(name => (
              <MenuItem key={name} value={name}>
                {name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl fullWidth disabled={model.name === ALL_VALUE}>
          <InputLabel>Version</InputLabel>
          <Select
            value={model.version}
            onChange={handleVersionChange}
            disabled={model.name === ALL_VALUE}>
            <MenuItem value={ALL_VALUE}>All</MenuItem>
            {versions.map(version => (
              <MenuItem key={version.digest} value={version.digest}>
                <VersionItem version={version} />
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <IconButton onClick={handleDelete} size="small">
          <DeleteIcon />
        </IconButton>
      </Box>
      <FormControlLabel
        control={
          <Checkbox
            checked={model.groupAllVersions}
            onChange={handleGroupAllVersionsChange}
          />
        }
        label="Group All Versions"
      />
    </Box>
  );
};

const VersionItem: React.FC<{
  version: VersionDetails;
}> = ({version}) => {
  return (
    <div>
      v{version.index} ({version.digest.slice(0, 6)})
    </div>
  );
};
