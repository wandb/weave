import React, { useState, useEffect } from 'react';
import { 
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  RadioGroup,
  FormControlLabel,
  Radio,
  Box,
  Divider,
  Typography
} from '@mui/material';
import { ModelDetailPanelProps, ModelType, ModelConfiguration } from '../types';
import { useAvailableModels, useWeavePlaygroundModels, useFoundationModels } from '../queries';
import { DetailDrawer, DrawerSection, DrawerFormField } from './DetailDrawer';

export const ModelDetailPanel: React.FC<ModelDetailPanelProps> = ({ 
  modelId, 
  onClose 
}) => {
  const { models } = useAvailableModels();
  const { models: weavePlaygroundModels } = useWeavePlaygroundModels();
  const { models: foundationModels } = useFoundationModels();
  
  const model = models.find(m => m.id === modelId);
  
  // Initialize configuration state
  const [config, setConfig] = useState<ModelConfiguration>({
    type: 'weave-playground',
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

  // Load Weave Playground model configuration
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

  if (!modelId || !model) return null;

  return (
    <DetailDrawer
      open={!!modelId}
      onClose={onClose}
      title={`Configure ${model.name}`}
      width={500}
    >
      {/* Model Type Selection */}
      <DrawerSection>
        <DrawerFormField 
          label="Model Type" 
          description="Choose between Weave Playground models or define your own"
          required
        >
          <RadioGroup
            value={config.type}
            onChange={(e) => setConfig(prev => ({ ...prev, type: e.target.value as ModelType }))}
          >
            <FormControlLabel 
              value="weave-playground" 
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
              value="user-defined" 
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
      {config.type === 'weave-playground' && (
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
                  onChange={(e) => setConfig(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="e.g., Customer Support Agent"
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
                  onChange={(e) => setConfig(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="e.g., Handles customer inquiries with empathy and efficiency"
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
                    onChange={(e) => setConfig(prev => ({ ...prev, foundationModel: e.target.value }))}
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
                  onChange={(e) => setConfig(prev => ({ ...prev, systemTemplate: e.target.value }))}
                  placeholder="You are a helpful assistant..."
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
                  onChange={(e) => setConfig(prev => ({ ...prev, userTemplate: e.target.value }))}
                  placeholder="User query: {{query}}"
                  sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}
                />
              </DrawerFormField>
            </DrawerSection>
          )}
        </>
      )}

      {/* User Defined Configuration */}
      {config.type === 'user-defined' && (
        <DrawerSection>
          <Box sx={{ 
            padding: 3, 
            backgroundColor: '#F5F5F5', 
            borderRadius: 1,
            textAlign: 'center'
          }}>
            <Typography variant="body2" color="text.secondary">
              User-defined model configuration coming soon
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
              You'll be able to integrate your own model endpoints
            </Typography>
          </Box>
        </DrawerSection>
      )}
    </DetailDrawer>
  );
}; 