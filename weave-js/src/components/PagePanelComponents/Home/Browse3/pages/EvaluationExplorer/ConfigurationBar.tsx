import React, { useState } from 'react';
import { 
  ChevronLeft, 
  ChevronRight,
  Star
} from '@mui/icons-material';
import IconButton from '@mui/material/IconButton';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Divider from '@mui/material/Divider';

// Placeholder hook for available datasets
const useAvailableDatasets = () => {
  // TODO: Replace with actual API call
  return {
    datasets: [
      { id: 'dataset-1', name: 'Customer Service v1' },
      { id: 'dataset-2', name: 'Customer Service v2' },
      { id: 'dataset-3', name: 'Product Reviews' },
      { id: 'dataset-4', name: 'Support Tickets' },
    ],
    isLoading: false
  };
};

interface ConfigurationBarProps {
  selectedDatasetId?: string;
  isDatasetEdited?: boolean;
  onDatasetChange?: (datasetId: string) => void;
}

export const ConfigurationBar: React.FC<ConfigurationBarProps> = ({
  selectedDatasetId,
  isDatasetEdited = false,
  onDatasetChange
}) => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const { datasets, isLoading } = useAvailableDatasets();

  const handleDatasetChange = (event: any) => {
    const value = event.target.value;
    if (onDatasetChange) {
      onDatasetChange(value);
    }
  };

  if (isCollapsed) {
    return (
      <Box
        sx={{
          width: '48px',
          height: '100%',
          borderRight: '1px solid #E0E0E0',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          paddingTop: 2,
          backgroundColor: '#FAFAFA'
        }}
      >
        <IconButton
          size="small"
          onClick={() => setIsCollapsed(false)}
          sx={{ marginBottom: 2 }}
        >
          <ChevronRight />
        </IconButton>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        width: '300px',
        height: '100%',
        borderRight: '1px solid #E0E0E0',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: '#FAFAFA'
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: 2,
          borderBottom: '1px solid #E0E0E0'
        }}
      >
        <Typography variant="h6" sx={{ fontWeight: 600 }}>
          Configuration
        </Typography>
        <IconButton
          size="small"
          onClick={() => setIsCollapsed(true)}
        >
          <ChevronLeft />
        </IconButton>
      </Box>

      {/* Dataset Section */}
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
            onChange={handleDatasetChange}
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
          <Typography 
            variant="caption" 
            sx={{ 
              color: '#FFA500',
              display: 'flex',
              alignItems: 'center',
              marginTop: 0.5
            }}
          >
            <Star sx={{ fontSize: 12, marginRight: 0.5 }} />
            Dataset has been edited
          </Typography>
        )}
      </Box>

      <Divider />

      {/* Models Section */}
      <Box sx={{ padding: 2 }}>
        <Typography variant="subtitle2" sx={{ marginBottom: 1, fontWeight: 600 }}>
          Model(s)
        </Typography>
        <Box sx={{ 
          padding: 2, 
          backgroundColor: '#F5F5F5', 
          borderRadius: 1,
          border: '1px dashed #CCC'
        }}>
          <Typography variant="body2" color="text.secondary">
            TODO: Model selection
          </Typography>
        </Box>
      </Box>

      <Divider />

      {/* Scorers Section */}
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
    </Box>
  );
}; 