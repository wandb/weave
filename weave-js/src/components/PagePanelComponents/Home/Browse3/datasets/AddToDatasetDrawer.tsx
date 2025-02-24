import {Box, Typography} from '@mui/material';
import React, {useCallback, useEffect, useState} from 'react';
import {toast} from 'react-toastify';

import {maybePluralize} from '../../../../../core/util/string';
import {Button} from '../../../../Button';
import {WaveLoader} from '../../../../Loaders/WaveLoader';
import {useWeaveflowRouteContext} from '../context';
import {ResizableDrawer} from '../pages/common/ResizableDrawer';
import {useWFHooks} from '../pages/wfReactInterface/context';
import {ObjectVersionSchema} from '../pages/wfReactInterface/wfDataModelHooksInterface';
import {
  DatasetEditProvider,
  useDatasetEditContext,
} from './DatasetEditorContext';
import {createNewDataset, updateExistingDataset} from './datasetOperations';
import {DatasetPublishToast} from './DatasetPublishToast';
import {EditAndConfirmStep} from './EditAndConfirmStep';
import {FieldConfig, NewDatasetSchemaStep} from './NewDatasetSchemaStep';
import {SchemaMappingStep} from './SchemaMappingStep';
import {CallData, FieldMapping} from './schemaUtils';
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
    <DatasetEditProvider>
      <AddToDatasetDrawerInner {...props} />
    </DatasetEditProvider>
  );
};

export const AddToDatasetDrawerInner: React.FC<AddToDatasetDrawerProps> = ({
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
  const [drawerWidth, setDrawerWidth] = useState(800);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [newDatasetName, setNewDatasetName] = useState<string | null>(null);
  const [fieldConfigs, setFieldConfigs] = useState<FieldConfig[]>([]);
  const [isNameValid, setIsNameValid] = useState(false);
  const [datasetKey, setDatasetKey] = useState<string>('');

  const {peekingRouter} = useWeaveflowRouteContext();
  const {useRootObjectVersions, useTableUpdate, useObjCreate, useTableCreate} =
    useWFHooks();
  const tableUpdate = useTableUpdate();
  const objCreate = useObjCreate();
  const tableCreate = useTableCreate();
  const {getRowsNoMeta, convertEditsToTableUpdateSpec, resetEditState} =
    useDatasetEditContext();

  // Update dataset key when the underlying dataset selection or mappings change
  useEffect(() => {
    if (currentStep === 1) {
      // Only update key when on the selection/mapping step
      setDatasetKey(
        selectedDataset
          ? `${selectedDataset.objectId}-${
              selectedDataset.versionHash
            }-${JSON.stringify(fieldMappings)}`
          : `new-dataset-${newDatasetName}-${JSON.stringify(fieldMappings)}`
      );
    }
  }, [currentStep, selectedDataset, newDatasetName, fieldMappings]);

  // Reset edit state only when the dataset key changes
  useEffect(() => {
    if (datasetKey) {
      resetEditState();
    }
  }, [datasetKey, resetEditState]);

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
    const isNewDataset = selectedDataset === null;
    if (isNewDataset) {
      if (!newDatasetName?.trim()) {
        setError('Please enter a dataset name');
        return;
      }
      if (!fieldConfigs.some(config => config.included)) {
        setError('Please select at least one field to include');
        return;
      }

      // Create field mappings from field configs
      const newMappings = fieldConfigs
        .filter(config => config.included)
        .map(config => ({
          sourceField: config.sourceField,
          targetField: config.targetField,
        }));
      setFieldMappings(newMappings);

      // Create an empty dataset object structure
      const newDatasetObject = {
        rows: [],
        schema: fieldConfigs
          .filter(config => config.included)
          .map(config => ({
            name: config.targetField,
            type: 'string', // You might want to infer the type from the source data
          })),
      };
      setDatasetObject(newDatasetObject);
    }
    setCurrentStep(prev => Math.min(prev + 1, 2));
  };

  const handleBack = () => {
    setCurrentStep(prev => Math.max(prev - 1, 1));
  };

  const handleDatasetSelect = (dataset: ObjectVersionSchema | null) => {
    if (dataset?.objectId !== selectedDataset?.objectId) {
      resetEditState();
      setSelectedDataset(dataset);
    } else {
      setSelectedDataset(dataset);
    }
  };

  const handleMappingChange = (newMappings: FieldMapping[]) => {
    if (JSON.stringify(newMappings) !== JSON.stringify(fieldMappings)) {
      resetEditState();
      setFieldMappings(newMappings);
    } else {
      setFieldMappings(newMappings);
    }
  };

  const projectId = `${entity}/${project}`;

  const resetDrawerState = useCallback(() => {
    setCurrentStep(1);
    setSelectedDataset(null);
    setFieldMappings([]);
    setDatasetObject(null);
    setError(null);
  }, []);

  const handleCreate = async () => {
    if (!datasetObject) {
      return;
    }

    setError(null);
    setIsCreating(true);
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
      onClose();
    } catch (error) {
      console.error('Failed to create dataset version:', error);
      setError(
        error instanceof Error ? error.message : 'An unexpected error occurred'
      );
    } finally {
      setIsCreating(false);
    }
  };

  const isNextDisabled =
    currentStep === 1 &&
    ((selectedDataset === null && (!newDatasetName?.trim() || !isNameValid)) ||
      (selectedDataset === null &&
        !fieldConfigs.some(config => config.included)));

  const renderStepContent = () => {
    const isNewDataset = selectedDataset === null;
    const hasDatasetChoice =
      selectedDataset !== null || newDatasetName !== null;

    switch (currentStep) {
      case 1:
        return (
          <div>
            <SelectDatasetStep
              selectedDataset={selectedDataset}
              setSelectedDataset={handleDatasetSelect}
              datasets={datasets}
              newDatasetName={newDatasetName}
              setNewDatasetName={setNewDatasetName}
              onValidationChange={setIsNameValid}
              entity={entity}
              project={project}
            />
            {hasDatasetChoice && (
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
                    onDatasetObjectLoaded={setDatasetObject}
                  />
                )}
                {isNewDataset && (
                  <NewDatasetSchemaStep
                    selectedCalls={selectedCalls}
                    fieldConfigs={fieldConfigs}
                    onFieldConfigsChange={setFieldConfigs}
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
      setWidth={width => !isFullscreen && setDrawerWidth(width)}>
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
                  onClick={() => setIsFullscreen(!isFullscreen)}
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
