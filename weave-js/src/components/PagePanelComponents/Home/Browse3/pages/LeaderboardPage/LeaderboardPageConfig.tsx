import AddIcon from '@mui/icons-material/Add';
import {Alert, Box, Button, Typography} from '@mui/material';
import React, {useState} from 'react';

import {ColumnConfig} from './ColumnConfig';
import {LeaderboardConfigType} from './LeaderboardConfigType';
import {ModelConfig} from './ModelConfig';

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
  const handleSave = () => {
    onPersist();
  };

  const handleCancel = () => {
    onCancel();
  };

  const handleAddColumn = () => {
    setConfig(prev => ({
      ...prev,
      config: {
        ...prev.config,
        datasets: [
          ...prev.config.datasets,
          {dataset: {name: '', version: 'latest'}, scores: []},
        ],
      },
    }));
  };

  const handleRemoveColumn = (index: number) => {
    setConfig(prev => ({
      ...prev,
      config: {
        ...prev.config,
        datasets: prev.config.datasets.filter((_, i) => i !== index),
      },
    }));
  };

  const handleUpdateColumn = (
    index: number,
    updatedColumn: LeaderboardConfigType['config']['datasets'][0]
  ) => {
    setConfig(prev => ({
      ...prev,
      config: {
        ...prev.config,
        datasets: prev.config.datasets.map((column, i) =>
          i === index ? updatedColumn : column
        ),
      },
    }));
  };

  const handleAddModel = () => {
    setConfig(prev => ({
      ...prev,
      config: {
        ...prev.config,
        models: [...prev.config.models, {name: '', version: 'latest'}],
      },
    }));
  };

  const handleRemoveModel = (index: number) => {
    setConfig(prev => ({
      ...prev,
      config: {
        ...prev.config,
        models: prev.config.models.filter((_, i) => i !== index),
      },
    }));
  };

  const handleUpdateModel = (
    index: number,
    updatedModel: LeaderboardConfigType['config']['models'][0]
  ) => {
    setConfig(prev => ({
      ...prev,
      config: {
        ...prev.config,
        models: prev.config.models.map((model, i) =>
          i === index ? updatedModel : model
        ),
      },
    }));
  };

  const [showAlert, setShowAlert] = useState(true);

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
          flexGrow: 1,
          overflowY: 'auto',
          p: 2,
        }}>
        {showAlert && <TempAlert onClose={() => setShowAlert(false)} />}
        <Typography variant="h5" gutterBottom>
          Leaderboard Configuration
        </Typography>

        <Box sx={{mb: 4}}>
          <Typography variant="h6" gutterBottom>
            Columns
          </Typography>
          {config.config.datasets.map((column, index) => (
            <ColumnConfig
              entity={entity}
              project={project}
              key={index}
              column={column}
              onUpdate={updatedColumn =>
                handleUpdateColumn(index, updatedColumn)
              }
              onRemove={() => handleRemoveColumn(index)}
            />
          ))}
          <Button
            startIcon={<AddIcon />}
            onClick={handleAddColumn}
            sx={{mt: 2}}>
            Add Column
          </Button>
        </Box>

        <Box sx={{mb: 4}}>
          <Typography variant="h6" gutterBottom>
            Models
          </Typography>
          {config.config.models.map((model, index) => (
            <ModelConfig
              key={index}
              model={model}
              onUpdate={updatedModel => handleUpdateModel(index, updatedModel)}
              onRemove={() => handleRemoveModel(index)}
            />
          ))}
          <Button startIcon={<AddIcon />} onClick={handleAddModel} sx={{mt: 2}}>
            Add Model
          </Button>
        </Box>
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
