import React from 'react';
import {
  Box,
  Typography,
  Paper,
  List,
  ListItem,
  ListItemText,
  Button,
  Grid,
} from '@mui/material';

interface ApprovalRequest {
  id: string;
  type: string;
  description: string;
  timestamp: string;
}

const Approver: React.FC = () => {
  const [requests, setRequests] = React.useState<ApprovalRequest[]>([]);

  const handleApprove = (id: string) => {
    // TODO: Implement approval handling
    console.log('Approving request:', id);
    setRequests(requests.filter(req => req.id !== id));
  };

  const handleReject = (id: string) => {
    // TODO: Implement rejection handling
    console.log('Rejecting request:', id);
    setRequests(requests.filter(req => req.id !== id));
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Approval Requests
      </Typography>
      <Paper sx={{ p: 3 }}>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            {requests.length === 0 ? (
              <Typography variant="body1" color="text.secondary">
                No pending approval requests
              </Typography>
            ) : (
              <List>
                {requests.map((request) => (
                  <ListItem
                    key={request.id}
                    secondaryAction={
                      <Box>
                        <Button
                          color="primary"
                          onClick={() => handleApprove(request.id)}
                          sx={{ mr: 1 }}
                        >
                          Approve
                        </Button>
                        <Button
                          color="error"
                          onClick={() => handleReject(request.id)}
                        >
                          Reject
                        </Button>
                      </Box>
                    }
                  >
                    <ListItemText
                      primary={request.type}
                      secondary={
                        <>
                          <Typography component="span" variant="body2">
                            {request.description}
                          </Typography>
                          <br />
                          <Typography component="span" variant="caption" color="text.secondary">
                            {request.timestamp}
                          </Typography>
                        </>
                      }
                    />
                  </ListItem>
                ))}
              </List>
            )}
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
};

export default Approver; 