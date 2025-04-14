import React, {
  createContext,
  Dispatch,
  ReactNode,
  useCallback,
  useContext,
  useReducer,
} from 'react';

import {ObjectVersionSchema} from '../pages/wfReactInterface/wfDataModelHooksInterface';
import {
  DatasetEditProvider,
  useDatasetEditContext,
} from './DatasetEditorContext';
import {FieldConfig} from './NewDatasetSchemaStep';
import {
  CallData,
  createProcessedRowsMap,
  FieldMapping,
  inferSchema,
  mapCallsToDatasetRows,
  suggestFieldMappings,
} from './schemaUtils';

// Define action type constants
export const ACTION_TYPES = {
  SET_CURRENT_STEP: 'SET_CURRENT_STEP',
  SET_DATASETS: 'SET_DATASETS',
  SELECT_DATASET: 'SELECT_DATASET',
  SET_IS_CREATING_NEW: 'SET_IS_CREATING_NEW',
  SET_NEW_DATASET_NAME: 'SET_NEW_DATASET_NAME',
  SET_FIELD_MAPPINGS: 'SET_FIELD_MAPPINGS',
  SET_FIELD_CONFIGS: 'SET_FIELD_CONFIGS',
  SET_DATASET_OBJECT: 'SET_DATASET_OBJECT',
  SET_SOURCE_SCHEMA: 'SET_SOURCE_SCHEMA',
  SET_TARGET_SCHEMA: 'SET_TARGET_SCHEMA',
  SET_DRAWER_WIDTH: 'SET_DRAWER_WIDTH',
  SET_IS_FULLSCREEN: 'SET_IS_FULLSCREEN',
  SET_IS_CREATING: 'SET_IS_CREATING',
  SET_ERROR: 'SET_ERROR',
  SET_IS_NAME_VALID: 'SET_IS_NAME_VALID',
  RESET_EDIT_STATE: 'RESET_EDIT_STATE',
  RESET_DRAWER_STATE: 'RESET_DRAWER_STATE',
  SET_PROCESSED_ROWS: 'SET_PROCESSED_ROWS',
  PROCESS_ROWS_FOR_EDITOR: 'PROCESS_ROWS_FOR_EDITOR',
  SET_USER_MODIFIED_MAPPINGS: 'SET_ADDED_ROWS_DIRTY',
} as const;

// Define the state interface
export interface DatasetDrawerState {
  // Step management
  currentStep: number;

  // Dataset selection
  selectedDataset: ObjectVersionSchema | null;
  isCreatingNew: boolean;
  newDatasetName: string | null;
  datasets: ObjectVersionSchema[];
  isNameValid: boolean;

  // Schema and field configuration
  fieldMappings: FieldMapping[];
  fieldConfigs: FieldConfig[];
  sourceSchema: any[];
  targetSchema: any[];

  // Flag to indicate mappings have been modified and rows need reprocessing
  addedRowsDirty: boolean;

  // Dataset object
  datasetObject: any;

  // Editor state
  processedRows: Map<string, any>;

  // UI state
  drawerWidth: number;
  isFullscreen: boolean;
  isCreating: boolean;
  error: string | null;
}

// Define action types using the constants
export type DatasetDrawerAction =
  | {
      type: typeof ACTION_TYPES.SET_CURRENT_STEP;
      payload: {step: number; setAddedRows?: (rows: Map<string, any>) => void};
    }
  | {type: typeof ACTION_TYPES.SET_DATASETS; payload: ObjectVersionSchema[]}
  | {
      type: typeof ACTION_TYPES.SELECT_DATASET;
      payload: ObjectVersionSchema | null;
    }
  | {type: typeof ACTION_TYPES.SET_IS_CREATING_NEW; payload: boolean}
  | {type: typeof ACTION_TYPES.SET_NEW_DATASET_NAME; payload: string | null}
  | {type: typeof ACTION_TYPES.SET_FIELD_MAPPINGS; payload: FieldMapping[]}
  | {type: typeof ACTION_TYPES.SET_FIELD_CONFIGS; payload: FieldConfig[]}
  | {type: typeof ACTION_TYPES.SET_DATASET_OBJECT; payload: any}
  | {type: typeof ACTION_TYPES.SET_SOURCE_SCHEMA; payload: any[]}
  | {type: typeof ACTION_TYPES.SET_TARGET_SCHEMA; payload: any[]}
  | {type: typeof ACTION_TYPES.SET_DRAWER_WIDTH; payload: number}
  | {type: typeof ACTION_TYPES.SET_IS_FULLSCREEN; payload: boolean}
  | {type: typeof ACTION_TYPES.SET_IS_CREATING; payload: boolean}
  | {type: typeof ACTION_TYPES.SET_ERROR; payload: string | null}
  | {type: typeof ACTION_TYPES.SET_IS_NAME_VALID; payload: boolean}
  | {type: typeof ACTION_TYPES.RESET_EDIT_STATE; payload?: undefined}
  | {type: typeof ACTION_TYPES.RESET_DRAWER_STATE; payload?: undefined}
  | {type: typeof ACTION_TYPES.SET_PROCESSED_ROWS; payload: Map<string, any>}
  | {
      type: typeof ACTION_TYPES.PROCESS_ROWS_FOR_EDITOR;
      payload?: {
        selectedCalls: CallData[];
        setAddedRows?: (rows: Map<string, any>) => void;
      };
    }
  | {type: typeof ACTION_TYPES.SET_USER_MODIFIED_MAPPINGS; payload: boolean};

// Initial state
const initialState: DatasetDrawerState = {
  currentStep: 1,
  selectedDataset: null,
  isCreatingNew: false,
  newDatasetName: null,
  datasets: [],
  isNameValid: false,
  fieldMappings: [],
  fieldConfigs: [],
  sourceSchema: [],
  targetSchema: [],
  addedRowsDirty: false,
  datasetObject: null,
  processedRows: new Map(),
  drawerWidth: 800,
  isFullscreen: false,
  isCreating: false,
  error: null,
};

/**
 * Handles the transition from step 2 (editing) back to step 1 (mapping).
 *
 * @param state - Current state of the dataset drawer
 * @returns Updated state for step 1
 */
function handleTransitionToStep1(
  state: DatasetDrawerState
): DatasetDrawerState {
  return {
    ...state,
    currentStep: 1,
    // Preserve addedRowsDirty flag when going back to step 1
  };
}

/**
 * Handles state transitions when changing steps in the dataset drawer workflow.
 *
 * This function manages the complex logic of transitioning between different steps
 * in the dataset creation/editing process, particularly focusing on:
 * - Processing rows when moving from mapping (step 1) to editing (step 2)
 * - Applying appropriate filtering based on dataset type (new vs existing)
 * - Updating the editor with processed rows when necessary
 *
 * @param state - Current state of the dataset drawer
 * @param newStep - The step number to transition to
 * @param currentStep - The current step number
 * @param setAddedRows - Optional callback to update rows in the editor
 * @returns Updated state after the step transition
 */
function handleStepTransition(
  state: DatasetDrawerState,
  newStep: number,
  currentStep: number,
  setAddedRows?: (rows: Map<string, any>) => void
): DatasetDrawerState {
  // Handle step transition from 1 to 2 specifically
  if (currentStep === 1 && newStep === 2) {
    // The main processing is now done in the AddToDatasetDrawer component
    // Return the updated state with the new current step
    return {
      ...state,
      currentStep: newStep,
      addedRowsDirty: false, // Reset the dirty flag when moving to step 2
    };
  }

  // Handle step transition from 2 to 1
  if (currentStep === 2 && newStep === 1) {
    return handleTransitionToStep1(state);
  }

  // Default case: just update the step
  return {...state, currentStep: newStep};
}

// Reducer function without additional parameters
function datasetDrawerReducer(
  state: DatasetDrawerState,
  action: DatasetDrawerAction
): DatasetDrawerState {
  switch (action.type) {
    case ACTION_TYPES.SET_CURRENT_STEP: {
      // Extract parameters from the action payload
      const newStep = action.payload.step;
      const currentStep = state.currentStep;
      const setAddedRows = action.payload.setAddedRows;

      // Use the helper function to handle the step transition
      return handleStepTransition(state, newStep, currentStep, setAddedRows);
    }

    case ACTION_TYPES.SET_DATASETS:
      return {...state, datasets: action.payload};

    case ACTION_TYPES.SELECT_DATASET: {
      // When selecting a dataset, we need to reset related state
      return {
        ...state,
        selectedDataset: action.payload,
        isCreatingNew: action.payload === null,
        addedRowsDirty: true, // Mark rows as dirty when selecting a dataset
      };
    }

    case ACTION_TYPES.SET_IS_CREATING_NEW:
      return {
        ...state,
        isCreatingNew: action.payload,
        // If switching to creating new, ensure dataset is null
        selectedDataset: action.payload ? null : state.selectedDataset,
      };

    case ACTION_TYPES.SET_NEW_DATASET_NAME:
      return {...state, newDatasetName: action.payload};

    case ACTION_TYPES.SET_FIELD_MAPPINGS:
      // For new datasets, update the dataset object schema to match the field mappings
      if (state.isCreatingNew && state.datasetObject) {
        const updatedSchema = action.payload.map(mapping => ({
          name: mapping.targetField,
          type: 'string', // Default type
        }));

        return {
          ...state,
          fieldMappings: action.payload,
          datasetObject: {
            ...state.datasetObject,
            schema: updatedSchema,
          },
        };
      }
      return {
        ...state,
        fieldMappings: action.payload,
        addedRowsDirty: true,
      };

    case ACTION_TYPES.SET_FIELD_CONFIGS:
      return {
        ...state,
        fieldConfigs: action.payload,
        addedRowsDirty: true,
      };

    case ACTION_TYPES.SET_DATASET_OBJECT:
      return {...state, datasetObject: action.payload};

    case ACTION_TYPES.SET_SOURCE_SCHEMA:
      return {...state, sourceSchema: action.payload};

    case ACTION_TYPES.SET_TARGET_SCHEMA: {
      // When the target schema is set (after dataset selection), suggest field mappings
      const mappings = suggestFieldMappings(
        state.sourceSchema,
        action.payload,
        state.selectedDataset ? state.fieldMappings : []
      );

      return {
        ...state,
        targetSchema: action.payload,
        // Update field mappings with suggestions
        fieldMappings: mappings,
      };
    }

    case ACTION_TYPES.SET_DRAWER_WIDTH:
      return {...state, drawerWidth: action.payload};

    case ACTION_TYPES.SET_IS_FULLSCREEN:
      return {...state, isFullscreen: action.payload};

    case ACTION_TYPES.SET_IS_CREATING:
      return {...state, isCreating: action.payload};

    case ACTION_TYPES.SET_ERROR:
      return {...state, error: action.payload};

    case ACTION_TYPES.SET_IS_NAME_VALID:
      return {...state, isNameValid: action.payload};

    case ACTION_TYPES.SET_PROCESSED_ROWS:
      return {...state, processedRows: action.payload};

    case ACTION_TYPES.PROCESS_ROWS_FOR_EDITOR: {
      if (
        !action.payload?.selectedCalls ||
        action.payload.selectedCalls.length === 0
      ) {
        return state;
      }

      const {selectedCalls, setAddedRows} = action.payload;
      const isNewDataset = state.selectedDataset === null;

      try {
        // Map calls to dataset rows
        let mappedRows = mapCallsToDatasetRows(
          selectedCalls,
          state.fieldMappings
        );

        // Apply filtering for new datasets
        if (isNewDataset) {
          const targetFields = new Set(
            state.fieldMappings.map(m => m.targetField)
          );
          mappedRows = mappedRows.map(row => {
            const {___weave, ...rest} = row;
            const filteredData = Object.fromEntries(
              Object.entries(rest).filter(([key]) => targetFields.has(key))
            );
            return {
              ___weave,
              ...filteredData,
            };
          });
        }

        // Process rows with schema-based filtering
        const processedRowsMap = createProcessedRowsMap(
          mappedRows,
          state.datasetObject
        );

        // Update the editor with the processed rows
        if (setAddedRows) {
          setAddedRows(processedRowsMap);
        }

        return {
          ...state,
          processedRows: processedRowsMap,
          addedRowsDirty: false,
        };
      } catch (error) {
        console.error('Error processing rows for editor:', error);
        return state;
      }
    }

    case ACTION_TYPES.RESET_EDIT_STATE:
      // This now also resets the processed rows and dirty flag
      return {...state, processedRows: new Map(), addedRowsDirty: false};

    case ACTION_TYPES.RESET_DRAWER_STATE:
      // Reset everything to initial state
      return initialState;

    case ACTION_TYPES.SET_USER_MODIFIED_MAPPINGS:
      return {...state, addedRowsDirty: action.payload};

    default:
      return state;
  }
}

// Create context
interface DatasetDrawerContextType {
  state: DatasetDrawerState;
  dispatch: Dispatch<DatasetDrawerAction>;

  // Memoized actions
  setCurrentStep: (step: number) => void;
  handleDatasetSelect: (dataset: ObjectVersionSchema | null) => void;
  handleMappingChange: (mappings: FieldMapping[]) => void;
  handleDatasetObjectLoaded: (datasetObj: any, rowsData?: any[]) => void;
  setSourceSchema: (schema: any[]) => void;
  resetDrawerState: () => void;
  handleNext: () => void;
  handleBack: () => void;
  processRowsForEditor: (selectedCalls: CallData[]) => void;
  resetEditState: () => void;

  // Row computation
  getMappedRows: (
    calls: CallData[],
    mappings: FieldMapping[],
    isNewDataset: boolean
  ) => Array<{___weave: {id: string; isNew: boolean}; [key: string]: any}>;

  // Derived state
  isNextDisabled: boolean;

  // Editor context access
  editorContext: ReturnType<typeof useDatasetEditContext>;
}

const DatasetDrawerContext = createContext<
  DatasetDrawerContextType | undefined
>(undefined);

// Provider component
interface DatasetDrawerProviderProps {
  children: ReactNode;
  selectedCallIds: string[];
  onClose: () => void;
  entity: string;
  project: string;
}

// Wrapper component that provides both contexts
export const DatasetDrawerProvider: React.FC<DatasetDrawerProviderProps> = ({
  children,
  selectedCallIds,
  onClose,
  entity,
  project,
}) => {
  return (
    <DatasetEditProvider>
      <DatasetDrawerProviderInner
        selectedCallIds={selectedCallIds}
        onClose={onClose}
        entity={entity}
        project={project}>
        {children}
      </DatasetDrawerProviderInner>
    </DatasetEditProvider>
  );
};

// Inner provider that has access to the editor context
const DatasetDrawerProviderInner: React.FC<DatasetDrawerProviderProps> = ({
  children,
  selectedCallIds,
  onClose,
  entity,
  project,
}) => {
  // Access the dataset editor context
  const editorContext = useDatasetEditContext();
  const {setAddedRows, resetEditState: resetEditorState} = editorContext;

  // Custom reducer that passes additional parameters - we no longer need to pass selectedCalls
  const wrappedReducer = useCallback(
    (drawerState: DatasetDrawerState, action: DatasetDrawerAction) => {
      return datasetDrawerReducer(drawerState, action);
    },
    []
  );

  const [state, dispatch] = useReducer(wrappedReducer, initialState);

  // Memoized action dispatchers
  const setCurrentStep = useCallback(
    (step: number) =>
      dispatch({
        type: ACTION_TYPES.SET_CURRENT_STEP,
        payload: {step, setAddedRows: step === 2 ? setAddedRows : undefined},
      }),
    [setAddedRows]
  );

  const handleDatasetSelect = useCallback(
    (dataset: ObjectVersionSchema | null) => {
      dispatch({type: ACTION_TYPES.SELECT_DATASET, payload: dataset});
      // If changing datasets, we might want to clear any edits
      if (dataset?.objectId !== state.selectedDataset?.objectId) {
        resetEditorState();
      }
    },
    [dispatch, state.selectedDataset, resetEditorState]
  );

  const handleMappingChange = useCallback((mappings: FieldMapping[]) => {
    dispatch({type: ACTION_TYPES.SET_FIELD_MAPPINGS, payload: mappings});
    // Mark that the rows need reprocessing
    dispatch({type: ACTION_TYPES.SET_USER_MODIFIED_MAPPINGS, payload: true});
  }, []);

  const setSourceSchema = useCallback((schema: any[]) => {
    dispatch({type: ACTION_TYPES.SET_SOURCE_SCHEMA, payload: schema});
  }, []);

  const resetDrawerState = useCallback(() => {
    dispatch({type: ACTION_TYPES.RESET_DRAWER_STATE});
    // Also reset the editor state
    resetEditorState();
  }, [dispatch, resetEditorState]);

  const handleDatasetObjectLoaded = useCallback(
    (datasetObj: any, rowsData?: any[]) => {
      dispatch({type: ACTION_TYPES.SET_DATASET_OBJECT, payload: datasetObj});

      // If rows data is provided, infer the target schema
      if (rowsData && rowsData.length > 0) {
        const inferredSchema = inferSchema(rowsData.map(row => row.val));

        // Setting the target schema will also trigger field mapping suggestions
        // in the reducer's SET_TARGET_SCHEMA case
        dispatch({
          type: ACTION_TYPES.SET_TARGET_SCHEMA,
          payload: inferredSchema,
        });
      }
    },
    [dispatch]
  );

  // Callback to compute mapped rows from calls and field mappings
  // This is kept for backward compatibility but the main functionality has moved to the reducer
  const getMappedRows = useCallback(
    (
      calls: CallData[],
      mappings: FieldMapping[],
      isNewDataset: boolean
    ): Array<{
      ___weave: {id: string; isNew: boolean};
      [key: string]: any;
    }> => {
      try {
        // Validate inputs
        if (!Array.isArray(calls) || !Array.isArray(mappings)) {
          console.warn('Invalid inputs to getMappedRows:', {
            callsIsArray: Array.isArray(calls),
            mappingsIsArray: Array.isArray(mappings),
          });
          return [];
        }

        // Only proceed if we have calls and valid field mappings
        if (!calls.length || !mappings.length) {
          return [];
        }

        // The core mapping logic is now in the reducer, but we keep this method for backward compatibility
        let mappedRows: Array<{
          ___weave: {id: string; isNew: boolean};
          [key: string]: any;
        }> = [];
        try {
          mappedRows = mapCallsToDatasetRows(calls, mappings);
        } catch (error) {
          console.error('Error in mapCallsToDatasetRows:', error);
          return [];
        }

        // For new datasets, filter fields (same as in the reducer)
        if (isNewDataset) {
          const targetFields = new Set(mappings.map(m => m.targetField));
          // Use proper typing to avoid null values
          return mappedRows
            .map(row => {
              try {
                if (!row || typeof row !== 'object' || !row.___weave) {
                  console.warn('Invalid row structure:', row);
                  return undefined; // Use undefined instead of null for easier filtering
                }

                const {___weave, ...rest} = row;
                const filteredData = Object.fromEntries(
                  Object.entries(rest).filter(([key]) => targetFields.has(key))
                );
                return {
                  ___weave,
                  ...filteredData,
                };
              } catch (rowError) {
                console.error('Error processing row:', rowError);
                return undefined;
              }
            })
            .filter(
              (
                row
              ): row is {
                ___weave: {id: string; isNew: boolean};
                [key: string]: any;
              } => row !== undefined
            ); // Type-safe filter
        }

        return mappedRows;
      } catch (error) {
        console.error('Unhandled error in getMappedRows:', error);
        return [];
      }
    },
    []
  );

  // Navigation handlers
  const handleNext = useCallback(() => {
    const isNewDataset = state.selectedDataset === null;

    if (isNewDataset) {
      if (!state.newDatasetName?.trim()) {
        dispatch({
          type: ACTION_TYPES.SET_ERROR,
          payload: 'Please enter a dataset name',
        });
        return;
      }

      if (!state.fieldConfigs.some(config => config.included)) {
        dispatch({
          type: ACTION_TYPES.SET_ERROR,
          payload: 'Please select at least one field to include',
        });
        return;
      }

      // Always recreate field mappings from field configs for new datasets
      // This ensures that changes to field inclusion are reflected in the mappings
      const newMappings = state.fieldConfigs
        .filter(config => config.included)
        .map(config => ({
          sourceField: config.sourceField,
          targetField: config.targetField,
        }));
      dispatch({type: ACTION_TYPES.SET_FIELD_MAPPINGS, payload: newMappings});

      // Create a fresh dataset object structure for new datasets
      const newDatasetObject = {
        rows: [],
        schema: state.fieldConfigs
          .filter(config => config.included)
          .map(config => ({
            name: config.targetField,
            type: 'string', // Default type
          })),
      };
      dispatch({
        type: ACTION_TYPES.SET_DATASET_OBJECT,
        payload: newDatasetObject,
      });
    }

    // Move to step 2 - Now automatically passing setAddedRows through the setCurrentStep function
    setCurrentStep(Math.min(state.currentStep + 1, 2));
  }, [
    state.selectedDataset,
    state.newDatasetName,
    state.fieldConfigs,
    state.currentStep,
    setCurrentStep,
    dispatch,
  ]);

  const handleBack = useCallback(() => {
    // When returning to step 1, the reducer will handle state changes
    setCurrentStep(Math.max(state.currentStep - 1, 1));
  }, [state.currentStep, setCurrentStep]);

  // Add processing rows for editor
  const processRowsForEditor = useCallback(
    (selectedCalls: CallData[]) => {
      dispatch({
        type: ACTION_TYPES.PROCESS_ROWS_FOR_EDITOR,
        payload: {
          selectedCalls,
          setAddedRows,
        },
      });
    },
    [dispatch, setAddedRows]
  );

  // Add reset edit state - now uses both contexts
  const resetEditState = useCallback(() => {
    dispatch({type: ACTION_TYPES.RESET_EDIT_STATE});
    resetEditorState(); // Call the editor context reset as well
  }, [resetEditorState]);

  // Compute derived state
  const isNextDisabled =
    state.currentStep === 1 &&
    ((state.selectedDataset === null &&
      (!state.newDatasetName?.trim() || !state.isNameValid)) ||
      (state.selectedDataset === null &&
        !state.fieldConfigs.some(config => config.included)));

  const contextValue = {
    state,
    dispatch,
    setCurrentStep,
    handleDatasetSelect,
    handleMappingChange,
    handleDatasetObjectLoaded,
    setSourceSchema,
    resetDrawerState,
    handleNext,
    handleBack,
    getMappedRows,
    processRowsForEditor,
    resetEditState,
    isNextDisabled,
    editorContext,
  };

  return (
    <DatasetDrawerContext.Provider value={contextValue}>
      {children}
    </DatasetDrawerContext.Provider>
  );
};

// Hook for using the context
export const useDatasetDrawer = () => {
  const context = useContext(DatasetDrawerContext);
  if (context === undefined) {
    throw new Error(
      'useDatasetDrawer must be used within a DatasetDrawerProvider'
    );
  }
  return context;
};
