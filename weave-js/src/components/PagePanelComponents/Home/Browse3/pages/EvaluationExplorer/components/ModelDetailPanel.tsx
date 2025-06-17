import React from 'react';
import { 
  Box, 
  Typography, 
  IconButton, 
  Divider,
  TextField,
  Slider,
  FormControl,
  FormLabel,
  Paper
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { ModelDetailPanelProps } from '../types';
import { useAvailableModels } from '../queries';

export const ModelDetailPanel: React.FC<ModelDetailPanelProps> = ({ 
  modelId, 
  onClose 
}) => {
  const { models } = useAvailableModels();
  const model = models.find(m => m.id === modelId);

  if (!modelId || !model) return null;

  return (
    <Paper
      elevation={3}
      sx={{
        position: 'absolute',
        top: 0,
        right: 0,
        width: '400px',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: 'white',
        borderLeft: '1px solid #E0E0E0',
        zIndex: 10,
        transform: modelId ? 'translateX(0)' : 'translateX(100%)',
        transition: 'transform 0.3s ease-in-out'
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
          Configure {model.name}
        </Typography>
        <IconButton
          size="small"
          onClick={onClose}
          sx={{ 
            '&:hover': { 
              backgroundColor: 'rgba(0, 0, 0, 0.04)' 
            } 
          }}
        >
          <CloseIcon />
        </IconButton>
      </Box>

      {/* Content */}
      <Box sx={{ 
        flex: 1, 
        overflowY: 'auto', 
        padding: 3,
        display: 'flex',
        flexDirection: 'column',
        gap: 3
      }}>
        <Box>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            {model.description}
          </Typography>
        </Box>

        <Divider />

        {/* Temperature */}
        <FormControl fullWidth>
          <FormLabel sx={{ fontSize: '0.875rem', fontWeight: 600, mb: 1 }}>
            Temperature
          </FormLabel>
          <Slider
            defaultValue={0.7}
            min={0}
            max={2}
            step={0.1}
            valueLabelDisplay="auto"
            marks={[
              { value: 0, label: '0' },
              { value: 1, label: '1' },
              { value: 2, label: '2' }
            ]}
            sx={{ mb: 2 }}
          />
          <Typography variant="caption" color="text.secondary">
            Controls randomness: lowering results in less random completions
          </Typography>
        </FormControl>

        {/* Max Tokens */}
        <FormControl fullWidth>
          <FormLabel sx={{ fontSize: '0.875rem', fontWeight: 600, mb: 1 }}>
            Max Tokens
          </FormLabel>
          <TextField
            type="number"
            defaultValue={1000}
            size="small"
            fullWidth
            inputProps={{ min: 1, max: 4096 }}
          />
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
            Maximum number of tokens to generate
          </Typography>
        </FormControl>

        {/* System Prompt */}
        <FormControl fullWidth>
          <FormLabel sx={{ fontSize: '0.875rem', fontWeight: 600, mb: 1 }}>
            System Prompt
          </FormLabel>
          <TextField
            multiline
            rows={4}
            defaultValue="You are a helpful assistant."
            size="small"
            fullWidth
          />
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
            Instructions to guide the model's behavior
          </Typography>
        </FormControl>

        {/* API Endpoint */}
        <FormControl fullWidth>
          <FormLabel sx={{ fontSize: '0.875rem', fontWeight: 600, mb: 1 }}>
            API Endpoint
          </FormLabel>
          <TextField
            defaultValue="https://api.openai.com/v1/chat/completions"
            size="small"
            fullWidth
          />
        </FormControl>

        {/* Placeholder for more settings */}
        <Box sx={{ 
          mt: 'auto', 
          pt: 3, 
          borderTop: '1px solid #E0E0E0' 
        }}>
          <Typography variant="caption" color="text.secondary">
            Additional model-specific settings can be configured here
          </Typography>
        </Box>
      </Box>
    </Paper>
  );
}; 