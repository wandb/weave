import React, { useState } from 'react';
import { Box, Button, TextField, Typography, Paper } from '@mui/material';
import {
  useMagician,
  useRespond,
  useRegisterComponentContext,
  useRegisterComponentTool,
} from '../index';

/**
 * Demo component showing how to use the Magician toolkit
 */
export const MagicianDemoComponent: React.FC = () => {
  const [modelName, setModelName] = useState('gpt-4o');
  const [prompt, setPrompt] = useState('');
  const [generatedText, setGeneratedText] = useState('');

  // Register component context
  useRegisterComponentContext({
    key: 'demo-component-state',
    data: {
      currentModel: modelName,
      currentPrompt: prompt,
      generatedText,
    },
    autoInclude: true,
    displayName: 'Demo Component State',
    description: 'Current state of the demo component',
  });

  // Register a tool that the AI can use
  const updateGeneratedText = (text: string) => {
    setGeneratedText(text);
    return { success: true, text };
  };

  useRegisterComponentTool({
    key: 'update-generated-text',
    tool: updateGeneratedText,
    displayName: 'Update Generated Text',
    description: 'Updates the generated text field in the demo component',
    autoExecutable: true,
    schema: {
      type: 'object',
      properties: {
        text: {
          type: 'string',
          description: 'The text to set in the generated text field',
        },
      },
      required: ['text'],
    },
  });

  // Use the respond hook for a specific query
  const generateDescription = useRespond({
    input: `Generate a creative description for: ${prompt}`,
    modelName,
  });

  // Direct response example
  const magician = useMagician();
  const [directResponse, setDirectResponse] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleDirectQuery = async () => {
    setIsLoading(true);
    try {
      const response = await magician.respond({
        input: 'What can you help me with?',
        modelName,
      });

      let accumulated = '';
      for await (const chunk of response.getStream()) {
        if (chunk.type === 'content') {
          accumulated += chunk.content || '';
          setDirectResponse(accumulated);
        }
      }
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Paper sx={{ p: 3, m: 2 }}>
      <Typography variant="h5" gutterBottom>
        Magician Demo Component
      </Typography>

      <Box sx={{ mb: 3 }}>
        <TextField
          label="Model"
          value={modelName}
          onChange={(e) => setModelName(e.target.value)}
          select
          fullWidth
          sx={{ mb: 2 }}
        >
          <option value="gpt-4o">GPT-4</option>
          <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
        </TextField>

        <TextField
          label="Prompt"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          multiline
          rows={3}
          fullWidth
          sx={{ mb: 2 }}
          placeholder="Enter something to generate a description for..."
        />

        <Button
          variant="contained"
          onClick={() => generateDescription.refetch()}
          disabled={generateDescription.loading || !prompt}
        >
          Generate Description
        </Button>
      </Box>

      {generateDescription.loading && (
        <Typography>Generating...</Typography>
      )}

      {generateDescription.error && (
        <Typography color="error">
          Error: {generateDescription.error.message}
        </Typography>
      )}

      {generateDescription.data && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="h6">Generated Description:</Typography>
          <Typography>{generateDescription.data.content}</Typography>
        </Box>
      )}

      <Box sx={{ mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Direct API Example
        </Typography>
        <Button
          variant="outlined"
          onClick={handleDirectQuery}
          disabled={isLoading}
        >
          Ask "What can you help me with?"
        </Button>
        {directResponse && (
          <Typography sx={{ mt: 2 }}>{directResponse}</Typography>
        )}
      </Box>

      <Box>
        <Typography variant="h6" gutterBottom>
          Generated Text (Tool Example)
        </Typography>
        <TextField
          value={generatedText}
          onChange={(e) => setGeneratedText(e.target.value)}
          multiline
          rows={3}
          fullWidth
          placeholder="The AI can update this field using the registered tool..."
        />
        <Typography variant="caption" display="block" sx={{ mt: 1 }}>
          Try asking the AI to "update the generated text field with a haiku about coding"
        </Typography>
      </Box>
    </Paper>
  );
}; 