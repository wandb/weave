import React, { useState } from 'react';
import { 
  ChevronLeft, 
  ChevronRight,
  Star,
  ExpandMore,
  Add,
  Delete
} from '@mui/icons-material';
import IconButton from '@mui/material/IconButton';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Divider from '@mui/material/Divider';
import Checkbox from '@mui/material/Checkbox';
import ListItemText from '@mui/material/ListItemText';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import Chip from '@mui/material/Chip';
import Button from '@mui/material/Button';

// Placeholder hook for available datasets
const useAvailableDatasets = () => {
  // TODO: Replace with actual API call
  return {
    datasets: [
      { id: 'dataset-1', name: 'Customer Service v1' },
      { id: 'dataset-2', name: 'Customer Service v2' },
      { id: 'dataset-3', name: 'Product Reviews' },
      { id: 'dataset-4', name: 'Support Tickets' },
    ],
    isLoading: false
  };
};

// Placeholder hook for available models
const useAvailableModels = () => {
  // TODO: Replace with actual API call
  return {
    models: [
      { id: 'gpt-4', name: 'GPT-4', description: 'OpenAI GPT-4' },
      { id: 'gpt-3.5-turbo', name: 'GPT-3.5 Turbo', description: 'OpenAI GPT-3.5 Turbo' },
      { id: 'claude-2', name: 'Claude 2', description: 'Anthropic Claude 2' },
      { id: 'llama-2-70b', name: 'Llama 2 70B', description: 'Meta Llama 2' },
      { id: 'custom-model-1', name: 'Custom Fine-tuned Model', description: 'Your custom model' },
    ],
    isLoading: false
  };
};

interface ConfigurationBarProps {
  selectedDatasetId?: string;
  isDatasetEdited?: boolean;
  onDatasetChange?: (datasetId: string) => void;
  selectedModelIds?: string[];
  onModelsChange?: (modelIds: string[]) => void;
}

export const ConfigurationBar: React.FC<ConfigurationBarProps> = ({
  selectedDatasetId,
  isDatasetEdited = false,
  onDatasetChange,
  selectedModelIds = [],
  onModelsChange
}) => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [expandedModels, setExpandedModels] = useState<string[]>([]);
  const { datasets, isLoading } = useAvailableDatasets();
  const { models, isLoading: modelsLoading } = useAvailableModels();

  const handleDatasetChange = (event: any) => {
    const value = event.target.value;
    if (onDatasetChange) {
      onDatasetChange(value);
    }
  };

  const handleModelToggle = (modelId: string) => {
    const currentIds = selectedModelIds || [];
    const newIds = currentIds.includes(modelId)
      ? currentIds.filter(id => id !== modelId)
      : [...currentIds, modelId];
    
    if (onModelsChange) {
      onModelsChange(newIds);
    }
  };

  const handleAddNewModel = () => {
    // TODO: Handle creating new model
    console.log('Create new model');
    const newModelId = 'new-model-' + Date.now();
    if (onModelsChange) {
      onModelsChange([...(selectedModelIds || []), newModelId]);
    }
  };

  const handleModelExpand = (modelId: string) => {
    setExpandedModels(prev => 
      prev.includes(modelId) 
        ? prev.filter(id => id !== modelId)
        : [...prev, modelId]
    );
  };

  if (isCollapsed) {
    return (
      <Box
        sx={{
          width: '48px',
          height: '100%',
          borderRight: '1px solid #E0E0E0',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          paddingTop: 2,
          backgroundColor: '#FAFAFA'
        }}
      >
        <IconButton
          size="small"
          onClick={() => setIsCollapsed(false)}
          sx={{ marginBottom: 2 }}
        >
          <ChevronRight />
        </IconButton>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        width: '300px',
        height: '100%',
        borderRight: '1px solid #E0E0E0',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: '#FAFAFA'
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: 2,
          borderBottom: '1px solid #E0E0E0'
        }}
      >
        <Typography variant="h6" sx={{ fontWeight: 600 }}>
          Configuration
        </Typography>
        <IconButton
          size="small"
          onClick={() => setIsCollapsed(true)}
        >
          <ChevronLeft />
        </IconButton>
      </Box>

      {/* Dataset Section */}
      <Box sx={{ padding: 2 }}>
        <Typography variant="subtitle2" sx={{ marginBottom: 1, fontWeight: 600 }}>
          Dataset
        </Typography>
        <FormControl fullWidth size="small">
          <InputLabel id="dataset-select-label">
            {isDatasetEdited ? 'Dataset (edited)' : 'Select Dataset'}
          </InputLabel>
          <Select
            labelId="dataset-select-label"
            value={selectedDatasetId || ''}
            label={isDatasetEdited ? 'Dataset (edited)' : 'Select Dataset'}
            onChange={handleDatasetChange}
            disabled={isLoading}
            endAdornment={
              isDatasetEdited ? (
                <Star 
                  sx={{ 
                    color: '#FFA500', 
                    fontSize: 16, 
                    marginRight: 2 
                  }} 
                />
              ) : null
            }
          >
            <MenuItem value="create-new">
              <em>Create New Dataset</em>
            </MenuItem>
            <Divider />
            {datasets.map((dataset) => (
              <MenuItem key={dataset.id} value={dataset.id}>
                {dataset.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        {isDatasetEdited && (
          <Typography 
            variant="caption" 
            sx={{ 
              color: '#FFA500',
              display: 'flex',
              alignItems: 'center',
              marginTop: 0.5
            }}
          >
            <Star sx={{ fontSize: 12, marginRight: 0.5 }} />
            Dataset has been edited
          </Typography>
        )}
      </Box>

      <Divider />

      {/* Models Section */}
      <Box sx={{ padding: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 1 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
            Model(s) {selectedModelIds && selectedModelIds.length > 0 && (
              <Chip size="small" label={selectedModelIds.length} sx={{ marginLeft: 1 }} />
            )}
          </Typography>
          <Button 
            size="small" 
            startIcon={<Add />} 
            onClick={handleAddNewModel}
            sx={{ minWidth: 'auto', padding: '2px 8px' }}
          >
            New
          </Button>
        </Box>
        
        {/* Model Selection List */}
        <Box sx={{ maxHeight: 200, overflowY: 'auto', marginBottom: 1 }}>
          {models.map((model) => (
            <Box key={model.id} sx={{ display: 'flex', alignItems: 'center' }}>
              <Checkbox
                checked={(selectedModelIds || []).includes(model.id)}
                onChange={() => handleModelToggle(model.id)}
                size="small"
              />
              <ListItemText 
                primary={model.name}
                secondary={model.description}
                primaryTypographyProps={{ variant: 'body2' }}
                secondaryTypographyProps={{ variant: 'caption' }}
              />
            </Box>
          ))}
        </Box>

        {/* Selected Models with Expandable Configuration */}
        {selectedModelIds && selectedModelIds.length > 0 && (
          <Box sx={{ marginTop: 2 }}>
            <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary' }}>
              Selected Models Configuration:
            </Typography>
            {selectedModelIds.map((modelId) => {
              const model = models.find(m => m.id === modelId) || { id: modelId, name: modelId, description: 'Custom Model' };
              return (
                <Accordion 
                  key={modelId}
                  expanded={expandedModels.includes(modelId)}
                  onChange={() => handleModelExpand(modelId)}
                  sx={{ 
                    marginTop: 1,
                    '&:before': { display: 'none' },
                    boxShadow: 'none',
                    border: '1px solid #E0E0E0'
                  }}
                >
                  <AccordionSummary
                    expandIcon={<ExpandMore />}
                    sx={{ minHeight: 36, '&.Mui-expanded': { minHeight: 36 } }}
                  >
                    <Box sx={{ display: 'flex', alignItems: 'center', width: '100%' }}>
                      <Typography variant="body2">{model.name}</Typography>
                      <IconButton 
                        size="small" 
                        onClick={(e) => {
                          e.stopPropagation();
                          handleModelToggle(modelId);
                        }}
                        sx={{ marginLeft: 'auto', marginRight: 1 }}
                      >
                        <Delete fontSize="small" />
                      </IconButton>
                    </Box>
                  </AccordionSummary>
                  <AccordionDetails sx={{ borderTop: '1px solid #E0E0E0' }}>
                    <Box sx={{ padding: 1 }}>
                      <Typography variant="caption" color="text.secondary">
                        TODO: Model configuration for {model.name}
                      </Typography>
                      {/* Placeholder for model-specific settings */}
                      <Box sx={{ 
                        marginTop: 1, 
                        padding: 1, 
                        backgroundColor: '#FAFAFA', 
                        borderRadius: 1 
                      }}>
                        <Typography variant="caption">Temperature, Max tokens, etc.</Typography>
                      </Box>
                    </Box>
                  </AccordionDetails>
                </Accordion>
              );
            })}
          </Box>
        )}
      </Box>

      <Divider />

      {/* Scorers Section */}
      <Box sx={{ padding: 2 }}>
        <Typography variant="subtitle2" sx={{ marginBottom: 1, fontWeight: 600 }}>
          Scorer(s)
        </Typography>
        <Box sx={{ 
          padding: 2, 
          backgroundColor: '#F5F5F5', 
          borderRadius: 1,
          border: '1px dashed #CCC'
        }}>
          <Typography variant="body2" color="text.secondary">
            TODO: Scorer selection
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}; 