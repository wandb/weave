import React, { useState } from 'react';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import FormControl from '@mui/material/FormControl';
import TextField from '@mui/material/TextField';
import { DrawerSection, DrawerFormField } from './DetailDrawer';

const MODEL_TEMPLATES = {
  'customer-support': {
    name: 'Customer Support Agent',
    description: 'Handles customer inquiries and provides helpful responses',
    systemTemplate: 'You are a helpful customer support agent...',
    userTemplate: 'Customer inquiry: {input}'
  },
  'code-reviewer': {
    name: 'Code Reviewer',
    description: 'Reviews code and provides constructive feedback',
    systemTemplate: 'You are an expert code reviewer...',
    userTemplate: 'Please review this code: {code}'
  },
  'text-summarizer': {
    name: 'Text Summarizer',
    description: 'Creates concise summaries of longer texts',
    systemTemplate: 'You are a text summarization expert...',
    userTemplate: 'Summarize this text: {text}'
  }
};

const FOUNDATION_MODELS = [
  { value: 'gpt-4', label: 'GPT-4 (OpenAI)', provider: 'OpenAI' },
  { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo (OpenAI)', provider: 'OpenAI' },
  { value: 'claude-3-opus', label: 'Claude 3 Opus (Anthropic)', provider: 'Anthropic' },
  { value: 'claude-3-sonnet', label: 'Claude 3 Sonnet (Anthropic)', provider: 'Anthropic' },
  { value: 'llama-3-70b', label: 'Llama 3 70B (Meta)', provider: 'Meta' },
  { value: 'gemini-pro', label: 'Gemini Pro (Google)', provider: 'Google' },
];

interface ModelDetailContentProps {
  modelId: string | null;
}

export const ModelDetailContent: React.FC<ModelDetailContentProps> = ({ modelId }) => {
  const [modelType, setModelType] = useState<'weave' | 'user'>('weave');
  const [selectedTemplate, setSelectedTemplate] = useState<string>('');
  const [config, setConfig] = useState({
    name: '',
    description: '',
    foundationModel: 'gpt-4',
    systemTemplate: '',
    userTemplate: ''
  });

  const handleTemplateChange = (templateId: string) => {
    setSelectedTemplate(templateId);
    if (templateId && templateId !== 'create-new') {
      const template = MODEL_TEMPLATES[templateId as keyof typeof MODEL_TEMPLATES];
      setConfig({
        ...config,
        name: template.name,
        description: template.description,
        systemTemplate: template.systemTemplate,
        userTemplate: template.userTemplate
      });
    }
  };

  if (!modelId) return null;

  return (
    <>
      <DrawerSection>
        <DrawerFormField
          label="Model Type"
          description="Choose between a pre-configured Weave model or define your own"
        >
          <FormControl fullWidth size="small">
            <Select
              value={modelType}
              onChange={(e) => setModelType(e.target.value as 'weave' | 'user')}
            >
              <MenuItem value="weave">Weave Playground</MenuItem>
              <MenuItem value="user">User Defined</MenuItem>
            </Select>
          </FormControl>
        </DrawerFormField>
      </DrawerSection>

      {modelType === 'weave' && (
        <>
          <DrawerSection>
            <DrawerFormField
              label="Pre-configured Models"
              description="Select from our curated model templates or create your own"
            >
              <FormControl fullWidth size="small">
                <Select
                  value={selectedTemplate}
                  onChange={(e) => handleTemplateChange(e.target.value)}
                  displayEmpty
                >
                  <MenuItem value="">
                    <em>Select a template</em>
                  </MenuItem>
                  {Object.entries(MODEL_TEMPLATES).map(([key, template]) => (
                    <MenuItem key={key} value={key}>
                      {template.name}
                    </MenuItem>
                  ))}
                  <MenuItem value="create-new">Create New</MenuItem>
                </Select>
              </FormControl>
            </DrawerFormField>
          </DrawerSection>

          <DrawerSection>
            <DrawerFormField
              label="Configuration"
              description="Customize the model settings"
            >
              <TextField
                fullWidth
                size="small"
                label="Name"
                value={config.name}
                onChange={(e) => setConfig({ ...config, name: e.target.value })}
                sx={{ marginBottom: 2 }}
              />
              
              <TextField
                fullWidth
                size="small"
                label="Description"
                multiline
                rows={2}
                value={config.description}
                onChange={(e) => setConfig({ ...config, description: e.target.value })}
                sx={{ marginBottom: 2 }}
              />

              <FormControl fullWidth size="small" sx={{ marginBottom: 2 }}>
                <DrawerFormField
                  label="Foundation Model"
                  description="Select the underlying AI model"
                >
                  <Select
                    value={config.foundationModel}
                    onChange={(e) => setConfig({ ...config, foundationModel: e.target.value })}
                  >
                    {FOUNDATION_MODELS.map(model => (
                      <MenuItem key={model.value} value={model.value}>
                        {model.label}
                      </MenuItem>
                    ))}
                  </Select>
                </DrawerFormField>
              </FormControl>

              <TextField
                fullWidth
                size="small"
                label="System Template"
                multiline
                rows={4}
                value={config.systemTemplate}
                onChange={(e) => setConfig({ ...config, systemTemplate: e.target.value })}
                sx={{ marginBottom: 2 }}
              />

              <TextField
                fullWidth
                size="small"
                label="User Template"
                multiline
                rows={4}
                value={config.userTemplate}
                onChange={(e) => setConfig({ ...config, userTemplate: e.target.value })}
              />
            </DrawerFormField>
          </DrawerSection>
        </>
      )}

      {modelType === 'user' && (
        <DrawerSection>
          <DrawerFormField
            label="User Defined Model"
            description="Configure your custom model integration"
          >
            <TextField
              fullWidth
              size="small"
              label="Model Endpoint"
              placeholder="https://api.example.com/v1/completions"
              sx={{ marginBottom: 2 }}
            />
            
            <TextField
              fullWidth
              size="small"
              label="API Key"
              type="password"
              placeholder="Enter your API key"
            />
          </DrawerFormField>
        </DrawerSection>
      )}
    </>
  );
}; 