import {
  Alert,
  Box,
  Button,
  Checkbox,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Select,
  SelectChangeEvent,
  TextField,
  Typography,
} from '@mui/material';
import React, {useCallback, useEffect, useState} from 'react';

import {useWFHooks} from '../wfReactInterface/context';
import {FilterAndGroupDatasetSpec, FilterAndGroupSourceEvaluationSpec, FilterAndGroupSpec, LeaderboardConfigType} from './LeaderboardConfigType';

export const LeaderboardConfig: React.FC<{
  entity: string;
  project: string;
  config: LeaderboardConfigType;
  onCancel: () => void;
  onPersist: () => void;
  setConfig: (
    updater: (config: LeaderboardConfigType) => LeaderboardConfigType
  ) => void;
}> = ({entity, project, config, setConfig, onPersist, onCancel}) => {
  const [showAlert, setShowAlert] = useState(true);

  const handleSave = () => {
    onPersist();
  };

  const handleCancel = () => {
    onCancel();
  };

  const updateConfig = (updater: (spec: FilterAndGroupSpec) => FilterAndGroupSpec) => {
    setConfig((prevConfig) => ({
      ...prevConfig,
      config: {
        ...prevConfig.config,
        dataSelectionSpec: updater(prevConfig.config.dataSelectionSpec),
      },
    }));
  };

  return (
    <Box
      sx={{
        width: '50%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        border: '1px solid #e0e0e0',
      }}>
      <Box
        sx={{
          overflowY: 'auto',
          p: 2,
        }}>
        {showAlert && <TempAlert onClose={() => setShowAlert(false)} />}
        <Typography variant="h5" gutterBottom>
          Leaderboard Configuration
        </Typography>
      </Box>

      <Box sx={{mt: 2, mb: 2, flex: 1, overflowY: 'auto', px: 2}}>
        <SourceEvaluationsConfig
          sourceEvaluations={config.config.dataSelectionSpec.sourceEvaluations}
          updateConfig={updateConfig}
        />
        <DatasetsConfig
          datasets={config.config.dataSelectionSpec.datasets}
          updateConfig={updateConfig}
        />
        <ModelsConfig
          models={config.config.dataSelectionSpec.models}
          updateConfig={updateConfig}
        />
      </Box>

      <Box sx={{mt: 2, mb: 2, px: 2}}>
        <Typography variant="h6" gutterBottom>
          Configuration Preview
        </Typography>
        <pre
          style={{
            backgroundColor: '#f5f5f5',
            padding: '10px',
            borderRadius: '4px',
            overflowX: 'auto',
            maxHeight: '400px',
            whiteSpace: 'pre-wrap',
            wordWrap: 'break-word',
          }}>
          {JSON.stringify(config, null, 2)}
        </pre>
      </Box>

      <Box
        sx={{
          display: 'flex',
          justifyContent: 'flex-end',
          height: '51px',
          p: 1,
          borderTop: '1px solid #e0e0e0',
        }}>
        <Button variant="outlined" onClick={handleCancel} sx={{mr: 2}}>
          Cancel
        </Button>
        <Button variant="contained" onClick={handleSave} sx={{mr: 2}}>
          Save
        </Button>
      </Box>
    </Box>
  );
};

const TempAlert: React.FC<{onClose: () => void}> = ({onClose}) => {
  return (
    <Alert severity="info" onClose={onClose}>
      <Typography variant="body1">
        Configuration edtior purely for internal exploration, not for production
        use.
      </Typography>
    </Alert>
  );
};

const SourceEvaluationsConfig: React.FC<{
  sourceEvaluations: FilterAndGroupSourceEvaluationSpec[] | undefined;
  updateConfig: (updater: (spec: FilterAndGroupSpec) => FilterAndGroupSpec) => void;
}> = ({sourceEvaluations, updateConfig}) => {
  const [evaluationNames, setEvaluationNames] = useState<string[]>([]);

  useEffect(() => {
    fetchEvaluationNames().then(setEvaluationNames);
  }, []);

  const handleAddSourceEvaluation = () => {
    updateConfig((spec) => ({
      ...spec,
      sourceEvaluations: [...(spec.sourceEvaluations || []), {name: '', version: '*'}],
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
  evaluation: FilterAndGroupSourceEvaluationSpec;
  evaluationNames: string[];
  updateConfig: (updater: (spec: FilterAndGroupSpec) => FilterAndGroupSpec) => void;
  index: number;
}> = ({evaluation, evaluationNames, updateConfig, index}) => {
  const [versions, setVersions] = useState<string[]>([]);

  useEffect(() => {
    if (evaluation.name) {
      fetchEvaluationVersionsForName(evaluation.name).then(setVersions);
    }
  }, [evaluation.name]);

  const handleNameChange = (event: SelectChangeEvent<string>) => {
    const newName = event.target.value as string;
    updateConfig((spec) => ({
      ...spec,
      sourceEvaluations: spec.sourceEvaluations?.map((e, i) =>
        i === index ? {...e, name: newName} : e
      ),
    }));
  };

  const handleVersionChange = (event: SelectChangeEvent<string>) => {
    const newVersion = event.target.value as string;
    updateConfig((spec) => ({
      ...spec,
      sourceEvaluations: spec.sourceEvaluations?.map((e, i) =>
        i === index ? {...e, version: newVersion} : e
      ),
    }));
  };

  return (
    <Box sx={{display: 'flex', gap: 2, mb: 2}}>
      <FormControl fullWidth>
        <InputLabel>Name</InputLabel>
        <Select value={evaluation.name} onChange={handleNameChange}>
          <MenuItem value="*">All</MenuItem>
          {evaluationNames.map((name) => (
            <MenuItem key={name} value={name}>
              {name}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
      <FormControl fullWidth>
        <InputLabel>Version</InputLabel>
        <Select value={evaluation.version} onChange={handleVersionChange}>
          <MenuItem value="*">All</MenuItem>
          {versions.map((version) => (
            <MenuItem key={version} value={version}>
              {version}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
    </Box>
  );
};

const DatasetsConfig: React.FC<{
  datasets: FilterAndGroupDatasetSpec[] | undefined;
  updateConfig: (updater: (spec: FilterAndGroupSpec) => FilterAndGroupSpec) => void;
}> = ({datasets, updateConfig}) => {
  const [datasetNames, setDatasetNames] = useState<string[]>([]);

  useEffect(() => {
    fetchDatasetNamesForSpec({}).then(setDatasetNames);
  }, []);

  const handleAddDataset = () => {
    updateConfig((spec) => ({
      ...spec,
      datasets: [...(spec.datasets || []), {name: '', version: '*', groupAllVersions: false}],
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
  dataset: FilterAndGroupDatasetSpec;
  datasetNames: string[];
  updateConfig: (updater: (spec: FilterAndGroupSpec) => FilterAndGroupSpec) => void;
  index: number;
}> = ({dataset, datasetNames, updateConfig, index}) => {
  const [versions, setVersions] = useState<string[]>([]);

  useEffect(() => {
    if (dataset.name) {
      fetchDatasetVersionsForSpecAndName({}, dataset.name).then(setVersions);
    }
  }, [dataset.name]);

    const handleNameChange = (event: SelectChangeEvent<string>) => {
    const newName = event.target.value as string;
    updateConfig((spec) => ({
      ...spec,
      datasets: spec.datasets?.map((d, i) =>
        i === index ? {...d, name: newName} : d
      ),
    }));
  };

  const handleVersionChange = (event: SelectChangeEvent<string>) => {
    const newVersion = event.target.value as string;
    updateConfig((spec) => ({
      ...spec,
      datasets: spec.datasets?.map((d, i) =>
        i === index ? {...d, version: newVersion} : d
      ),
    }));
  };

  const handleGroupAllVersionsChange = (event: SelectChangeEvent<HTMLInputElement>) => {
    const newGroupAllVersions = event.target.checked;
    updateConfig((spec) => ({
      ...spec,
      datasets: spec.datasets?.map((d, i) =>
        i === index ? {...d, groupAllVersions: newGroupAllVersions} : d
      ),
    }));
  };

  return (
    <Box sx={{display: 'flex', flexDirection: 'column', gap: 2, mb: 2}}>
      <Box sx={{display: 'flex', gap: 2}}>
        <FormControl fullWidth>
          <InputLabel>Name</InputLabel>
          <Select value={dataset.name} onChange={handleNameChange}>
            <MenuItem value="*">All</MenuItem>
            {datasetNames.map((name) => (
              <MenuItem key={name} value={name}>
                {name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl fullWidth>
          <InputLabel>Version</InputLabel>
          <Select value={dataset.version} onChange={handleVersionChange}>
            <MenuItem value="*">All</MenuItem>
            {versions.map((version) => (
              <MenuItem key={version} value={version}>
                {version}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
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
    </Box>
  );
};

const ModelsConfig: React.FC<{
  models: FilterAndGroupDatasetSpec[] | undefined;
  updateConfig: (updater: (spec: FilterAndGroupSpec) => FilterAndGroupSpec) => void;
}> = ({models, updateConfig}) => {
  const [modelNames, setModelNames] = useState<string[]>([]);

  useEffect(() => {
    fetchModelNamesForSpec({}).then(setModelNames);
  }, []);

  const handleAddModel = () => {
    updateConfig((spec) => ({
      ...spec,
      models: [...(spec.models || []), {name: '', version: '*', groupAllVersions: false}],
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
  model: FilterAndGroupDatasetSpec;
  modelNames: string[];
  updateConfig: (updater: (spec: FilterAndGroupSpec) => FilterAndGroupSpec) => void;
  index: number;
}> = ({model, modelNames, updateConfig, index}) => {
  const [versions, setVersions] = useState<string[]>([]);

  useEffect(() => {
    if (model.name) {
      fetchModelVersionsForSpecndName({}, model.name).then(setVersions);
    }
  }, [model.name]);

  const handleNameChange = (event: SelectChangeEvent<string>) => {
    const newName = event.target.value as string;
    updateConfig((spec) => ({
      ...spec,
      models: spec.models?.map((m, i) =>
        i === index ? {...m, name: newName} : m
      ),
    }));
  };

  const handleVersionChange = (event: SelectChangeEvent<string>) => {
    const newVersion = event.target.value as string;
    updateConfig((spec) => ({
      ...spec,
      models: spec.models?.map((m, i) =>
        i === index ? {...m, version: newVersion} : m
      ),
    }));
  };

  const handleGroupAllVersionsChange = (event: SelectChangeEvent<HTMLInputElement>) => {
    const newGroupAllVersions = event.target.checked;
    updateConfig((spec) => ({
      ...spec,
      models: spec.models?.map((m, i) =>
        i === index ? {...m, groupAllVersions: newGroupAllVersions} : m
      ),
    }));
  };

  return (
    <Box sx={{display: 'flex', flexDirection: 'column', gap: 2, mb: 2}}>
      <Box sx={{display: 'flex', gap: 2}}>
        <FormControl fullWidth>
          <InputLabel>Name</InputLabel>
          <Select value={model.name} onChange={handleNameChange}>
            <MenuItem value="*">All</MenuItem>
            {modelNames.map((name) => (
              <MenuItem key={name} value={name}>
                {name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl fullWidth>
          <InputLabel>Version</InputLabel>
          <Select value={model.version} onChange={handleVersionChange}>
            <MenuItem value="*">All</MenuItem>
            {versions.map((version) => (
              <MenuItem key={version} value={version}>
                {version}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
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

const fetchEvaluationNames = async (): Promise<string[]> => {
  // TODO
  return Promise.resolve([])
}

const fetchEvaluationVersionsForName = async (name: string): Promise<string[]> => {
  // TODO
  return Promise.resolve([])
}

const fetchDatasetNamesForSpec = async (spec: FilterAndGroupSpec): Promise<string[]> => {
  // TODO
  return Promise.resolve([])
}

const fetchDatasetVersionsForSpecAndName = async (spec: FilterAndGroupSpec, name: string): Promise<string[]> => {
  // TODO
  return Promise.resolve([])
}

const fetchModelNamesForSpec = async (spec: FilterAndGroupSpec): Promise<string[]> => {
  // TODO
  return Promise.resolve([])
}

const fetchModelVersionsForSpecndName = async (spec: FilterAndGroupSpec, name: string): Promise<string[]> => {
  // TODO
  return Promise.resolve([])
}

const fetchScorerNamesForSpec = async (spec: FilterAndGroupSpec): Promise<string[]> => {
  // TODO
  return Promise.resolve([])
}

const fetchScorerVersionsForSpecAndName = async (spec: FilterAndGroupSpec, name: string): Promise<string[]> => {
  // TODO
  return Promise.resolve([])
}

const fetchMetricPathsForSpec = async (spec: FilterAndGroupSpec): Promise<string[]> => {
    // TODO
    return Promise.resolve([])
}