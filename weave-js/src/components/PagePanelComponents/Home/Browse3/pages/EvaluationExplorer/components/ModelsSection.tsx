import React from 'react';
import { Add, Settings, Close } from '@mui/icons-material';
import IconButton from '@mui/material/IconButton';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Checkbox from '@mui/material/Checkbox';
import ListItemText from '@mui/material/ListItemText';
import Chip from '@mui/material/Chip';
import Button from '@mui/material/Button';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemSecondaryAction from '@mui/material/ListItemSecondaryAction';
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

  return (
    <Box sx={{ padding: 2 }}>
      <Box sx={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between', 
        marginBottom: 2 
      }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
          Model(s) {selectedModelIds.length > 0 && (
            <Chip 
              size="small" 
              label={selectedModelIds.length} 
              sx={{ 
                marginLeft: 1,
                height: 20,
                fontSize: '0.75rem'
              }} 
            />
          )}
        </Typography>
        <Button 
          size="small" 
          startIcon={<Add fontSize="small" />} 
          onClick={handleAddNewModel}
          sx={{ 
            minWidth: 'auto', 
            padding: '4px 12px',
            textTransform: 'none',
            fontSize: '0.875rem'
          }}
          disabled={isLoading}
        >
          New
        </Button>
      </Box>
      
      {/* Model Selection List */}
      <List sx={{ 
        maxHeight: 240, 
        overflowY: 'auto', 
        border: '1px solid #E0E0E0',
        borderRadius: 1,
        padding: 0.5
      }}>
        {models.map((model) => (
          <ListItem
            key={model.id}
            disablePadding
            dense
          >
            <ListItemButton
              role={undefined}
              onClick={() => handleModelToggle(model.id)}
              dense
              sx={{ py: 0.5 }}
            >
              <ListItemIcon sx={{ minWidth: 36 }}>
                <Checkbox
                  edge="start"
                  checked={selectedModelIds.includes(model.id)}
                  tabIndex={-1}
                  disableRipple
                  size="small"
                  disabled={isLoading}
                />
              </ListItemIcon>
              <ListItemText 
                primary={model.name}
                secondary={model.description}
                primaryTypographyProps={{ 
                  variant: 'body2',
                  fontSize: '0.875rem'
                }}
                secondaryTypographyProps={{ 
                  variant: 'caption',
                  fontSize: '0.75rem'
                }}
              />
              {selectedModelIds.includes(model.id) && onModelDetailOpen && (
                <ListItemSecondaryAction>
                  <IconButton 
                    edge="end" 
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation();
                      onModelDetailOpen(model.id);
                    }}
                    sx={{ 
                      '&:hover': { 
                        backgroundColor: 'rgba(0, 0, 0, 0.04)' 
                      } 
                    }}
                  >
                    <Settings fontSize="small" />
                  </IconButton>
                </ListItemSecondaryAction>
              )}
            </ListItemButton>
          </ListItem>
        ))}
      </List>

      {/* Selected Models Summary */}
      {selectedModelIds.length > 0 && (
        <Box sx={{ 
          marginTop: 2,
          padding: 1.5,
          backgroundColor: '#F5F5F5',
          borderRadius: 1,
          border: '1px solid #E0E0E0'
        }}>
          <Typography 
            variant="caption" 
            sx={{ 
              fontWeight: 600, 
              color: 'text.secondary',
              fontSize: '0.75rem'
            }}
          >
            Selected Models:
          </Typography>
          <Box sx={{ 
            display: 'flex', 
            flexWrap: 'wrap', 
            gap: 0.5, 
            marginTop: 1 
          }}>
            {selectedModelIds.map((modelId) => {
              const model = models.find(m => m.id === modelId) || { 
                id: modelId, 
                name: modelId 
              };
              
              return (
                <Chip
                  key={modelId}
                  label={model.name}
                  size="small"
                  onDelete={() => handleModelToggle(modelId)}
                  deleteIcon={<Close fontSize="small" />}
                  sx={{ 
                    fontSize: '0.75rem',
                    height: 24
                  }}
                />
              );
            })}
          </Box>
        </Box>
      )}
    </Box>
  );
}; 