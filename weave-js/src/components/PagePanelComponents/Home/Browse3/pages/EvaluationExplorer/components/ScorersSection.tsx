import React from 'react';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { ScorersSectionProps } from '../types';

export const ScorersSection: React.FC<ScorersSectionProps> = ({
  selectedScorerIds,
  onScorersChange,
  scorers,
  isLoading
}) => {
  return (
    <Box sx={{ padding: 2 }}>
      <Typography variant="subtitle2" sx={{ marginBottom: 2, fontWeight: 600 }}>
        Scorer(s)
      </Typography>
      <Box sx={{ 
        padding: 2, 
        backgroundColor: '#FAFAFA', 
        borderRadius: 1,
        border: '1px solid #E0E0E0',
        display: 'flex',
        alignItems: 'center',
        gap: 1
      }}>
        <InfoOutlinedIcon sx={{ color: 'text.secondary', fontSize: 20 }} />
        <Typography 
          variant="body2" 
          color="text.secondary"
          sx={{ fontSize: '0.875rem' }}
        >
          Scorer selection coming soon
        </Typography>
      </Box>
    </Box>
  );
}; 