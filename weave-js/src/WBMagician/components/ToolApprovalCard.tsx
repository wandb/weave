import React, {FC, useState} from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  IconButton,
  Collapse,
  TextField,
  alpha,
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  Close as CloseIcon,
  Edit as EditIcon,
  Check as CheckIcon,
} from '@mui/icons-material';

import type { ToolCall, RegisteredTool } from '../types';

interface ToolApprovalCardProps {
  toolCall: ToolCall;
  tool: RegisteredTool;
  onApprove: (modifiedArgs?: Record<string, any>) => void;
  onReject: () => void;
}

export const ToolApprovalCard: FC<ToolApprovalCardProps> = ({
  toolCall,
  tool,
  onApprove,
  onReject,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editedArgs, setEditedArgs] = useState(
    JSON.stringify(toolCall.arguments, null, 2)
  );

  const handleApprove = () => {
    if (isEditing) {
      try {
        const modifiedArgs = JSON.parse(editedArgs);
        onApprove(modifiedArgs);
      } catch (error) {
        console.error('Invalid JSON:', error);
        // Show error to user
      }
    } else {
      onApprove();
    }
  };

  return (
    <Card
      sx={{
        maxWidth: 400,
        bgcolor: alpha('#2196F3', 0.05),
        border: 1,
        borderColor: alpha('#2196F3', 0.3),
      }}
    >
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', mb: 2 }}>
          <Box sx={{ flex: 1 }}>
            <Typography variant="subtitle2" sx={{ color: '#2196F3', fontWeight: 600 }}>
              Tool Request
            </Typography>
            <Typography variant="h6" sx={{ mt: 0.5 }}>
              {tool.displayName}
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5 }}>
              {tool.description}
            </Typography>
          </Box>
          
          <IconButton size="small" onClick={() => setIsEditing(!isEditing)}>
            <EditIcon fontSize="small" />
          </IconButton>
        </Box>

        <Collapse in={isEditing || Object.keys(toolCall.arguments).length > 0}>
          <Box sx={{ mb: 2 }}>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              Arguments:
            </Typography>
            {isEditing ? (
              <TextField
                fullWidth
                multiline
                rows={4}
                value={editedArgs}
                onChange={(e) => setEditedArgs(e.target.value)}
                sx={{
                  mt: 1,
                  '& .MuiOutlinedInput-root': {
                    fontFamily: 'monospace',
                    fontSize: '0.875rem',
                  },
                }}
              />
            ) : (
              <Box
                sx={{
                  mt: 1,
                  p: 1.5,
                  bgcolor: 'background.paper',
                  borderRadius: 1,
                  fontFamily: 'monospace',
                  fontSize: '0.875rem',
                }}
              >
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                  {JSON.stringify(toolCall.arguments, null, 2)}
                </pre>
              </Box>
            )}
          </Box>
        </Collapse>

        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="contained"
            size="small"
            startIcon={isEditing ? <CheckIcon /> : <PlayIcon />}
            onClick={handleApprove}
            sx={{
              bgcolor: '#2196F3',
              '&:hover': {
                bgcolor: '#1976D2',
              },
            }}
          >
            {isEditing ? 'Save & Run' : 'Run Tool'}
          </Button>
          <Button
            variant="outlined"
            size="small"
            startIcon={<CloseIcon />}
            onClick={onReject}
            sx={{
              borderColor: 'divider',
              color: 'text.secondary',
            }}
          >
            Cancel
          </Button>
        </Box>
      </CardContent>
    </Card>
  );
}; 