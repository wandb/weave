import React from 'react';
import {
  Box,
  Typography,
  Paper,
  TextField,
  Button,
  Grid,
} from '@mui/material';

const Playground: React.FC = () => {
  const [input, setInput] = React.useState('');
  const [output, setOutput] = React.useState('');

  const handleSubmit = () => {
    // TODO: Implement MCP request handling
    console.log('Submitting request:', input);
    setOutput('Response will appear here...');
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Playground
      </Typography>
      <Paper sx={{ p: 3 }}>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <TextField
              fullWidth
              multiline
              rows={4}
              label="Input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
            />
          </Grid>
          <Grid item xs={12}>
            <Button
              variant="contained"
              color="primary"
              onClick={handleSubmit}
            >
              Submit
            </Button>
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              multiline
              rows={4}
              label="Output"
              value={output}
              InputProps={{
                readOnly: true,
              }}
            />
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
};

export default Playground; 