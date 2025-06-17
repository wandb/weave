import React from 'react';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import { ScorersSectionProps } from '../types';

export const ScorersSection: React.FC<ScorersSectionProps> = ({
  selectedScorerIds,
  onScorersChange,
  scorers,
  isLoading
}) => {
  return (
    <Box sx={{ padding: 2 }}>
      <Typography variant="subtitle2" sx={{ marginBottom: 1, fontWeight: 600 }}>
        Scorer(s)
      </Typography>
      <Box sx={{ 
        padding: 2, 
        backgroundColor: '#F5F5F5', 
        borderRadius: 1,
        border: '1px dashed #CCC'
      }}>
        <Typography variant="body2" color="text.secondary">
          TODO: Scorer selection
        </Typography>
      </Box>
    </Box>
  );
}; 