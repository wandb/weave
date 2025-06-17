import React, { useState, useEffect } from 'react';
import { 
  TextField,
  Select,
  MenuItem,
  FormControl,
  RadioGroup,
  FormControlLabel,
  Radio,
  Box,
  Divider,
  Typography
} from '@mui/material';
import { ModelType, ModelConfiguration } from '../types';
import { useAvailableModels, useWeavePlaygroundModels, useFoundationModels } from '../queries';
import { DrawerSection, DrawerFormField } from './DetailDrawer';

// Constants for better maintainability
const MODEL_TYPES = {
  WEAVE_PLAYGROUND: 'weave-playground' as ModelType,
  USER_DEFINED: 'user-defined' as ModelType
};

const PLACEHOLDERS = {
  MODEL_NAME: 'e.g., Customer Support Agent',
  MODEL_DESCRIPTION: 'e.g., Handles customer inquiries with empathy and efficiency',
  SYSTEM_TEMPLATE: 'You are a helpful assistant...',
  USER_TEMPLATE: 'User query: {{query}}',
  MODEL_ENDPOINT: 'https://api.example.com/v1/completions',
  API_KEY: 'Enter your API key'
};

interface ModelDetailContentProps {
  modelId: string | null;
}

export const ModelDetailContent: React.FC<ModelDetailContentProps> = ({ modelId }) => {
  const { models } = useAvailableModels();
  const { models: weavePlaygroundModels } = useWeavePlaygroundModels();
  const { models: foundationModels } = useFoundationModels();
  
  const model = models.find(m => m.id === modelId);
  
  // Initialize configuration state
  const [config, setConfig] = useState<ModelConfiguration>({
    type: MODEL_TYPES.WEAVE_PLAYGROUND,
    weavePlaygroundId: '',
    name: model?.name || '',
    description: model?.description || '',
    foundationModel: '',
    systemTemplate: '',
    userTemplate: ''
  });

  // Update config when model changes
  useEffect(() => {
    if (model) {
      setConfig(prev => ({
        ...prev,
        name: model.name,
        description: model.description
      }));
    }
  }, [model]);

  // Handle Weave Playground model selection
  const handleWeavePlaygroundSelect = (playgroundId: string) => {
    if (playgroundId === 'create-new') {
      setConfig(prev => ({
        ...prev,
        weavePlaygroundId: playgroundId,
        foundationModel: '',
        systemTemplate: '',
        userTemplate: ''
      }));
    } else {
      const playgroundModel = weavePlaygroundModels.find(m => m.id === playgroundId);
      if (playgroundModel) {
        setConfig(prev => ({
          ...prev,
          weavePlaygroundId: playgroundId,
          name: playgroundModel.name,
          description: playgroundModel.description,
          foundationModel: playgroundModel.foundationModel,
          systemTemplate: playgroundModel.systemTemplate,
          userTemplate: playgroundModel.userTemplate
        }));
      }
    }
  };

  // Helper function to update config
  const updateConfig = (updates: Partial<ModelConfiguration>) => {
    setConfig(prev => ({ ...prev, ...updates }));
  };

  if (!modelId) return null;

  return (
    <>
      {/* Model Type Selection */}
      <DrawerSection>
        <DrawerFormField 
          label="Model Type" 
          description="Choose between Weave Playground models or define your own"
          required
        >
          <RadioGroup
            value={config.type}
            onChange={(e) => updateConfig({ type: e.target.value as ModelType })}
          >
            <FormControlLabel 
              value={MODEL_TYPES.WEAVE_PLAYGROUND} 
              control={<Radio size="small" />} 
              label={
                <Box>
                  <Typography variant="body2">Weave Playground</Typography>
                  <Typography variant="caption" color="text.secondary">
                    Use pre-configured models or create new ones
                  </Typography>
                </Box>
              }
              sx={{ mb: 1 }}
            />
            <FormControlLabel 
              value={MODEL_TYPES.USER_DEFINED} 
              control={<Radio size="small" />} 
              label={
                <Box>
                  <Typography variant="body2">User Defined</Typography>
                  <Typography variant="caption" color="text.secondary">
                    Bring your own model implementation
                  </Typography>
                </Box>
              }
            />
          </RadioGroup>
        </DrawerFormField>
      </DrawerSection>

      {/* Weave Playground Configuration */}
      {config.type === MODEL_TYPES.WEAVE_PLAYGROUND && (
        <>
          <DrawerSection>
            <DrawerFormField 
              label="Weave Playground Model" 
              description="Select a pre-configured model or create a new one"
              required
            >
              <FormControl fullWidth size="small">
                <Select
                  value={config.weavePlaygroundId || ''}
                  onChange={(e) => handleWeavePlaygroundSelect(e.target.value)}
                >
                  <MenuItem value="">
                    <em>Select a model</em>
                  </MenuItem>
                  <MenuItem value="create-new">
                    <em>Create New Model</em>
                  </MenuItem>
                  <Divider />
                  {weavePlaygroundModels.map((pm) => (
                    <MenuItem key={pm.id} value={pm.id}>
                      <Box>
                        <Typography variant="body2">{pm.name}</Typography>
                        <Typography variant="caption" color="text.secondary">
                          {pm.description}
                        </Typography>
                      </Box>
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </DrawerFormField>
          </DrawerSection>

          {/* Model Configuration Fields */}
          {(config.weavePlaygroundId === 'create-new' || config.weavePlaygroundId) && (
            <DrawerSection>
              <DrawerFormField 
                label="Name" 
                description="A short, descriptive name for your model"
                required
              >
                <TextField
                  fullWidth
                  size="small"
                  value={config.name}
                  onChange={(e) => updateConfig({ name: e.target.value })}
                  placeholder={PLACEHOLDERS.MODEL_NAME}
                />
              </DrawerFormField>

              <DrawerFormField 
                label="Description" 
                description="Explain what this model does"
              >
                <TextField
                  fullWidth
                  size="small"
                  multiline
                  rows={2}
                  value={config.description}
                  onChange={(e) => updateConfig({ description: e.target.value })}
                  placeholder={PLACEHOLDERS.MODEL_DESCRIPTION}
                />
              </DrawerFormField>

              <DrawerFormField 
                label="Foundation Model" 
                description="Select the base language model"
                required
              >
                <FormControl fullWidth size="small">
                  <Select
                    value={config.foundationModel || ''}
                    onChange={(e) => updateConfig({ foundationModel: e.target.value })}
                  >
                    <MenuItem value="">
                      <em>Select foundation model</em>
                    </MenuItem>
                    {foundationModels.map((fm) => (
                      <MenuItem key={fm.id} value={fm.id}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                          <Typography variant="body2">{fm.name}</Typography>
                          <Typography variant="caption" color="text.secondary">
                            {fm.provider}
                          </Typography>
                        </Box>
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </DrawerFormField>

              <DrawerFormField 
                label="System Template" 
                description="Instructions that define the model's behavior and personality"
              >
                <TextField
                  fullWidth
                  size="small"
                  multiline
                  rows={4}
                  value={config.systemTemplate}
                  onChange={(e) => updateConfig({ systemTemplate: e.target.value })}
                  placeholder={PLACEHOLDERS.SYSTEM_TEMPLATE}
                  sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}
                />
              </DrawerFormField>

              <DrawerFormField 
                label="User Template" 
                description="Template for formatting user inputs. Use {{variable}} for placeholders"
              >
                <TextField
                  fullWidth
                  size="small"
                  multiline
                  rows={4}
                  value={config.userTemplate}
                  onChange={(e) => updateConfig({ userTemplate: e.target.value })}
                  placeholder={PLACEHOLDERS.USER_TEMPLATE}
                  sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}
                />
              </DrawerFormField>
            </DrawerSection>
          )}
        </>
      )}

      {/* User Defined Configuration */}
      {config.type === MODEL_TYPES.USER_DEFINED && (
        <DrawerSection>
          <DrawerFormField
            label="User Defined Model"
            description="Configure your custom model integration"
          >
            <TextField
              fullWidth
              size="small"
              label="Model Endpoint"
              placeholder={PLACEHOLDERS.MODEL_ENDPOINT}
              sx={{ marginBottom: 2 }}
            />
            
            <TextField
              fullWidth
              size="small"
              label="API Key"
              type="password"
              placeholder={PLACEHOLDERS.API_KEY}
            />
          </DrawerFormField>
        </DrawerSection>
      )}
    </>
  );
}; 