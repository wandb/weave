import {Box} from '@mui/material';
import {Button} from '@wandb/weave/components';
import React, {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
} from 'react';

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
import {
  DatasetObjectVal,
  EditableDatasetView,
  EditableDatasetViewProps,
} from '../../datasets/EditableDatasetView';
import {useDatasetSaving} from '../../datasets/useDatasetSaving';
import {HEADER_HEIGHT_PX} from './constants';
import {clientBound, hookify} from './hooks';
import {getObjByRef} from './query';
import {defaultScorerConfigPayload} from './state';

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
  {datasetRef: string}
>(({datasetRef}, ref) => {
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
      />
    </DatasetEditProvider>
  );
});

const ExistingDatasetEditorInner = forwardRef<
  {handleSave: () => Promise<string | null>},
  {
    datasetRef: string;
    datasetObject: DatasetObjectVal;
  }
>(({datasetRef, datasetObject}, ref) => {
  const {editedRows, deletedRows, addedRows, resetEditState} =
    useDatasetEditContext();

  // Check if there are any unsaved changes
  const hasChanges = React.useMemo(() => {
    return editedRows.size > 0 || deletedRows.length > 0 || addedRows.size > 0;
  }, [editedRows.size, deletedRows.length, addedRows.size]);

  const handleSave = React.useCallback(async () => {
    // TODO: Implement actual save logic
    console.log('Saving dataset changes...', {
      editedRows: editedRows.size,
      deletedRows: deletedRows.length,
      addedRows: addedRows.size,
    });

    // For now, just return the existing dataset ref
    // In the future, this should create a new version of the dataset with the changes
    // and return the new ref

    // After save, reset the edit state
    resetEditState();
    // Return the existing dataset ref since we're updating it
    return datasetRef;
  }, [editedRows, deletedRows, addedRows, resetEditState, datasetRef]);

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
