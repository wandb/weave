import React, { useState } from 'react';
import { ChevronLeft, ChevronRight } from '@mui/icons-material';
import IconButton from '@mui/material/IconButton';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Divider from '@mui/material/Divider';
import { ConfigurationBarProps } from './types';
import { useAvailableDatasets, useAvailableModels, useAvailableScorers } from './queries';
import { DatasetSection, ModelsSection, ScorersSection, DetailDrawer, DrawerSection, ModelDetailContent } from './components';

export const ConfigurationBar: React.FC<ConfigurationBarProps> = ({
  selectedDatasetId,
  isDatasetEdited = false,
  onDatasetChange,
  selectedModelIds = [],
  onModelsChange,
  onModelDetailOpen
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedModelForDetail, setSelectedModelForDetail] = useState<string | null>(null);
  const { datasets, isLoading: datasetsLoading } = useAvailableDatasets();
  const { models, isLoading: modelsLoading } = useAvailableModels();
  const { scorers, isLoading: scorersLoading } = useAvailableScorers();

  // Handle model detail opening
  const handleModelDetailOpen = (modelId: string) => {
    setSelectedModelForDetail(modelId);
  };

  const handleModelDetailClose = () => {
    setSelectedModelForDetail(null);
  };

  const handleToggle = () => {
    setIsOpen(!isOpen);
  };

  const handleCloseDrawer = () => {
    setIsOpen(false);
    setSelectedModelForDetail(null);
  };

  // Create panels array for expanded drawer
  const panels = selectedModelForDetail ? [{
    id: 'model-detail',
    title: 'Model Configuration',
    content: <ModelDetailContent modelId={selectedModelForDetail} />,
    width: 400,
    onClose: handleModelDetailClose
  }] : [];

  return (
    <>
      {/* Toggle button */}
      <Box
        sx={{
          position: 'absolute',
          right: 0,
          top: 0,
          width: '48px',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          paddingTop: 1,
          zIndex: 8,
          backgroundColor: '#FAFAFA',
          borderLeft: '1px solid #E0E0E0',
          boxShadow: '-2px 0 4px rgba(0, 0, 0, 0.04)'
        }}
      >
        <IconButton
          onClick={handleToggle}
          sx={{ 
            '&:hover': {
              backgroundColor: 'rgba(0, 0, 0, 0.04)'
            }
          }}
        >
          {isOpen ? <ChevronRight /> : <ChevronLeft />}
        </IconButton>
        
        {/* Vertical text when closed */}
        {!isOpen && (
          <Typography
            sx={{
              writingMode: 'vertical-rl',
              transform: 'rotate(180deg)',
              fontSize: '0.875rem',
              fontWeight: 600,
              color: 'text.secondary',
              userSelect: 'none',
              marginTop: 2
            }}
          >
            Configuration
          </Typography>
        )}
      </Box>

      {/* Drawer */}
      <DetailDrawer
        open={isOpen}
        onClose={handleCloseDrawer}
        title="Configuration"
        width={300}
        side="right"
        showCloseButton={false}
        headerExtra={
          <IconButton
            size="small"
            onClick={handleCloseDrawer}
            sx={{ 
              '&:hover': { 
                backgroundColor: 'rgba(0, 0, 0, 0.04)' 
              } 
            }}
          >
            <ChevronRight />
          </IconButton>
        }
        panels={panels}
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
            onModelDetailOpen={handleModelDetailOpen}
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
    </>
  );
}; 