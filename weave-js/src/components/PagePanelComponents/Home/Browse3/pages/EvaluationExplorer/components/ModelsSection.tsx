import React, { useState } from 'react';
import { ExpandMore, Add, Delete } from '@mui/icons-material';
import IconButton from '@mui/material/IconButton';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Checkbox from '@mui/material/Checkbox';
import ListItemText from '@mui/material/ListItemText';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import Chip from '@mui/material/Chip';
import Button from '@mui/material/Button';
import { ModelsSectionProps } from '../types';

export const ModelsSection: React.FC<ModelsSectionProps> = ({
  selectedModelIds = [],
  onModelsChange,
  models,
  isLoading
}) => {
  const [expandedModels, setExpandedModels] = useState<string[]>([]);

  const handleModelToggle = (modelId: string) => {
    const newIds = selectedModelIds.includes(modelId)
      ? selectedModelIds.filter(id => id !== modelId)
      : [...selectedModelIds, modelId];
    
    if (onModelsChange) {
      onModelsChange(newIds);
    }
  };

  const handleAddNewModel = () => {
    // TODO: Handle creating new model
    console.log('Create new model');
    const newModelId = 'new-model-' + Date.now();
    if (onModelsChange) {
      onModelsChange([...selectedModelIds, newModelId]);
    }
  };

  const handleModelExpand = (modelId: string) => {
    setExpandedModels(prev => 
      prev.includes(modelId) 
        ? prev.filter(id => id !== modelId)
        : [...prev, modelId]
    );
  };

  return (
    <Box sx={{ padding: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 1 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
          Model(s) {selectedModelIds.length > 0 && (
            <Chip size="small" label={selectedModelIds.length} sx={{ marginLeft: 1 }} />
          )}
        </Typography>
        <Button 
          size="small" 
          startIcon={<Add />} 
          onClick={handleAddNewModel}
          sx={{ minWidth: 'auto', padding: '2px 8px' }}
          disabled={isLoading}
        >
          New
        </Button>
      </Box>
      
      {/* Model Selection List */}
      <Box sx={{ maxHeight: 200, overflowY: 'auto', marginBottom: 1 }}>
        {models.map((model) => (
          <Box key={model.id} sx={{ display: 'flex', alignItems: 'center' }}>
            <Checkbox
              checked={selectedModelIds.includes(model.id)}
              onChange={() => handleModelToggle(model.id)}
              size="small"
              disabled={isLoading}
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
      {selectedModelIds.length > 0 && (
        <Box sx={{ marginTop: 2 }}>
          <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary' }}>
            Selected Models Configuration:
          </Typography>
          {selectedModelIds.map((modelId) => {
            const model = models.find(m => m.id === modelId) || { 
              id: modelId, 
              name: modelId, 
              description: 'Custom Model' 
            };
            
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
  );
}; 