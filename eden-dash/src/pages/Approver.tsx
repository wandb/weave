import React from 'react';
import { Box, Typography, Paper, Button, Grid, Chip } from '@mui/material';
import { Check as CheckIcon, Close as CloseIcon } from '@mui/icons-material';

interface ToolRequest {
  id: string;
  tool: string;
  arguments: Record<string, any>;
  user: string;
  timestamp: string;
}

const Approver: React.FC = () => {
  const [requests, setRequests] = React.useState<ToolRequest[]>([
    {
      id: '1',
      tool: 'search',
      arguments: { query: 'latest AI research' },
      user: 'user1',
      timestamp: new Date().toISOString(),
    },
    {
      id: '2',
      tool: 'execute',
      arguments: { command: 'ls -la' },
      user: 'user2',
      timestamp: new Date().toISOString(),
    },
  ]);

  const handleApprove = (id: string) => {
    // TODO: Implement approval logic
    console.log('Approved request:', id);
    setRequests(requests.filter(req => req.id !== id));
  };

  const handleDeny = (id: string) => {
    // TODO: Implement denial logic
    console.log('Denied request:', id);
    setRequests(requests.filter(req => req.id !== id));
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Tool Approver
      </Typography>
      <Paper sx={{ p: 3 }}>
        {requests.length === 0 ? (
          <Typography>No pending requests.</Typography>
        ) : (
          <Grid container spacing={2}>
            {requests.map((request) => (
              <Grid item xs={12} key={request.id}>
                <Paper sx={{ p: 2 }}>
                  <Grid container spacing={2} alignItems="center">
                    <Grid item xs={12} sm={3}>
                      <Typography variant="subtitle1" fontWeight="bold">
                        {request.tool}
                      </Typography>
                      <Chip 
                        label={request.user} 
                        size="small" 
                        color="primary" 
                        variant="outlined" 
                        sx={{ mt: 1 }}
                      />
                    </Grid>
                    <Grid item xs={12} sm={5}>
                      <Typography variant="body2" color="text.secondary">
                        Arguments:
                      </Typography>
                      <Typography variant="body1">
                        {JSON.stringify(request.arguments, null, 2)}
                      </Typography>
                    </Grid>
                    <Grid item xs={12} sm={4} sx={{ textAlign: 'right' }}>
                      <Button
                        variant="contained"
                        color="success"
                        startIcon={<CheckIcon />}
                        onClick={() => handleApprove(request.id)}
                        sx={{ mr: 1 }}
                      >
                        Approve
                      </Button>
                      <Button
                        variant="contained"
                        color="error"
                        startIcon={<CloseIcon />}
                        onClick={() => handleDeny(request.id)}
                      >
                        Deny
                      </Button>
                    </Grid>
                  </Grid>
                </Paper>
              </Grid>
            ))}
          </Grid>
        )}
      </Paper>
    </Box>
  );
};

export default Approver; 