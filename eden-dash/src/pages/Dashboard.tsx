import React from 'react';
import { Box, Typography, Paper, Grid } from '@mui/material';
import { CheckCircle as CheckCircleIcon, Error as ErrorIcon } from '@mui/icons-material';

const Dashboard: React.FC = () => {
  // Mock data - will be replaced with actual server status
  const serverStatus = {
    status: 'running',
    uptime: '2 hours',
    connectedServers: 3,
    pendingRequests: 2,
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Dashboard
      </Typography>
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              {serverStatus.status === 'running' ? (
                <CheckCircleIcon color="success" sx={{ mr: 1 }} />
              ) : (
                <ErrorIcon color="error" sx={{ mr: 1 }} />
              )}
              <Typography variant="h6">
                Server Status: {serverStatus.status}
              </Typography>
            </Box>
            <Typography variant="body1" gutterBottom>
              Uptime: {serverStatus.uptime}
            </Typography>
            <Typography variant="body1" gutterBottom>
              Connected MCP Servers: {serverStatus.connectedServers}
            </Typography>
            <Typography variant="body1">
              Pending Tool Requests: {serverStatus.pendingRequests}
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Quick Actions
            </Typography>
            <Typography variant="body1" paragraph>
              • View and edit configuration
            </Typography>
            <Typography variant="body1" paragraph>
              • Test MCP server connections
            </Typography>
            <Typography variant="body1" paragraph>
              • Monitor tool requests
            </Typography>
            <Typography variant="body1">
              • Access the playground
            </Typography>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Dashboard; 