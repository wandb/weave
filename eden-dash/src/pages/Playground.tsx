import React from 'react';
import { Box, Typography, Paper, TextField, Button, Grid } from '@mui/material';
import { Send as SendIcon } from '@mui/icons-material';

const Playground: React.FC = () => {
  const [input, setInput] = React.useState('');
  const [messages, setMessages] = React.useState<Array<{ role: 'user' | 'assistant', content: string }>>([]);

  const handleSend = () => {
    if (!input.trim()) return;

    const newMessages = [
      ...messages,
      { role: 'user', content: input },
      { role: 'assistant', content: 'This is a placeholder response. The actual response will come from the MCP server.' }
    ];
    setMessages(newMessages);
    setInput('');
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Playground
      </Typography>
      <Paper sx={{ p: 3, height: 'calc(100vh - 200px)', display: 'flex', flexDirection: 'column' }}>
        <Box sx={{ flexGrow: 1, overflow: 'auto', mb: 2 }}>
          {messages.map((message, index) => (
            <Paper
              key={index}
              sx={{
                p: 2,
                mb: 2,
                backgroundColor: message.role === 'user' ? 'primary.light' : 'grey.100',
                color: message.role === 'user' ? 'white' : 'text.primary',
              }}
            >
              <Typography>{message.content}</Typography>
            </Paper>
          ))}
        </Box>
        <Grid container spacing={2}>
          <Grid item xs>
            <TextField
              fullWidth
              variant="outlined"
              placeholder="Type your message..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSend()}
            />
          </Grid>
          <Grid item>
            <Button
              variant="contained"
              color="primary"
              endIcon={<SendIcon />}
              onClick={handleSend}
            >
              Send
            </Button>
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
};

export default Playground; 