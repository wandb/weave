import {Box, Typography} from '@mui/material';
import React, {useCallback, useRef, useState} from 'react';
import {toast} from 'react-toastify';

import {
  MOON_300,
  TEAL_300,
  TEAL_500,
} from '../../../../../common/css/color.styles';
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
import {SUPPORTED_FILE_EXTENSIONS} from './fileFormats';

// Define typography style with Source Sans Pro font
const typographyStyle = {fontFamily: 'Source Sans Pro'};

interface CreateDatasetDrawerProps {
  open: boolean;
  onClose: () => void;
  onSaveDataset: (name: string, rows: any[]) => void;
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
    parseFile,
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
        await parseFile(file);
      }
    },
    [parseFile]
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
        const fileExtension = file.name.split('.').pop()?.toLowerCase();
        if (SUPPORTED_FILE_EXTENSIONS.includes(fileExtension as any)) {
          await parseFile(file);
        } else {
          toast.error(
            `Please upload a ${SUPPORTED_FILE_EXTENSIONS.join(', ')} file`
          );
        }
      }
    },
    [parseFile]
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
            height: 44,
            minHeight: 44,
            pl: 2,
            pr: 1,
            borderBottom: '1px solid',
            borderColor: 'divider',
          }}>
          <Typography variant="h6" sx={{...typographyStyle, fontWeight: 600}}>
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

              <Box sx={{mb: 2}}>
                <Typography
                  sx={{
                    ...typographyStyle,
                    fontWeight: 600,
                    mb: '8px',
                  }}>
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
                    fontWeight: 400,
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
                    borderColor: isDragging ? TEAL_500 : MOON_300,
                    borderRadius: '8px',
                    p: 4,
                    flex: 1,
                    minHeight: '300px',
                    backgroundColor: isDragging
                      ? `${TEAL_300}52`
                      : 'transparent',
                    transition: 'all 0.2s ease',
                  }}
                  onDragEnter={handleDragEnter}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}>
                  <Typography
                    variant="h6"
                    sx={{
                      ...typographyStyle,
                      fontSize: '1.125rem',
                      fontWeight: 600,
                    }}
                    gutterBottom>
                    {isDragging ? 'Drop file here' : 'Upload your data file'}
                  </Typography>
                  <Typography
                    variant="body2"
                    sx={typographyStyle}
                    color="textSecondary"
                    align="center"
                    gutterBottom>
                    Drag and drop your {SUPPORTED_FILE_EXTENSIONS.join(', ')}{' '}
                    file here, or click below to browse.
                    <br />
                    Your file will be converted to a dataset that you can edit
                    before saving.
                  </Typography>
                  <Box sx={{mt: 2}}>
                    <input
                      accept={SUPPORTED_FILE_EXTENSIONS.map(
                        ext => `.${ext}`
                      ).join(',')}
                      id="data-upload"
                      type="file"
                      style={{display: 'none'}}
                      onChange={handleFileChange}
                      ref={fileInputRef}
                    />
                    <Button onClick={handleUploadClick} variant="secondary">
                      Browse for file
                    </Button>
                  </Box>
                  {isDragging && (
                    <Typography
                      variant="body2"
                      sx={{...typographyStyle, fontWeight: 'bold', mt: 2}}
                      style={{color: TEAL_500}}>
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
                    borderTop: '1px solid',
                    borderColor: 'divider',
                    mx: -2,
                    mb: -2,
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
