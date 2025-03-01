import React, {
  createContext,
  Dispatch,
  ReactNode,
  useCallback,
  useContext,
  useReducer,
} from 'react';
import {v4 as uuidv4} from 'uuid';

import {sanitizeObjectId} from '../pages/wfReactInterface/traceServerDirectClient';
import {
  DatasetEditProvider,
  useDatasetEditContext,
} from './DatasetEditorContext';

// Action type constants
export const CREATE_DATASET_ACTIONS = {
  SET_IS_OPEN: 'SET_IS_OPEN',
  SET_DATASET_NAME: 'SET_DATASET_NAME',
  SET_DATASET_DESCRIPTION: 'SET_DATASET_DESCRIPTION',
  SET_PARSED_DATA: 'SET_PARSED_DATA',
  SET_IS_LOADING: 'SET_IS_LOADING',
  SET_ERROR: 'SET_ERROR',
  SET_DRAWER_WIDTH: 'SET_DRAWER_WIDTH',
  SET_IS_FULLSCREEN: 'SET_IS_FULLSCREEN',
  RESET: 'RESET',
} as const;

// State interface
export interface CreateDatasetState {
  isOpen: boolean;
  datasetName: string;
  datasetDescription: string;
  parsedData: any | null;
  isLoading: boolean;
  error: string | null;
  drawerWidth: number;
  isFullscreen: boolean;
}

// Action types
export type CreateDatasetAction =
  | {type: typeof CREATE_DATASET_ACTIONS.SET_IS_OPEN; payload: boolean}
  | {type: typeof CREATE_DATASET_ACTIONS.SET_DATASET_NAME; payload: string}
  | {
      type: typeof CREATE_DATASET_ACTIONS.SET_DATASET_DESCRIPTION;
      payload: string;
    }
  | {type: typeof CREATE_DATASET_ACTIONS.SET_PARSED_DATA; payload: any}
  | {type: typeof CREATE_DATASET_ACTIONS.SET_IS_LOADING; payload: boolean}
  | {type: typeof CREATE_DATASET_ACTIONS.SET_ERROR; payload: string | null}
  | {type: typeof CREATE_DATASET_ACTIONS.SET_DRAWER_WIDTH; payload: number}
  | {type: typeof CREATE_DATASET_ACTIONS.SET_IS_FULLSCREEN; payload: boolean}
  | {type: typeof CREATE_DATASET_ACTIONS.RESET};

// Initial state
const initialState: CreateDatasetState = {
  isOpen: false,
  datasetName: '',
  datasetDescription: '',
  parsedData: null,
  isLoading: false,
  error: null,
  drawerWidth: 800,
  isFullscreen: false,
};

// CSV Parser implementation
const parseCSV = (
  csvText: string
): {data: any[]; errors: Array<{message: string}>} => {
  try {
    // Split the CSV into lines and filter out empty lines
    const lines = csvText.split('\n').filter(line => line.trim() !== '');

    if (lines.length === 0) {
      return {
        data: [],
        errors: [{message: 'CSV file is empty'}],
      };
    }

    // Parse CSV line with proper handling of quoted fields and commas
    const parseCSVLine = (line: string): string[] => {
      const values: string[] = [];
      let inQuote = false;
      let currentValue = '';

      for (let i = 0; i < line.length; i++) {
        const char = line[i];

        if (char === '"' && (i === 0 || line[i - 1] !== '\\')) {
          inQuote = !inQuote;
        } else if (char === ',' && !inQuote) {
          values.push(currentValue.trim());
          currentValue = '';
        } else {
          currentValue += char;
        }
      }

      // Add the last value
      values.push(currentValue.trim());
      return values;
    };

    // Parse headers
    const headers = parseCSVLine(lines[0]);

    // Parse data rows
    const data = [];
    for (let i = 1; i < lines.length; i++) {
      if (!lines[i].trim()) {
        continue;
      }

      const values = parseCSVLine(lines[i]);
      const row: Record<string, any> = {};

      // Map values to headers, handling case where values might be shorter than headers
      headers.forEach((header, index) => {
        row[header] = values[index] !== undefined ? values[index] : '';
      });

      data.push(row);
    }

    return {
      data,
      errors: [],
    };
  } catch (error) {
    return {
      data: [],
      errors: [
        {
          message:
            error instanceof Error ? error.message : 'Unknown parsing error',
        },
      ],
    };
  }
};

// Reducer function
function createDatasetReducer(
  state: CreateDatasetState,
  action: CreateDatasetAction
): CreateDatasetState {
  switch (action.type) {
    case CREATE_DATASET_ACTIONS.SET_IS_OPEN:
      return {...state, isOpen: action.payload};
    case CREATE_DATASET_ACTIONS.SET_DATASET_NAME:
      return {...state, datasetName: action.payload};
    case CREATE_DATASET_ACTIONS.SET_DATASET_DESCRIPTION:
      return {...state, datasetDescription: action.payload};
    case CREATE_DATASET_ACTIONS.SET_PARSED_DATA:
      return {...state, parsedData: action.payload};
    case CREATE_DATASET_ACTIONS.SET_IS_LOADING:
      return {...state, isLoading: action.payload};
    case CREATE_DATASET_ACTIONS.SET_ERROR:
      return {...state, error: action.payload};
    case CREATE_DATASET_ACTIONS.SET_DRAWER_WIDTH:
      return {...state, drawerWidth: action.payload};
    case CREATE_DATASET_ACTIONS.SET_IS_FULLSCREEN:
      return {...state, isFullscreen: action.payload};
    case CREATE_DATASET_ACTIONS.RESET:
      return initialState;
    default:
      return state;
  }
}

// Context interface
interface CreateDatasetContextType {
  state: CreateDatasetState;
  dispatch: Dispatch<CreateDatasetAction>;
  parseCSVFile: (file: File) => Promise<void>;
  handleCloseDrawer: () => void;
  handlePublishDataset: () => void;
  editorContext: ReturnType<typeof useDatasetEditContext>;
}

// Create the context
const CreateDatasetContext = createContext<
  CreateDatasetContextType | undefined
>(undefined);

// Provider component
interface CreateDatasetProviderProps {
  children: ReactNode;
  onPublishDataset: (dataset: any) => void;
}

// Wrapper component that provides both contexts
export const CreateDatasetProvider: React.FC<CreateDatasetProviderProps> = ({
  children,
  onPublishDataset: onSaveDataset,
}) => {
  return (
    <DatasetEditProvider>
      <CreateDatasetProviderInner onPublishDataset={onSaveDataset}>
        {children}
      </CreateDatasetProviderInner>
    </DatasetEditProvider>
  );
};

// Inner provider that has access to the editor context
const CreateDatasetProviderInner: React.FC<CreateDatasetProviderProps> = ({
  children,
  onPublishDataset: onSaveDataset,
}) => {
  // Access the dataset editor context
  const editorContext = useDatasetEditContext();
  const {setAddedRows, resetEditState} = editorContext;

  const [state, dispatch] = useReducer(createDatasetReducer, initialState);

  // Parse CSV file with robust handling
  const parseCSVFile = useCallback(
    async (file: File) => {
      dispatch({type: CREATE_DATASET_ACTIONS.SET_IS_LOADING, payload: true});
      dispatch({type: CREATE_DATASET_ACTIONS.SET_ERROR, payload: null});

      try {
        // Set default dataset name from file name
        if (!state.datasetName) {
          const fileName = file.name.replace(/\.[^/.]+$/, ''); // Remove extension
          const sanitizedName = sanitizeObjectId(fileName);
          dispatch({
            type: CREATE_DATASET_ACTIONS.SET_DATASET_NAME,
            payload: sanitizedName,
          });
        }

        // Read the file content as text
        const text = await file.text();

        // Parse the CSV
        const result = parseCSV(text);

        if (result.errors.length > 0) {
          const errorMessage = result.errors.map(err => err.message).join(', ');
          dispatch({
            type: CREATE_DATASET_ACTIONS.SET_ERROR,
            payload: `CSV parsing errors: ${errorMessage}`,
          });
          dispatch({
            type: CREATE_DATASET_ACTIONS.SET_IS_LOADING,
            payload: false,
          });
          return;
        }

        if (result.data.length === 0) {
          dispatch({
            type: CREATE_DATASET_ACTIONS.SET_ERROR,
            payload: 'No data found in CSV file',
          });
          dispatch({
            type: CREATE_DATASET_ACTIONS.SET_IS_LOADING,
            payload: false,
          });
          return;
        }

        // Create dataset object structure
        const dataset = {
          _type: 'Dataset',
          name: state.datasetName || file.name.replace(/\.[^/.]+$/, ''),
          description: state.datasetDescription || '',
          rows: JSON.stringify(result.data),
          _class_name: 'Dataset',
          _bases: ['Object', 'BaseModel'],
        };

        dispatch({
          type: CREATE_DATASET_ACTIONS.SET_PARSED_DATA,
          payload: dataset,
        });

        // Prepare rows for the editor with proper structure
        const rows = new Map();
        result.data.forEach(row => {
          const id = `new-${uuidv4()}`;
          rows.set(id, {
            ___weave: {
              id,
              isNew: true,
            },
            ...row,
          });
        });

        // Update the editor state
        setAddedRows(rows);
      } catch (error) {
        console.error('Error parsing CSV:', error);
        dispatch({
          type: CREATE_DATASET_ACTIONS.SET_ERROR,
          payload:
            error instanceof Error
              ? error.message
              : 'Unknown error parsing CSV',
        });
      } finally {
        dispatch({
          type: CREATE_DATASET_ACTIONS.SET_IS_LOADING,
          payload: false,
        });
      }
    },
    [state.datasetName, state.datasetDescription, setAddedRows]
  );

  // Handle drawer close
  const handleCloseDrawer = useCallback(() => {
    dispatch({type: CREATE_DATASET_ACTIONS.SET_IS_OPEN, payload: false});
    dispatch({type: CREATE_DATASET_ACTIONS.SET_PARSED_DATA, payload: null});
    resetEditState();
  }, [resetEditState]);

  // Handle save dataset
  const handleSaveDataset = useCallback(() => {
    if (state.parsedData) {
      // Get the updated rows from the editor context
      const rows = editorContext.getRowsNoMeta();

      // Update the dataset with the edited rows
      const updatedDataset = {
        ...state.parsedData,
        name: state.datasetName,
        description: state.datasetDescription,
        rows: JSON.stringify(rows),
      };

      // Call the onSaveDataset callback
      onSaveDataset(updatedDataset);

      // Reset the state
      dispatch({type: CREATE_DATASET_ACTIONS.RESET});
      resetEditState();
    }
  }, [
    state.parsedData,
    state.datasetName,
    state.datasetDescription,
    editorContext,
    onSaveDataset,
    resetEditState,
  ]);

  // Handle publish dataset - similar to save but marked for publication
  const handlePublishDataset = useCallback(() => {
    if (state.parsedData) {
      // Get the updated rows from the editor context
      const rows = editorContext.getRowsNoMeta();

      // Update the dataset with the edited rows and mark it for publication
      const updatedDataset = {
        ...state.parsedData,
        name: state.datasetName,
        description: state.datasetDescription,
        rows: JSON.stringify(rows),
        publishNow: true, // Flag to indicate this should be published immediately
      };

      // Call the onSaveDataset callback with the publish flag
      onSaveDataset(updatedDataset);

      // Reset the state
      dispatch({type: CREATE_DATASET_ACTIONS.RESET});
      resetEditState();
    }
  }, [
    state.parsedData,
    state.datasetName,
    state.datasetDescription,
    editorContext,
    onSaveDataset,
    resetEditState,
  ]);

  const contextValue = {
    state,
    dispatch,
    parseCSVFile,
    handleCloseDrawer,
    handleSaveDataset,
    handlePublishDataset,
    editorContext,
  };

  return (
    <CreateDatasetContext.Provider value={contextValue}>
      {children}
    </CreateDatasetContext.Provider>
  );
};

// Hook for using the context
export const useCreateDatasetContext = () => {
  const context = useContext(CreateDatasetContext);
  if (context === undefined) {
    throw new Error(
      'useCreateDatasetContext must be used within a CreateDatasetProvider'
    );
  }
  return context;
};
