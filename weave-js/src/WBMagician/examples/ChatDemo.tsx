import React from 'react';
import { Box, Container, Typography, Paper } from '@mui/material';
import { MagicianContextProvider, MagicianComponent } from '../index';

/**
 * Demo of the Magician chat interface.
 * Shows how to integrate the chat component into an app.
 */
export function ChatDemo() {
  return (
    <MagicianContextProvider service="demo">
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Typography variant="h4" gutterBottom>
          Magician Chat Interface Demo
        </Typography>
        
        <Typography variant="body1" paragraph color="text.secondary">
          Try typing a message or use @ to mention contexts and tools.
        </Typography>

        <Box sx={{ display: 'flex', gap: 3 }}>
          {/* Main content area */}
          <Paper sx={{ flex: 1, p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Your Application Content
            </Typography>
            <Typography variant="body2" color="text.secondary">
              This is where your main application would go. The chat interface
              works alongside your app to provide AI assistance.
            </Typography>
          </Paper>

          {/* Chat interface */}
          <MagicianComponent 
            projectId="demo-project"
            height="500px"
            placeholder="Ask me anything... Try @ to see available contexts"
          />
        </Box>

        <Box sx={{ mt: 4 }}>
          <Typography variant="h6" gutterBottom>
            Features to Try:
          </Typography>
          <ul>
            <li>Send a message to see streaming responses</li>
            <li>Type @ to see available contexts and tools</li>
            <li>Hover over messages to see the copy button</li>
            <li>Watch the "Active Session" indicator appear</li>
          </ul>
        </Box>
      </Container>
    </MagicianContextProvider>
  );
} 