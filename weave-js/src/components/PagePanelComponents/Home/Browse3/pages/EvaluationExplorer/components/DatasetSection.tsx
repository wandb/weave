import React from 'react';
import { Star } from '@mui/icons-material';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Divider from '@mui/material/Divider';
import { DatasetSectionProps } from '../types';

export const DatasetSection: React.FC<DatasetSectionProps> = ({
  selectedDatasetId,
  isDatasetEdited = false,
  onDatasetChange,
  datasets,
  isLoading
}) => {
  const handleChange = (event: any) => {
    const value = event.target.value;
    if (onDatasetChange) {
      onDatasetChange(value);
    }
  };

  return (
    <Box sx={{ padding: 2 }}>
      <Typography variant="subtitle2" sx={{ marginBottom: 1, fontWeight: 600 }}>
        Dataset
      </Typography>
      <FormControl fullWidth size="small">
        <InputLabel id="dataset-select-label">
          {isDatasetEdited ? 'Dataset (edited)' : 'Select Dataset'}
        </InputLabel>
        <Select
          labelId="dataset-select-label"
          value={selectedDatasetId || ''}
          label={isDatasetEdited ? 'Dataset (edited)' : 'Select Dataset'}
          onChange={handleChange}
          disabled={isLoading}
          endAdornment={
            isDatasetEdited ? (
              <Star 
                sx={{ 
                  color: '#FFA500', 
                  fontSize: 16, 
                  marginRight: 2 
                }} 
              />
            ) : null
          }
        >
          <MenuItem value="create-new">
            <em>Create New Dataset</em>
          </MenuItem>
          <Divider />
          {datasets.map((dataset) => (
            <MenuItem key={dataset.id} value={dataset.id}>
              {dataset.name}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
      {isDatasetEdited && (
        <Box
          sx={{ 
            display: 'flex',
            alignItems: 'center',
            marginTop: 1,
            padding: '4px 8px',
            backgroundColor: 'rgba(255, 165, 0, 0.1)',
            borderRadius: 1,
            border: '1px solid rgba(255, 165, 0, 0.3)'
          }}
        >
          <Star sx={{ fontSize: 14, marginRight: 0.5, color: '#FFA500' }} />
          <Typography 
            variant="caption" 
            sx={{ 
              color: '#FF8C00',
              fontSize: '0.75rem',
              fontWeight: 500
            }}
          >
            Dataset has been edited
          </Typography>
        </Box>
      )}
    </Box>
  );
}; 