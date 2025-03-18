import {Box, Typography} from '@mui/material';
import React, {useCallback, useRef, useState} from 'react';
import {toast} from 'react-toastify';

import {GLOBAL_COLORS} from '../../../../../common/util/colors';
import {Button} from '../../../../Button';
import {TextField} from '../../../../Form/TextField';
import {WaveLoader} from '../../../../Loaders/WaveLoader';
import {ResizableDrawer} from '../pages/common/ResizableDrawer';
import {
  CREATE_DATASET_ACTIONS,
  CreateDatasetProvider,
  useCreateDatasetContext,
} from './CreateDatasetDrawerContext';
import {validateDatasetName} from './datasetNameValidation';
import {EditableDatasetView} from './EditableDatasetView';

// Define typography style with Source Sans Pro font
const typographyStyle = {fontFamily: 'Source Sans Pro'};

interface CreateDatasetDrawerProps {
  open: boolean;
  onClose: () => void;
  onSaveDataset: (dataset: any) => void;
  isCreating?: boolean;
}

export const CreateDatasetDrawer: React.FC<CreateDatasetDrawerProps> = ({
  open,
  onClose,
  onSaveDataset,
  isCreating = false,
}) => {
  return (
    <CreateDatasetProvider onPublishDataset={onSaveDataset}>
      <CreateDatasetDrawerContent
        open={open}
        onClose={onClose}
        isCreating={isCreating}
      />
    </CreateDatasetProvider>
  );
};

const CreateDatasetDrawerContent: React.FC<{
  open: boolean;
  onClose: () => void;
  isCreating?: boolean;
}> = ({open, onClose, isCreating = false}) => {
  const {
    state,
    dispatch,
    parseCSVFile,
    handleCloseDrawer,
    handlePublishDataset,
    clearDataset,
  } = useCreateDatasetContext();

  const {datasetName, parsedData, isLoading, error, drawerWidth, isFullscreen} =
    state;

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);

  const handleNameChange = useCallback(
    (value: string) => {
      dispatch({
        type: CREATE_DATASET_ACTIONS.SET_DATASET_NAME,
        payload: value,
      });

      const validationResult = validateDatasetName(value);
      setNameError(validationResult.error);
    },
    [dispatch]
  );

  const handleFileChange = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (file) {
        await parseCSVFile(file);
      }
    },
    [parseCSVFile]
  );

  const handleUploadClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const wrappedOnClose = useCallback(() => {
    handleCloseDrawer();
    onClose();
  }, [handleCloseDrawer, onClose]);

  // Handle drag events
  const handleDragEnter = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    async (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);

      const files = e.dataTransfer.files;
      if (files.length > 0) {
        const file = files[0];
        if (file.type === 'text/csv' || file.name.endsWith('.csv')) {
          await parseCSVFile(file);
        } else {
          toast.error('Please upload a CSV file');
        }
      }
    },
    [parseCSVFile]
  );

  const handleToggleFullscreen = useCallback(() => {
    dispatch({
      type: CREATE_DATASET_ACTIONS.SET_IS_FULLSCREEN,
      payload: !isFullscreen,
    });
  }, [dispatch, isFullscreen]);

  const handleClearDataset = useCallback(() => {
    clearDataset();
  }, [clearDataset]);

  return (
    <ResizableDrawer
      open={open}
      onClose={wrappedOnClose}
      defaultWidth={isFullscreen ? window.innerWidth - 73 : drawerWidth}
      setWidth={width =>
        !isFullscreen &&
        dispatch({
          type: CREATE_DATASET_ACTIONS.SET_DRAWER_WIDTH,
          payload: width,
        })
      }
      headerContent={
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            py: 2,
            pl: 2,
            pr: 1,
            borderBottom: '1px solid',
            borderColor: 'divider',
          }}>
          <Typography variant="h6" sx={{...typographyStyle}}>
            Create New Dataset
          </Typography>
          <Box sx={{display: 'flex', gap: 1}}>
            {parsedData && (
              <Button
                onClick={handleClearDataset}
                variant="ghost"
                icon="delete"
                tooltip="Clear dataset"
              />
            )}
            <Button
              onClick={handleToggleFullscreen}
              variant="ghost"
              icon={isFullscreen ? 'minimize-mode' : 'full-screen-mode-expand'}
              tooltip={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
            />
            <Button
              onClick={wrappedOnClose}
              variant="ghost"
              icon="close"
              tooltip="Close"
            />
          </Box>
        </Box>
      }>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          overflow: 'hidden',
        }}>
        {isCreating || isLoading ? (
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              flex: 1,
            }}>
            <WaveLoader size="huge" />
          </Box>
        ) : (
          <>
            <Box
              sx={{
                p: 2,
                flexGrow: 1,
                overflow: 'auto',
                display: 'flex',
                flexDirection: 'column',
                minHeight: 0,
              }}>
              {error && (
                <Box
                  sx={{
                    mb: 2,
                    p: 2,
                    bgcolor: 'error.light',
                    borderRadius: 1,
                    color: 'error.dark',
                  }}>
                  <Typography sx={typographyStyle}>{error}</Typography>
                </Box>
              )}

              <Box sx={{mb: 4}}>
                <Typography
                  sx={{...typographyStyle, fontWeight: 600, mb: '8px'}}>
                  Dataset Name
                </Typography>
                <TextField
                  value={datasetName}
                  onChange={handleNameChange}
                  placeholder="Enter a name for your dataset"
                  errorState={nameError !== null}
                />
                {nameError && (
                  <Typography
                    sx={{
                      ...typographyStyle,
                      color: 'error.main',
                      fontSize: '0.875rem',
                      mt: 1,
                    }}>
                    {nameError}
                  </Typography>
                )}
                <Typography
                  sx={{
                    ...typographyStyle,
                    color: 'text.secondary',
                    fontSize: '0.875rem',
                    mt: 1,
                  }}>
                  Valid dataset names must start with a letter or number and can
                  only contain letters, numbers, hyphens, and underscores.
                </Typography>
              </Box>

              {!parsedData ? (
                <Box
                  sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    border: '2px dashed',
                    borderColor: isDragging
                      ? GLOBAL_COLORS.primary.string()
                      : GLOBAL_COLORS.outline.string(),
                    borderRadius: '8px',
                    p: 4,
                    flex: 1,
                    minHeight: '300px',
                    backgroundColor: isDragging
                      ? GLOBAL_COLORS.primary.alpha(0.05).string()
                      : 'transparent',
                    transition: 'all 0.2s ease',
                  }}
                  onDragEnter={handleDragEnter}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}>
                  <Typography variant="h6" sx={typographyStyle} gutterBottom>
                    {isDragging
                      ? 'Drop CSV file here'
                      : 'Upload or drag & drop a CSV file'}
                  </Typography>
                  <Typography
                    variant="body2"
                    sx={typographyStyle}
                    color="textSecondary"
                    align="center"
                    gutterBottom>
                    Drag and drop your CSV file here, or click below to browse.
                    Your file will be converted to a dataset that you can edit
                    before saving.
                  </Typography>
                  <Box sx={{mt: 2}}>
                    <input
                      accept=".csv"
                      id="csv-upload"
                      type="file"
                      style={{display: 'none'}}
                      onChange={handleFileChange}
                      ref={fileInputRef}
                    />
                    <Button onClick={handleUploadClick} variant="secondary">
                      Browse for CSV File
                    </Button>
                  </Box>
                  {isDragging && (
                    <Typography
                      variant="body2"
                      sx={{...typographyStyle, fontWeight: 'bold', mt: 2}}
                      color="primary">
                      Release to upload
                    </Typography>
                  )}
                </Box>
              ) : (
                <Box
                  sx={{
                    flex: 1,
                    display: 'flex',
                    flexDirection: 'column',
                    minHeight: 0,
                    overflow: 'hidden',
                  }}>
                  <EditableDatasetView
                    datasetObject={parsedData}
                    isEditing={true}
                    hideRemoveForAddedRows={false}
                    showAddRowButton={true}
                    hideIdColumn={true}
                    disableNewRowHighlight={true}
                  />
                </Box>
              )}
            </Box>

            {/* Publish button at the bottom */}
            {parsedData && (
              <Box
                sx={{
                  py: 2,
                  px: 0,
                  borderTop: '1px solid',
                  borderColor: 'divider',
                  backgroundColor: 'background.paper',
                  width: '100%',
                  display: 'flex',
                  flexShrink: 0,
                }}>
                <Button
                  onClick={handlePublishDataset}
                  variant="primary"
                  disabled={!parsedData || !datasetName || nameError !== null}
                  tooltip="Save and publish the dataset"
                  style={{
                    width: '100%',
                    margin: '0 16px',
                    borderRadius: '4px',
                  }}
                  twWrapperStyles={{
                    width: 'calc(100% - 32px)',
                    display: 'block',
                  }}>
                  Publish Dataset
                </Button>
              </Box>
            )}
          </>
        )}
      </Box>
    </ResizableDrawer>
  );
};
