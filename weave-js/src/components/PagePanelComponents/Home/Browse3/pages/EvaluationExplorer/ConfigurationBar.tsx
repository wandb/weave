import React, { useState } from 'react';
import { ChevronLeft, ChevronRight } from '@mui/icons-material';
import IconButton from '@mui/material/IconButton';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Divider from '@mui/material/Divider';
import { ConfigurationBarProps } from './types';
import { useAvailableDatasets, useAvailableModels, useAvailableScorers } from './queries';
import { DatasetSection, ModelsSection, ScorersSection, DetailDrawer, DrawerSection } from './components';

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
    <DetailDrawer
      open={!isCollapsed}
      title="Configuration"
      width={300}
      side="left"
      showCloseButton={false}
      headerExtra={
        <IconButton
          size="small"
          onClick={() => setIsCollapsed(true)}
          sx={{ 
            '&:hover': { 
              backgroundColor: 'rgba(0, 0, 0, 0.04)' 
            } 
          }}
        >
          <ChevronLeft />
        </IconButton>
      }
    >
      <DrawerSection noPadding>
        <DatasetSection
          selectedDatasetId={selectedDatasetId}
          isDatasetEdited={isDatasetEdited}
          onDatasetChange={onDatasetChange}
          datasets={datasets}
          isLoading={datasetsLoading}
        />
      </DrawerSection>

      <Divider />

      <DrawerSection noPadding>
        <ModelsSection
          selectedModelIds={selectedModelIds}
          onModelsChange={onModelsChange}
          models={models}
          isLoading={modelsLoading}
          onModelDetailOpen={onModelDetailOpen}
        />
      </DrawerSection>

      <Divider />

      <DrawerSection noPadding>
        <ScorersSection
          scorers={scorers}
          isLoading={scorersLoading}
        />
      </DrawerSection>
    </DetailDrawer>
  );
}; 