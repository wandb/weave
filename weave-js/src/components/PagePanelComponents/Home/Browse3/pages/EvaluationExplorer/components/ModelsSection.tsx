import React from 'react';
import { Add, Settings, Close } from '@mui/icons-material';
import IconButton from '@mui/material/IconButton';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import FormControl from '@mui/material/FormControl';
import Button from '@mui/material/Button';
import { ModelsSectionProps } from '../types';

interface ExtendedModelsSectionProps extends ModelsSectionProps {
  onModelDetailOpen?: (modelId: string) => void;
}

export const ModelsSection: React.FC<ExtendedModelsSectionProps> = ({
  selectedModelIds = [],
  onModelsChange,
  models,
  isLoading,
  onModelDetailOpen
}) => {
  const handleModelChange = (index: number, newModelId: string) => {
    const newIds = [...selectedModelIds];
    
    if (newModelId === 'create-new') {
      // Handle creating new model
      const tempModelId = 'new-model-' + Date.now();
      newIds[index] = tempModelId;
      if (onModelDetailOpen) {
        onModelDetailOpen(tempModelId);
      }
    } else if (newModelId === 'remove') {
      // Remove this dropdown
      newIds.splice(index, 1);
    } else {
      newIds[index] = newModelId;
    }
    
    if (onModelsChange) {
      onModelsChange(newIds);
    }
  };

  const handleAddDropdown = () => {
    if (onModelsChange) {
      onModelsChange([...selectedModelIds, '']);
    }
  };

  // Ensure at least one dropdown exists
  const dropdownIds = selectedModelIds.length > 0 ? selectedModelIds : [''];

  return (
    <Box sx={{ padding: 2 }}>
      <Box sx={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between', 
        marginBottom: 2 
      }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
          Models
        </Typography>
      </Box>
      
      {/* Model Selection Dropdowns */}
      <Box sx={{ 
        display: 'flex',
        flexDirection: 'column',
        gap: 1
      }}>
        {dropdownIds.map((modelId, index) => (
          <Box 
            key={index} 
            sx={{ 
              display: 'flex', 
              alignItems: 'center',
              gap: 1
            }}
          >
            <FormControl size="small" sx={{ flex: 1 }}>
              <Select
                value={modelId || ''}
                onChange={(e) => handleModelChange(index, e.target.value)}
                displayEmpty
                sx={{ 
                  fontSize: '0.875rem',
                  '& .MuiSelect-select': {
                    paddingY: 1
                  }
                }}
                disabled={isLoading}
              >
                <MenuItem value="" disabled>
                  <em>Select a model</em>
                </MenuItem>
                {models.map(model => (
                  <MenuItem 
                    key={model.id} 
                    value={model.id}
                    disabled={selectedModelIds.includes(model.id) && model.id !== modelId}
                  >
                    {model.name}
                  </MenuItem>
                ))}
                <MenuItem value="create-new">
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Add fontSize="small" />
                    <span>Create new model</span>
                  </Box>
                </MenuItem>
              </Select>
            </FormControl>
            
            {/* Settings button */}
            {modelId && modelId !== '' && (
              <IconButton 
                size="small"
                onClick={() => onModelDetailOpen && onModelDetailOpen(modelId)}
                sx={{ 
                  '&:hover': { 
                    backgroundColor: 'rgba(0, 0, 0, 0.04)' 
                  } 
                }}
              >
                <Settings fontSize="small" />
              </IconButton>
            )}
            
            {/* Remove button */}
            {dropdownIds.length > 1 && (
              <IconButton 
                size="small"
                onClick={() => handleModelChange(index, 'remove')}
                sx={{ 
                  '&:hover': { 
                    backgroundColor: 'rgba(0, 0, 0, 0.04)' 
                  } 
                }}
              >
                <Close fontSize="small" />
              </IconButton>
            )}
          </Box>
        ))}
        
        {/* Add new dropdown button */}
        <Button 
          size="small" 
          startIcon={<Add fontSize="small" />} 
          onClick={handleAddDropdown}
          sx={{ 
            alignSelf: 'flex-start',
            marginTop: 1,
            padding: '4px 12px',
            textTransform: 'none',
            fontSize: '0.875rem',
            color: 'primary.main',
            '&:hover': {
              backgroundColor: 'rgba(25, 118, 210, 0.04)'
            }
          }}
          disabled={isLoading}
        >
          Add model
        </Button>
      </Box>
    </Box>
  );
}; 