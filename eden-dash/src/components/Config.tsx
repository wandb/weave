import React from 'react';
import {
  Box,
  Typography,
  Paper,
  TextField,
  Button,
  Grid,
} from '@mui/material';

const Config: React.FC = () => {
  const [config, setConfig] = React.useState({
    servers: [],
    tools: [],
    resources: [],
    prompts: [],
    sampling: {},
  });

  const handleSave = () => {
    // TODO: Implement save functionality
    console.log('Saving config:', config);
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Configuration
      </Typography>
      <Paper sx={{ p: 3 }}>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <TextField
              fullWidth
              multiline
              rows={10}
              label="Configuration"
              value={JSON.stringify(config, null, 2)}
              onChange={(e) => {
                try {
                  setConfig(JSON.parse(e.target.value));
                } catch (error) {
                  // Invalid JSON, ignore
                }
              }}
            />
          </Grid>
          <Grid item xs={12}>
            <Button
              variant="contained"
              color="primary"
              onClick={handleSave}
            >
              Save Configuration
            </Button>
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
};

export default Config; 