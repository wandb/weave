import React, { useState } from 'react';
import { Box, TextField, Button, Paper, Typography, Grid } from '@mui/material';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

const Playground: React.FC = () => {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);

  const handleSubmit = () => {
    if (!input.trim()) return;

    const newMessages: Message[] = [
      ...messages,
      { role: 'user' as const, content: input },
      { role: 'assistant' as const, content: 'This is a placeholder response. The actual response will come from the MCP server.' }
    ];
    setMessages(newMessages);
    setInput('');
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        MCP Playground
      </Typography>
      <Paper sx={{ p: 2, mb: 2 }}>
        <Grid container spacing={2}>
          <Grid item xs={12}>
            <TextField
              fullWidth
              multiline
              rows={4}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Enter your message..."
              variant="outlined"
            />
          </Grid>
          <Grid item xs={12}>
            <Button
              variant="contained"
              color="primary"
              onClick={handleSubmit}
              disabled={!input.trim()}
            >
              Send
            </Button>
          </Grid>
        </Grid>
      </Paper>
      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>
          Conversation
        </Typography>
        {messages.map((message, index) => (
          <Box key={index} sx={{ mb: 2 }}>
            <Typography variant="subtitle2" color="textSecondary">
              {message.role}
            </Typography>
            <Typography>{message.content}</Typography>
          </Box>
        ))}
      </Paper>
    </Box>
  );
};

export default Playground; 