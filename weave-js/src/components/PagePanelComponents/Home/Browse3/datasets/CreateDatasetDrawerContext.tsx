import React, {
  createContext,
  Dispatch,
  useCallback,
  useContext,
  useReducer,
} from 'react';

import {sanitizeObjectId} from '../pages/wfReactInterface/traceServerDirectClient';
import {parseCSV} from './csvUtils';
import {
  DatasetEditProvider,
  useDatasetEditContext,
} from './DatasetEditorContext';
import {DatasetObjectVal} from './EditableDatasetView';
import {parseJSON, parseJSONL} from './jsonUtils';

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
  parsedData: DatasetObjectVal | null;
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
      type: typeof CREATE_DATASET_ACTIONS.SET_PARSED_DATA;
      payload: DatasetObjectVal | null;
    }
  | {type: typeof CREATE_DATASET_ACTIONS.SET_IS_LOADING; payload: boolean}
  | {type: typeof CREATE_DATASET_ACTIONS.SET_ERROR; payload: string | null}
  | {type: typeof CREATE_DATASET_ACTIONS.SET_DRAWER_WIDTH; payload: number}
  | {type: typeof CREATE_DATASET_ACTIONS.SET_IS_FULLSCREEN; payload: boolean}
  | {type: typeof CREATE_DATASET_ACTIONS.RESET};

// Initial state
const initialState: CreateDatasetState = {
  isOpen: false,
  datasetName: '',
  parsedData: null,
  isLoading: false,
  error: null,
  drawerWidth: 800,
  isFullscreen: false,
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
  parseFile: (file: File) => Promise<void>;
  handleCloseDrawer: () => void;
  handlePublishDataset: () => void;
  clearDataset: () => void;
  editorContext: ReturnType<typeof useDatasetEditContext>;
}

// Create the context
const CreateDatasetContext = createContext<
  CreateDatasetContextType | undefined
>(undefined);

// Provider component
export const CreateDatasetProvider: React.FC<{
  children: React.ReactNode;
  onPublishDataset: (name: string, rows: any[]) => void;
}> = ({children, onPublishDataset}) => {
  return (
    <DatasetEditProvider>
      <CreateDatasetProviderInner onPublishDataset={onPublishDataset}>
        {children}
      </CreateDatasetProviderInner>
    </DatasetEditProvider>
  );
};

// Inner provider that has access to the editor context
const CreateDatasetProviderInner: React.FC<{
  children: React.ReactNode;
  onPublishDataset: (name: string, rows: any[]) => void;
}> = ({children, onPublishDataset}) => {
  const [state, dispatch] = useReducer(createDatasetReducer, initialState);
  const editorContext = useDatasetEditContext();

  interface ParseError {
    message: string;
    row?: number;
  }

  const parseFile = useCallback(
    async (file: File) => {
      dispatch({type: CREATE_DATASET_ACTIONS.SET_IS_LOADING, payload: true});
      dispatch({type: CREATE_DATASET_ACTIONS.SET_ERROR, payload: null});

      try {
        // If filename is like "dataset.csv", extract "dataset" as default name
        const fileName = file.name.split('.').slice(0, -1).join('.');
        if (fileName) {
          const sanitizedName = sanitizeObjectId(fileName);
          dispatch({
            type: CREATE_DATASET_ACTIONS.SET_DATASET_NAME,
            payload: sanitizedName,
          });
        }

        let transformedRows: Record<string, any>[];
        const fileExtension = file.name.split('.').pop()?.toLowerCase();

        switch (fileExtension) {
          case 'csv':
            const csvResult = await parseCSV(file);
            if (csvResult.errors.length > 0) {
              const errorMessage = csvResult.errors
                .map((err: ParseError) => `Row ${err.row}: ${err.message}`)
                .join('\n');
              dispatch({
                type: CREATE_DATASET_ACTIONS.SET_ERROR,
                payload: `File parsing errors:\n${errorMessage}`,
              });
              return;
            }
            transformedRows = csvResult.data;
            break;
          case 'tsv':
            const tsvResult = await parseCSV(file, '\t');
            if (tsvResult.errors.length > 0) {
              const errorMessage = tsvResult.errors
                .map((err: ParseError) => `Row ${err.row}: ${err.message}`)
                .join('\n');
              dispatch({
                type: CREATE_DATASET_ACTIONS.SET_ERROR,
                payload: `File parsing errors:\n${errorMessage}`,
              });
              return;
            }
            transformedRows = tsvResult.data;
            break;
          case 'json':
            const jsonResult = await parseJSON(file);
            transformedRows = jsonResult.data;
            break;
          case 'jsonl':
            const jsonlResult = await parseJSONL(file);
            transformedRows = jsonlResult.data;
            break;
          default:
            throw new Error(
              'Unsupported file type. Please upload a CSV, TSV, JSON, or JSONL file.'
            );
        }

        // Add weave metadata to each row
        transformedRows = transformedRows.map(
          (row: Record<string, any>, index: number) => ({
            ...row,
            ___weave: {
              id: `row-${index}`,
              index,
              isNew: true,
            },
          })
        );

        // Create a Map of the transformed rows for the editor context
        const rowsMap = new Map<string, any>(
          transformedRows.map((row: Record<string, any>) => [
            row.___weave.id,
            row,
          ])
        );

        const transformedData: DatasetObjectVal = {
          _type: 'Dataset',
          name: state.datasetName || null,
          description: null,
          rows: JSON.stringify(transformedRows),
          _class_name: 'Dataset',
          _bases: ['Object', 'BaseModel'],
        };

        dispatch({
          type: CREATE_DATASET_ACTIONS.SET_PARSED_DATA,
          payload: transformedData,
        });

        // Initialize the editor context with the transformed rows
        editorContext.setEditedRows(new Map());
        editorContext.setDeletedRows([]);
        editorContext.setAddedRows(rowsMap);
      } catch (error) {
        dispatch({
          type: CREATE_DATASET_ACTIONS.SET_ERROR,
          payload:
            error instanceof Error ? error.message : 'Failed to parse file',
        });
      } finally {
        dispatch({type: CREATE_DATASET_ACTIONS.SET_IS_LOADING, payload: false});
      }
    },
    [dispatch, state.datasetName, editorContext]
  );

  // Handle drawer close
  const handleCloseDrawer = useCallback(() => {
    dispatch({type: CREATE_DATASET_ACTIONS.SET_IS_OPEN, payload: false});
    dispatch({type: CREATE_DATASET_ACTIONS.SET_PARSED_DATA, payload: null});
    editorContext.resetEditState();
  }, [editorContext]);

  // Handle publish dataset
  const handlePublishDataset = useCallback(() => {
    if (state.parsedData) {
      // Get the updated rows from the editor context
      const rows = editorContext.getRowsNoMeta();

      // Call the onPublishDataset callback with just the name and rows
      onPublishDataset(state.datasetName, rows);

      // Reset the state
      dispatch({type: CREATE_DATASET_ACTIONS.RESET});
      editorContext.resetEditState();
    }
  }, [state.parsedData, state.datasetName, editorContext, onPublishDataset]);

  // Handle clear dataset
  const clearDataset = useCallback(() => {
    dispatch({type: CREATE_DATASET_ACTIONS.SET_PARSED_DATA, payload: null});
    editorContext.resetEditState();
  }, [editorContext]);

  return (
    <CreateDatasetContext.Provider
      value={{
        state,
        dispatch,
        parseFile,
        handleCloseDrawer,
        handlePublishDataset,
        clearDataset,
        editorContext,
      }}>
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
