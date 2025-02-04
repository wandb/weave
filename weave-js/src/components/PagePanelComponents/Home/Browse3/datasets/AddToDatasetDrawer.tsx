import {Box, Stack, Typography} from '@mui/material';
import React, {useCallback, useEffect, useRef, useState} from 'react';
import {toast} from 'react-toastify';

import {Button} from '../../../../Button';
import {useWeaveflowCurrentRouteContext} from '../context';
import {useWFHooks} from '../pages/wfReactInterface/context';
import {ObjectVersionSchema} from '../pages/wfReactInterface/wfDataModelHooksInterface';
import {DatasetEditProvider} from './DatasetEditorContext';
import {createDatasetVersion} from './datasetOperations';
import {DatasetPublishToast} from './DatasetPublishToast';
import {EditAndConfirmStep} from './EditAndConfirmStep';
import {SchemaMappingStep} from './SchemaMappingStep';
import {CallData, FieldMapping} from './schemaUtils';
import {SelectDatasetStep} from './SelectDatasetStep';
import {ResizableDrawer} from '../pages/common/ResizableDrawer';

interface AddToDatasetDrawerProps {
  entity: string;
  project: string;
  open: boolean;
  onClose: () => void;
  selectedCalls: CallData[];
}

const typographyStyle = {fontFamily: 'Source Sans Pro'};

export const AddToDatasetDrawer: React.FC<AddToDatasetDrawerProps> = ({
  open,
  onClose,
  entity,
  project,
  selectedCalls,
}) => {
  const [currentStep, setCurrentStep] = useState(1);
  const [selectedDataset, setSelectedDataset] =
    useState<ObjectVersionSchema | null>(null);
  const [datasets, setDatasets] = useState<ObjectVersionSchema[]>([]);
  const [fieldMappings, setFieldMappings] = useState<FieldMapping[]>([]);
  const [datasetObject, setDatasetObject] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const editContextRef = React.useRef<any>(null);
  const [drawerWidth, setDrawerWidth] = useState(800);

  const router = useWeaveflowCurrentRouteContext();

  const {useRootObjectVersions, useTableUpdate, useObjCreate} = useWFHooks();
  const tableUpdate = useTableUpdate();
  const objCreate = useObjCreate();

  const objectVersions = useRootObjectVersions(
    entity,
    project,
    {
      baseObjectClasses: ['Dataset'],
    },
    undefined,
    true
  );

  useEffect(() => {
    if (objectVersions.result) {
      setDatasets(objectVersions.result);
    }
  }, [objectVersions.result]);

  const handleNext = () => {
    setCurrentStep(prev => Math.min(prev + 1, 2));
  };

  const handleBack = () => {
    setCurrentStep(prev => Math.max(prev - 1, 1));
  };

  const projectId = `${entity}/${project}`;

  const resetDrawerState = useCallback(() => {
    setCurrentStep(1);
    setSelectedDataset(null);
    setFieldMappings([]);
    setDatasetObject(null);
    setError(null);
    // Optionally reset the editContextRef if it supports a reset
    // if (editContextRef.current && editContextRef.current.reset) {
    //   editContextRef.current.reset();
    // }
  }, []);

  const handleCreate = async () => {
    if (!selectedDataset || !datasetObject) {
      return;
    }

    setError(null);
    try {
      const {url, objectId} = await createDatasetVersion({
        projectId,
        selectedDataset,
        datasetObject,
        editContextRef,
        tableUpdate,
        objCreate,
        router,
        entity,
        project,
      });

      toast(<DatasetPublishToast {...{url, objectId}} />, {
        autoClose: 5000,
        hideProgressBar: true,
        closeOnClick: true,
        pauseOnHover: true,
      });

      resetDrawerState();
      onClose();
    } catch (error) {
      console.error('Failed to create dataset version:', error);
      setError(
        error instanceof Error ? error.message : 'An unexpected error occurred'
      );
    }
  };

  const isNextDisabled = currentStep === 1 && !selectedDataset;

  const renderStepContent = () => {
    switch (currentStep) {
      case 1:
        return (
          <div>
            <SelectDatasetStep
              selectedDataset={selectedDataset}
              setSelectedDataset={setSelectedDataset}
              datasets={datasets}
              selectedCallsCount={selectedCalls.length}
            />
            {selectedDataset && (
              <SchemaMappingStep
                selectedDataset={selectedDataset}
                selectedCalls={selectedCalls}
                entity={entity}
                project={project}
                fieldMappings={fieldMappings}
                datasetObject={datasetObject}
                onMappingChange={setFieldMappings}
                onDatasetObjectLoaded={setDatasetObject}
              />
            )}
          </div>
        );
      case 2:
        return selectedDataset && datasetObject ? (
          <EditAndConfirmStep
            selectedCalls={selectedCalls}
            fieldMappings={fieldMappings}
            datasetObject={datasetObject}
            editContextRef={editContextRef}
          />
        ) : null;
      default:
        return null;
    }
  };

  return (
    <ResizableDrawer
      open={open}
      onClose={onClose}
      defaultWidth={drawerWidth}
      setWidth={setDrawerWidth}>
      <DatasetEditProvider>
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
        <Typography
          sx={{
            ...typographyStyle,
            color: 'text.secondary',
            px: 2,
            pt: 2,
            pb: 0,
          }}>
          Step {currentStep} of 2:{' '}
          {currentStep === 1 ? 'Select dataset & map fields' : 'Edit & confirm'}
        </Typography>
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
                variant="ghost"
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
                Add
              </Button>
            </>
          )}
        </Box>
      </DatasetEditProvider>
    </ResizableDrawer>
  );
};
