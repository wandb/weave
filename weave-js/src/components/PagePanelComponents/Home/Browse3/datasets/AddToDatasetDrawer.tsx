import {Box, Typography} from '@mui/material';
import React, {useCallback, useEffect} from 'react';
import {toast} from 'react-toastify';

import {maybePluralize} from '../../../../../core/util/string';
import {Button} from '../../../../Button';
import {WaveLoader} from '../../../../Loaders/WaveLoader';
import {useWeaveflowRouteContext} from '../context';
import {ResizableDrawer} from '../pages/common/ResizableDrawer';
import {useWFHooks} from '../pages/wfReactInterface/context';
import {
  ACTION_TYPES,
  DatasetDrawerProvider,
  useDatasetDrawer,
} from './DatasetDrawerContext';
import {createNewDataset, updateExistingDataset} from './datasetOperations';
import {DatasetPublishToast} from './DatasetPublishToast';
import {EditAndConfirmStep} from './EditAndConfirmStep';
import {NewDatasetSchemaStep} from './NewDatasetSchemaStep';
import {SchemaMappingStep} from './SchemaMappingStep';
import {CallData, extractSourceSchema} from './schemaUtils';
import {SelectDatasetStep} from './SelectDatasetStep';

interface AddToDatasetDrawerProps {
  entity: string;
  project: string;
  open: boolean;
  onClose: () => void;
  selectedCalls: CallData[];
}

const typographyStyle = {fontFamily: 'Source Sans Pro'};

export const AddToDatasetDrawer: React.FC<AddToDatasetDrawerProps> = props => {
  return (
    <DatasetDrawerProvider
      selectedCalls={props.selectedCalls}
      onClose={props.onClose}
      entity={props.entity}
      project={props.project}>
      <AddToDatasetDrawerInner {...props} />
    </DatasetDrawerProvider>
  );
};

export const AddToDatasetDrawerInner: React.FC<AddToDatasetDrawerProps> = ({
  open,
  onClose,
  entity,
  project,
  selectedCalls,
}) => {
  const {
    state,
    dispatch,
    handleNext,
    handleBack,
    handleDatasetSelect,
    handleMappingChange,
    handleDatasetObjectLoaded,
    resetDrawerState,
    isNextDisabled,
    editorContext,
  } = useDatasetDrawer();

  const {
    currentStep,
    selectedDataset,
    newDatasetName,
    datasets,
    isCreatingNew,
    fieldMappings,
    fieldConfigs,
    datasetObject,
    drawerWidth,
    isFullscreen,
    isCreating,
    error,
  } = state;

  const {peekingRouter} = useWeaveflowRouteContext();
  const {useRootObjectVersions, useTableUpdate, useObjCreate, useTableCreate} =
    useWFHooks();
  const tableUpdate = useTableUpdate();
  const objCreate = useObjCreate();
  const tableCreate = useTableCreate();

  // Access edit context methods through the drawer context's editorContext property
  const {getRowsNoMeta, convertEditsToTableUpdateSpec, resetEditState} =
    editorContext;

  // Fetch datasets on component mount
  const objectVersions = useRootObjectVersions(
    entity,
    project,
    {
      baseObjectClasses: ['Dataset'],
    },
    undefined,
    true
  );

  // Update datasets when data is loaded
  useEffect(() => {
    if (objectVersions.result) {
      dispatch({
        type: ACTION_TYPES.SET_DATASETS,
        payload: objectVersions.result,
      });
    }
  }, [objectVersions.result, dispatch]);

  // Extract source schema from selected calls
  useEffect(() => {
    if (selectedCalls.length > 0) {
      const extractedSchema = extractSourceSchema(selectedCalls);
      dispatch({
        type: ACTION_TYPES.SET_SOURCE_SCHEMA,
        payload: extractedSchema,
      });
    }
  }, [selectedCalls, dispatch]);

  const projectId = `${entity}/${project}`;

  const handleCreate = useCallback(async () => {
    if (!datasetObject) {
      return;
    }

    dispatch({type: ACTION_TYPES.SET_ERROR, payload: null});
    dispatch({type: ACTION_TYPES.SET_IS_CREATING, payload: true});

    try {
      let result: any;
      const isNewDataset = selectedDataset === null;

      if (isNewDataset) {
        // Create new dataset flow
        if (!newDatasetName) {
          throw new Error('Dataset name is required');
        }
        result = await createNewDataset({
          projectId,
          entity,
          project,
          datasetName: newDatasetName,
          rows: getRowsNoMeta(),
          tableCreate,
          objCreate,
          router: peekingRouter,
        });
      } else {
        // Update existing dataset flow
        if (!selectedDataset) {
          throw new Error('No dataset selected');
        }
        result = await updateExistingDataset({
          projectId,
          entity,
          project,
          selectedDataset,
          datasetObject,
          updateSpecs: convertEditsToTableUpdateSpec(),
          tableUpdate,
          objCreate,
          router: peekingRouter,
        });
      }

      toast(
        <DatasetPublishToast
          message={`${maybePluralize(
            selectedCalls.length,
            'example'
          )} added to dataset`}
          url={result.url}
        />,
        {
          autoClose: 5000,
          hideProgressBar: true,
          closeOnClick: true,
          pauseOnHover: true,
        }
      );

      resetDrawerState();
      resetEditState();
      onClose();
    } catch (error) {
      console.error('Failed to create dataset version:', error);
      dispatch({
        type: ACTION_TYPES.SET_ERROR,
        payload:
          error instanceof Error
            ? error.message
            : 'An unexpected error occurred',
      });
    } finally {
      dispatch({type: ACTION_TYPES.SET_IS_CREATING, payload: false});
    }
  }, [
    datasetObject,
    selectedDataset,
    newDatasetName,
    projectId,
    entity,
    project,
    selectedCalls.length,
    getRowsNoMeta,
    tableCreate,
    objCreate,
    peekingRouter,
    convertEditsToTableUpdateSpec,
    tableUpdate,
    dispatch,
    resetDrawerState,
    resetEditState,
    onClose,
  ]);

  const renderStepContent = () => {
    const isNewDataset = selectedDataset === null;
    const showSchemaConfig = selectedDataset !== null || isCreatingNew;

    switch (currentStep) {
      case 1:
        return (
          <div>
            <SelectDatasetStep
              selectedDataset={selectedDataset}
              setSelectedDataset={handleDatasetSelect}
              datasets={datasets}
              newDatasetName={newDatasetName}
              setNewDatasetName={name =>
                dispatch({
                  type: ACTION_TYPES.SET_NEW_DATASET_NAME,
                  payload: name,
                })
              }
              onValidationChange={isValid =>
                dispatch({
                  type: ACTION_TYPES.SET_IS_NAME_VALID,
                  payload: isValid,
                })
              }
              entity={entity}
              project={project}
              isCreatingNew={isCreatingNew}
              setIsCreatingNew={isCreatingValue =>
                dispatch({
                  type: ACTION_TYPES.SET_IS_CREATING_NEW,
                  payload: isCreatingValue,
                })
              }
            />
            {showSchemaConfig && (
              <>
                {!isNewDataset && selectedDataset && (
                  <SchemaMappingStep
                    selectedDataset={selectedDataset}
                    selectedCalls={selectedCalls}
                    entity={entity}
                    project={project}
                    fieldMappings={fieldMappings}
                    datasetObject={datasetObject}
                    onMappingChange={handleMappingChange}
                    onDatasetObjectLoaded={handleDatasetObjectLoaded}
                  />
                )}
                {isNewDataset && (
                  <NewDatasetSchemaStep
                    selectedCalls={selectedCalls}
                    fieldConfigs={fieldConfigs}
                    onFieldConfigsChange={configs =>
                      dispatch({
                        type: ACTION_TYPES.SET_FIELD_CONFIGS,
                        payload: configs,
                      })
                    }
                  />
                )}
              </>
            )}
          </div>
        );
      case 2:
        return (
          <EditAndConfirmStep
            selectedCalls={selectedCalls}
            fieldMappings={fieldMappings}
            datasetObject={datasetObject}
            isNewDataset={isNewDataset}
          />
        );
      default:
        return null;
    }
  };

  return (
    <ResizableDrawer
      open={open}
      onClose={onClose}
      defaultWidth={isFullscreen ? window.innerWidth - 73 : drawerWidth}
      setWidth={width =>
        !isFullscreen &&
        dispatch({type: ACTION_TYPES.SET_DRAWER_WIDTH, payload: width})
      }>
      {isCreating ? (
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height: '100%',
          }}>
          <WaveLoader size="huge" />
        </Box>
      ) : (
        <>
          <Box
            sx={{
              position: 'sticky',
              top: 0,
              zIndex: 20,
              pl: '16px',
              pr: '8px',
              height: 44,
              width: '100%',
              borderBottom: '1px solid',
              borderColor: 'divider',
              display: 'flex',
              flexDirection: 'row',
              alignItems: 'center',
              justifyContent: 'space-between',
              backgroundColor: 'white',
            }}>
            <Box
              sx={{
                height: 44,
                display: 'flex',
                alignItems: 'center',
                gap: 1,
              }}>
              {currentStep === 2 ? (
                <Button
                  onClick={handleBack}
                  variant="ghost"
                  icon="back"
                  tooltip="Back"
                  size="medium"
                />
              ) : null}
              <Typography
                sx={{
                  ...typographyStyle,
                  fontWeight: 600,
                  fontSize: '1.25rem',
                }}>
                Add example{selectedCalls.length !== 1 ? 's' : ''} to dataset
              </Typography>
            </Box>
            <Box sx={{display: 'flex', gap: 1}}>
              {currentStep === 2 && (
                <Button
                  onClick={() =>
                    dispatch({
                      type: ACTION_TYPES.SET_IS_FULLSCREEN,
                      payload: !isFullscreen,
                    })
                  }
                  variant="ghost"
                  icon="full-screen-mode-expand"
                  tooltip={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
                  size="medium"
                />
              )}
              {currentStep === 1 && (
                <Button
                  size="medium"
                  variant="ghost"
                  icon="close"
                  onClick={onClose}
                  tooltip="Close"
                />
              )}
            </Box>
          </Box>
          <Box
            sx={{
              flex: 1,
              overflow: 'auto',
              px: currentStep === 1 ? 2 : 0,
              display: 'flex',
              flexDirection: 'column',
            }}>
            {error && (
              <Box sx={{mb: 2, p: 2, bgcolor: 'error.light', borderRadius: 1}}>
                <Typography sx={typographyStyle} color="error.dark">
                  {error}
                </Typography>
              </Box>
            )}
            {renderStepContent()}
          </Box>
          <Box
            sx={{
              p: 2,
              borderTop: '1px solid',
              borderColor: 'divider',
              display: 'flex',
              justifyContent: 'space-between',
              gap: 1,
              bgcolor: 'background.paper',
            }}>
            {currentStep === 1 ? (
              <Button
                onClick={handleNext}
                color="primary"
                variant="primary"
                disabled={isNextDisabled}
                style={{width: '100%'}}
                twWrapperStyles={{width: '100%'}}>
                Next
              </Button>
            ) : (
              <>
                <Button
                  onClick={handleBack}
                  color="primary"
                  variant="secondary"
                  style={{width: '100%'}}
                  twWrapperStyles={{width: '100%'}}>
                  Back
                </Button>
                <Button
                  onClick={handleCreate}
                  color="primary"
                  variant="primary"
                  style={{width: '100%'}}
                  twWrapperStyles={{width: '100%'}}>
                  {selectedDataset === null
                    ? 'Create dataset'
                    : 'Add to dataset'}
                </Button>
              </>
            )}
          </Box>
        </>
      )}
    </ResizableDrawer>
  );
};
