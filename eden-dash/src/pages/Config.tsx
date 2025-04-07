import React from 'react';
import { Box, Typography, Paper, TextField, Button, Grid } from '@mui/material';
import { Save as SaveIcon } from '@mui/icons-material';

const Config: React.FC = () => {
  const [config, setConfig] = React.useState('');

  const handleSave = () => {
    // TODO: Implement saving configuration to eden.json
    console.log('Saving configuration:', config);
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
              rows={20}
              variant="outlined"
              label="eden.json"
              value={config}
              onChange={(e) => setConfig(e.target.value)}
              sx={{ fontFamily: 'monospace' }}
            />
          </Grid>
          <Grid item xs={12}>
            <Button
              variant="contained"
              color="primary"
              startIcon={<SaveIcon />}
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