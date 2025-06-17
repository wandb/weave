import React, { useState } from 'react';
import { 
  ChevronLeft, 
  ChevronRight,
  Star,
  ExpandMore,
  Add,
  Delete
} from '@mui/icons-material';
import IconButton from '@mui/material/IconButton';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Divider from '@mui/material/Divider';
import Checkbox from '@mui/material/Checkbox';
import ListItemText from '@mui/material/ListItemText';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import Chip from '@mui/material/Chip';
import Button from '@mui/material/Button';
import { ConfigurationBarProps } from './types';
import { useAvailableDatasets, useAvailableModels, useAvailableScorers } from './queries';
import { DatasetSection, ModelsSection, ScorersSection } from './components';

export const ConfigurationBar: React.FC<ConfigurationBarProps> = ({
  selectedDatasetId,
  isDatasetEdited = false,
  onDatasetChange,
  selectedModelIds = [],
  onModelsChange,
  onModelDetailOpen
}) => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const { datasets, isLoading: datasetsLoading } = useAvailableDatasets();
  const { models, isLoading: modelsLoading } = useAvailableModels();
  const { scorers, isLoading: scorersLoading } = useAvailableScorers();

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
          backgroundColor: '#FAFAFA',
          paddingTop: 1
        }}
      >
        <IconButton
          onClick={() => setIsCollapsed(false)}
          sx={{ 
            marginBottom: 2,
            '&:hover': {
              backgroundColor: 'rgba(0, 0, 0, 0.04)'
            }
          }}
        >
          <ChevronRight />
        </IconButton>
        
        {/* Vertical text */}
        <Typography
          sx={{
            writingMode: 'vertical-rl',
            transform: 'rotate(180deg)',
            fontSize: '0.875rem',
            fontWeight: 600,
            color: 'text.secondary',
            userSelect: 'none'
          }}
        >
          Configuration
        </Typography>
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
        backgroundColor: '#FAFAFA',
        overflow: 'hidden'
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

      {/* Scrollable content area */}
      <Box sx={{ 
        flex: 1, 
        overflowY: 'auto',
        overflowX: 'hidden'
      }}>
        <DatasetSection
          selectedDatasetId={selectedDatasetId}
          isDatasetEdited={isDatasetEdited}
          onDatasetChange={onDatasetChange}
          datasets={datasets}
          isLoading={datasetsLoading}
        />

        <Divider />

        <ModelsSection
          selectedModelIds={selectedModelIds}
          onModelsChange={onModelsChange}
          models={models}
          isLoading={modelsLoading}
          onModelDetailOpen={onModelDetailOpen}
        />

        <Divider />

        <ScorersSection
          scorers={scorers}
          isLoading={scorersLoading}
        />
      </Box>
    </Box>
  );
}; 