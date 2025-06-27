import {Box} from '@mui/material';
import {Button} from '@wandb/weave/components';
import React, {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
} from 'react';

import {isWeaveObjectRef, parseRef} from '../../../../../../react';
import {makeRefObject} from '../../../../../../util/refs';
import {useWeaveflowCurrentRouteContext} from '../../context';
import {DatasetFilePicker} from '../../datasets/CreateDatasetDrawer';
import {
  CREATE_DATASET_ACTIONS,
  CreateDatasetProvider,
  useCreateDatasetContext,
} from '../../datasets/CreateDatasetDrawerContext';
import {
  DatasetEditProvider,
  useDatasetEditContext,
} from '../../datasets/DatasetEditorContext';
import {updateExistingDataset} from '../../datasets/datasetOperations';
import {
  DatasetObjectVal,
  EditableDatasetView,
  EditableDatasetViewProps,
} from '../../datasets/EditableDatasetView';
import {useDatasetSaving} from '../../datasets/useDatasetSaving';
import {useWFHooks} from '../wfReactInterface/context';
import {HEADER_HEIGHT_PX} from './constants';
import {clientBound, hookify} from './hooks';
import {getObjByRef} from './query';

const initializationRows = [
  {
    user_input: 'Hello, how are you?',
    expected_output: "I'm good, thank you!",
  },
  {
    user_input: 'What is the capital of France?',
    expected_output: 'Paris',
  },
  {
    user_input: 'What are you?',
    expected_output: 'I am a helpful AI assistant.',
  },
];

export interface DatasetEditorRef {
  save: () => Promise<string | null>;
}

export const NewDatasetEditor = forwardRef<
  DatasetEditorRef,
  {
    entity: string;
    project: string;
    useFilePicker?: boolean;
    onSaveComplete?: (datasetRef?: string) => void;
  }
>(({entity, project, useFilePicker = false, onSaveComplete}, ref) => {
  const innerRef = useRef<{handleSave: () => void} | null>(null);
  const saveResolverRef = useRef<((datasetRef: string | null) => void) | null>(
    null
  );

  const {handleSaveDataset} = useDatasetSaving({
    entity,
    project,
    showToast: false,
    onSaveComplete: datasetRef => {
      onSaveComplete?.(datasetRef);
      // Resolve the promise with the dataset ref
      if (saveResolverRef.current) {
        saveResolverRef.current(datasetRef || null);
        saveResolverRef.current = null;
      }
    },
  });

  // Expose save method via ref
  useImperativeHandle(
    ref,
    () => ({
      save: () => {
        return new Promise<string | null>(resolve => {
          saveResolverRef.current = resolve;
          // Trigger the save on the inner component
          if (innerRef.current) {
            innerRef.current.handleSave();
          } else {
            resolve(null);
          }

          // Set a timeout in case save doesn't complete
          setTimeout(() => {
            if (saveResolverRef.current) {
              saveResolverRef.current = null;
              resolve(null);
            }
          }, 10000); // 10 second timeout
        });
      },
    }),
    []
  );

  return (
    <CreateDatasetProvider onPublishDataset={handleSaveDataset}>
      {useFilePicker ? (
        <NewFileDatasetEditorInner ref={innerRef} />
      ) : (
        <NewEmptyDatasetEditorInner ref={innerRef} />
      )}
    </CreateDatasetProvider>
  );
});

const NewEmptyDatasetEditorInner = forwardRef<{handleSave: () => void}>(
  (props, ref) => {
    const {state, initializeDataset, handlePublishDataset} =
      useCreateDatasetContext();
    const {parsedData} = state;

    useEffect(() => {
      if (!parsedData) {
        initializeDataset(initializationRows);
      }
    }, [initializeDataset, parsedData]);

    useImperativeHandle(
      ref,
      () => ({
        handleSave: () => {
          handlePublishDataset();
        },
      }),
      [handlePublishDataset]
    );

    if (!parsedData) {
      return null;
    }

    return <EditableDatasetViewInner datasetObject={parsedData} />;
  }
);

const NewFileDatasetEditorInner = forwardRef<{handleSave: () => void}>(
  (props, ref) => {
    const {state, parseFile, handlePublishDataset} = useCreateDatasetContext();
    const {parsedData} = state;

    useImperativeHandle(
      ref,
      () => ({
        handleSave: () => {
          handlePublishDataset();
        },
      }),
      [handlePublishDataset]
    );

    if (!parsedData) {
      return (
        <Box sx={{p: 2}}>
          <DatasetFilePicker handleFileSelect={parseFile} />
        </Box>
      );
    }

    return <EditableDatasetViewInner datasetObject={parsedData} />;
  }
);

const EditableDatasetViewInner: React.FC<
  Pick<EditableDatasetViewProps, 'datasetObject'>
> = props => {
  const {handlePublishDataset, dispatch} = useCreateDatasetContext();
  useEffect(() => {
    // TODO: Get the name from the user
    dispatch({
      type: CREATE_DATASET_ACTIONS.SET_DATASET_NAME,
      payload: 'eval-dataset',
    });

    // TODO: Validate the name
    // const validationResult = validateDatasetName(value);
  }, [dispatch]);
  const onSave = useCallback(() => {
    handlePublishDataset();
  }, [handlePublishDataset]);
  return (
    <Box sx={{height: '100%', width: '100%', overflow: 'hidden'}}>
      <EditableDatasetView
        {...props}
        isEditing={true}
        hideRemoveForAddedRows={false}
        showAddRowButton={true}
        hideIdColumn={true}
        // disableNewRowHighlight={true}
        isNewDataset={true}
        footerHeight={HEADER_HEIGHT_PX}
        extraFooterContent={
          <Button icon="save" variant="primary" onClick={onSave}>
            Save Changes
          </Button>
        }
        inlineEditMode={true}
        autoAddRows={true}
        // columnsBeforeData={[
        //   {
        //     field: 'name_a',
        //     headerName: 'Name_a',
        //     width: 150,
        //   },
        //   {
        //     field: 'name_b',
        //     headerName: 'Name_b',
        //     width: 150,
        //   },
        // ]}
        // columnsAfterData={[
        //   {
        //     field: 'name_c',
        //     headerName: 'Name_c',
        //     width: 150,
        //   },
        //   {
        //     field: 'name_d',
        //     headerName: 'Name_d',
        //     width: 150,
        //   },
        // ]}
        // columnGroups={[
        //   {
        //     groupId: 'name_a',
        //     headerName: 'Prefix',
        //     children: [
        //       {field: "name_a"},
        //       {field: "name_b"}
        //     ],
        //   },
        //   {
        //     groupId: 'name_c',
        //     headerName: 'Suffix',
        //     children: [
        //       {field: "name_c"},
        //       {field: "name_d"}
        //     ],
        //   },
        // ]}
      />
    </Box>
  );
};

const useObjByRef = clientBound(hookify(getObjByRef));

export const ExistingDatasetEditor = forwardRef<
  DatasetEditorRef,
  {datasetRef: string; onSaveComplete?: (datasetRef?: string) => void}
>(({datasetRef, onSaveComplete}, ref) => {
  const innerRef = useRef<{handleSave: () => Promise<string | null>} | null>(
    null
  );
  const datasetObject = useObjByRef(datasetRef);

  useImperativeHandle(
    ref,
    () => ({
      save: async () => {
        if (innerRef.current) {
          return await innerRef.current.handleSave();
        }
        return null;
      },
    }),
    []
  );

  if (datasetObject.loading || datasetObject.error || !datasetObject.data) {
    // TODO
    return null;
  }
  return (
    <DatasetEditProvider>
      <ExistingDatasetEditorInner
        ref={innerRef}
        datasetRef={datasetRef}
        datasetObject={datasetObject.data.val as DatasetObjectVal}
        onSaveComplete={onSaveComplete}
      />
    </DatasetEditProvider>
  );
});

const ExistingDatasetEditorInner = forwardRef<
  {handleSave: () => Promise<string | null>},
  {
    datasetRef: string;
    datasetObject: DatasetObjectVal;
    onSaveComplete?: (datasetRef?: string) => void;
  }
>(({datasetRef, datasetObject, onSaveComplete}, ref) => {
  const {
    editedRows,
    deletedRows,
    addedRows,
    resetEditState,
    convertEditsToTableUpdateSpec,
  } = useDatasetEditContext();
  const {useTableUpdate, useObjCreate} = useWFHooks();
  const tableUpdate = useTableUpdate();
  const objCreate = useObjCreate();
  const router = useWeaveflowCurrentRouteContext();

  // Check if there are any unsaved changes
  const hasChanges = React.useMemo(() => {
    return editedRows.size > 0 || deletedRows.length > 0 || addedRows.size > 0;
  }, [editedRows.size, deletedRows.length, addedRows.size]);

  const handleSave = React.useCallback(async () => {
    try {
      // Parse the dataset ref to get entity and project
      const parsedRef = parseRef(datasetRef);
      if (!isWeaveObjectRef(parsedRef)) {
        throw new Error('Invalid dataset reference');
      }

      const entity = parsedRef.entityName;
      const project = parsedRef.projectName;
      const projectId = `${entity}/${project}`;

      // Get the update specs from the context
      const updateSpecs = convertEditsToTableUpdateSpec();

      if (updateSpecs.length === 0) {
        // No changes to save
        return datasetRef;
      }

      // Create the selected dataset object for the update function
      // Only objectId is actually used by updateExistingDataset
      const selectedDataset: any = {
        objectId: parsedRef.artifactName,
      };

      // Update the dataset
      const result = await updateExistingDataset({
        projectId,
        entity,
        project,
        selectedDataset,
        datasetObject,
        updateSpecs,
        tableUpdate,
        objCreate,
        router,
      });

      // Reset the edit state after successful save
      resetEditState();

      // Construct the new ref with the updated digest
      const newRef = makeRefObject(
        entity,
        project,
        'object',
        result.objectId,
        result.objectDigest,
        undefined
      );

      // Call the save complete callback with the new ref
      onSaveComplete?.(newRef);

      return newRef;
    } catch (error: any) {
      console.error('Failed to update dataset:', error);
      return null;
    }
  }, [
    datasetRef,
    convertEditsToTableUpdateSpec,
    datasetObject,
    tableUpdate,
    objCreate,
    router,
    resetEditState,
    onSaveComplete,
  ]);

  useImperativeHandle(
    ref,
    () => ({
      handleSave,
    }),
    [handleSave]
  );

  return (
    <Box sx={{height: '100%', width: '100%', overflow: 'hidden'}}>
      <EditableDatasetView
        datasetObject={datasetObject}
        isEditing={true}
        hideRemoveForAddedRows={false}
        showAddRowButton={true}
        hideIdColumn={true}
        footerHeight={HEADER_HEIGHT_PX}
        extraFooterContent={
          <Button
            icon="save"
            variant="primary"
            onClick={handleSave}
            disabled={!hasChanges}
            tooltip={!hasChanges ? 'No changes to save' : 'Save changes'}>
            Save Changes
          </Button>
        }
        inlineEditMode={true}
      />
    </Box>
  );
});
