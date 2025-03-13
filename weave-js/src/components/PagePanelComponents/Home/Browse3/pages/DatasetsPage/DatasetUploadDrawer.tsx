import {InputLabel} from '@material-ui/core';
import {GridColDef, GridRowSelectionModel} from '@mui/x-data-grid-pro';
import {Button} from '@wandb/weave/components/Button';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useEffect, useState} from 'react';
import {useHistory} from 'react-router-dom';

import {useWeaveflowRouteContext} from '../../context';
import {createNewDataset} from '../../datasets/datasetOperations';
import {ReusableDrawer} from '../../ReusableDrawer';
import {StyledDataGrid} from '../../StyledDataGrid';
import {TextFieldWithLabel} from '../ScorersPage/FormComponents';
import {useWFHooks} from '../wfReactInterface/context';

type ColumnRow = {
  id: number;
  selected: boolean;
  original: string;
  renamed: string;
};

export const DatasetUploadDrawer: React.FC<{
  entity: string;
  project: string;
  show: boolean;
  onClose: () => void;
}> = ({entity, project, show, onClose}) => {
  const [step, setStep] = useState<'upload' | 'configure' | 'preview'>(
    'upload'
  );
  const [file, setFile] = useState<File | null>(null);
  const [datasetName, setDatasetName] = useState<string>('');
  const [fileContent, setFileContent] = useState<any[] | null>(null);
  const [columns, setColumns] = useState<
    Array<{original: string; renamed: string; selected: boolean}>
  >([]);
  const [previewData, setPreviewData] = useState<any[] | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [publishing, setPublishing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [selectionModel, setSelectionModel] = useState<GridRowSelectionModel>(
    []
  );
  const [isDragging, setIsDragging] = useState<boolean>(false);

  const {peekingRouter} = useWeaveflowRouteContext();
  const {useObjCreate, useTableCreate} = useWFHooks();
  const tableCreate = useTableCreate();
  const objCreate = useObjCreate();
  const history = useHistory();

  // Reset form when drawer is opened
  useEffect(() => {
    if (show) {
      setStep('upload');
      setFile(null);
      setDatasetName('');
      setFileContent(null);
      setColumns([]);
      setPreviewData(null);
      setLoading(false);
      setPublishing(false);
      setError(null);
      setSelectionModel([]);
      setIsDragging(false);
    }
  }, [show]);

  // Update dataset name when file is selected (only if dataset name is empty)
  useEffect(() => {
    if (file && !datasetName) {
      // Use the file name without extension as default dataset name
      const nameWithoutExt = file.name.split('.').slice(0, -1).join('.');
      setDatasetName(nameWithoutExt);
    }
  }, [file, datasetName]);

  useEffect(() => {
    if (columns.length > 0) {
      // Initialize selection model with indices of all selected columns
      const newSelectionModel = columns
        .map((col, index) => (col.selected ? index : -1))
        .filter(index => index !== -1);
      setSelectionModel(newSelectionModel);
    }
  }, [columns]);

  const processFile = async (selectedFile: File) => {
    setError(null);

    const extension = selectedFile.name.split('.').pop()?.toLowerCase();
    if (!['csv', 'tsv', 'json', 'jsonl'].includes(extension || '')) {
      setError(
        'File type not supported. Please upload a CSV, TSV, JSON, or JSONL file.'
      );
      return;
    }

    setLoading(true);
    setFile(selectedFile);

    try {
      const content = await readFile(selectedFile);
      setFileContent(content);

      // Extract columns from the first row
      if (content && content.length > 0) {
        const firstRow = content[0];
        const extractedColumns = Object.keys(firstRow).map(column => ({
          original: column,
          renamed: column,
          selected: true,
        }));
        setColumns(extractedColumns);

        // Set preview data (first 5 rows)
        setPreviewData(content.slice(0, 5));
        setStep('configure');
      } else {
        setError('The file appears to be empty or has invalid format.');
      }
    } catch (err) {
      setError(
        `Error reading file: ${
          err instanceof Error ? err.message : String(err)
        }`
      );
    } finally {
      setLoading(false);
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) {
      return;
    }

    await processFile(selectedFile);
  };

  // Handle drag events
  const handleDragEnter = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (!isDragging) {
      setIsDragging(true);
    }
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      await processFile(files[0]);
    }
  };

  const handleColumnChange = (
    index: number,
    field: 'renamed' | 'selected',
    value: string | boolean
  ) => {
    setColumns(prev => {
      const newColumns = [...prev];
      newColumns[index] = {
        ...newColumns[index],
        [field]: value,
      };
      return newColumns;
    });
  };

  const handleSelectionModelChange = (
    newSelectionModel: GridRowSelectionModel
  ) => {
    setSelectionModel(newSelectionModel);

    // Update columns selection based on selection model
    setColumns(prev => {
      return prev.map((col, index) => ({
        ...col,
        selected: newSelectionModel.includes(index),
      }));
    });
  };

  const handleSubmit = async () => {
    if (!datasetName.trim()) {
      setError('Please enter a dataset name');
      return;
    }

    if (!file || !fileContent) {
      setError('Please upload a file');
      return;
    }

    setPublishing(true);
    setError(null);

    try {
      const finalColumns = columns.filter(col => col.selected);
      const finalRows = fileContent.map(row => {
        return Object.fromEntries(
          finalColumns.map(col => [col.renamed, row[col.original]])
        );
      });

      const projectId = `${entity}/${project}`;
      const res = await createNewDataset({
        projectId,
        entity,
        project,
        datasetName,
        rows: finalRows,
        tableCreate,
        objCreate,
        router: peekingRouter,
      });

      history.push(res.url);
      onClose();
    } catch (err) {
      setError(
        `Failed to publish dataset: ${
          err instanceof Error ? err.message : String(err)
        }`
      );
    } finally {
      setPublishing(false);
    }
  };

  // Generate rows for the columns table
  const columnsTableRows: ColumnRow[] = columns.map((col, index) => ({
    id: index,
    selected: col.selected,
    original: col.original,
    renamed: col.renamed,
  }));

  // Column definitions for the columns table
  const columnDefinitions: GridColDef[] = [
    {
      field: 'original',
      headerName: 'Original Name',
      flex: 1,
      editable: false,
    },
    {
      field: 'renamed',
      headerName: 'New Name',
      flex: 1,
      editable: true,
    },
  ];

  // Handle cell editing more explicitly
  const processRowUpdate = (newRow: ColumnRow, oldRow: ColumnRow) => {
    if (newRow.renamed !== oldRow.renamed) {
      handleColumnChange(newRow.id, 'renamed', newRow.renamed);
    }
    return newRow;
  };

  // Handle failed edit
  const handleProcessRowUpdateError = (newError: any) => {
    console.error('Error during row update:', newError);
  };

  // Generate column definitions for the preview table
  const previewColumnDefinitions = columns
    .filter(col => col.selected)
    .map(
      (col): GridColDef => ({
        field: col.original,
        headerName: col.renamed,
        flex: 1,
        editable: false,
      })
    );

  const renderUploadStep = () => (
    <Tailwind>
      <div className="flex h-full w-full flex-col gap-6 p-4">
        <div>
          <div
            className={`
              border-gray-200 bg-gray-50 rounded-md border border-dashed p-8 text-center 
              transition-all duration-200
              ${isDragging ? 'bg-blue-50 border-blue-500' : ''}
              hover:shadow-sm focus-within:border-blue-500 hover:border-blue-400
            `}
            onDragEnter={handleDragEnter}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}>
            <input
              type="file"
              accept=".csv,.tsv,.json,.jsonl"
              onChange={handleFileChange}
              className="hidden"
              id="file-upload"
            />
            <label
              htmlFor="file-upload"
              className="flex cursor-pointer flex-col items-center justify-center gap-3 outline-none">
              <div className="text-gray-500 text-4xl">
                {isDragging ? '📂' : '📄'}
              </div>
              <div className="text-gray-700 text-base font-medium">
                {isDragging
                  ? 'Drop your file here'
                  : 'Click to upload a file or drag and drop'}
              </div>
              <div className="text-gray-500 text-sm">
                Supported formats: CSV, TSV, JSON, JSONL
              </div>
            </label>
          </div>
        </div>

        {loading && (
          <div className="py-4 text-center">
            <div className="border-gray-500 mb-2 inline-block h-5 w-5 animate-spin rounded-full border-b-2 border-t-2"></div>
            <div className="text-gray-600">Processing file...</div>
          </div>
        )}

        {error && (
          <div className="bg-red-50 rounded border-l-2 border-red-400 p-3">
            <div className="flex items-center">
              <div className="flex-shrink-0">⚠️</div>
              <div className="ml-2">
                <p className="text-sm text-red-600">{error}</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </Tailwind>
  );

  const renderConfigureStep = () => (
    <Tailwind>
      <div className="flex flex-col gap-6 p-4">
        <TextFieldWithLabel
          label="Dataset Name"
          value={datasetName}
          onChange={setDatasetName}
        />

        <div>
          <div className="mb-2 flex items-center justify-between">
            <InputLabel>Columns</InputLabel>
            <div className="text-gray-500 text-xs">
              {columns.filter(c => c.selected).length} of {columns.length}{' '}
              selected
            </div>
          </div>

          <div style={{height: 400}}>
            <StyledDataGrid
              rows={columnsTableRows}
              columns={columnDefinitions}
              checkboxSelection
              disableRowSelectionOnClick
              disableColumnMenu
              disableColumnFilter
              hideFooter
              density="standard"
              columnHeaderHeight={38}
              rowHeight={38}
              onRowSelectionModelChange={handleSelectionModelChange}
              rowSelectionModel={selectionModel}
              processRowUpdate={processRowUpdate}
              onProcessRowUpdateError={handleProcessRowUpdateError}
            />
          </div>
        </div>

        {error && (
          <div className="bg-red-50 rounded border-l-2 border-red-400 p-3">
            <div className="flex items-center">
              <div className="flex-shrink-0">⚠️</div>
              <div className="ml-2">
                <p className="text-sm text-red-600">{error}</p>
              </div>
            </div>
          </div>
        )}

        <div>
          <div className="mb-2 flex items-center justify-between">
            <InputLabel>Preview</InputLabel>
            <div className="text-gray-500 text-xs">
              First {Math.min(previewData?.length || 0, 5)} rows shown
            </div>
          </div>

          <div style={{height: 200}}>
            {columns.filter(col => col.selected).length > 0 &&
            previewData &&
            previewData.length > 0 ? (
              <StyledDataGrid
                rows={previewData.map((row, index) => ({id: index, ...row}))}
                columns={previewColumnDefinitions}
                disableRowSelectionOnClick
                disableColumnMenu
                disableColumnFilter
                hideFooter
                density="compact"
                columnHeaderHeight={38}
                rowHeight={38}
              />
            ) : (
              <div className="text-gray-500 rounded border bg-white p-4 text-center">
                No columns selected for preview
              </div>
            )}
          </div>
        </div>
      </div>
    </Tailwind>
  );

  const renderContent = () => {
    switch (step) {
      case 'upload':
        return renderUploadStep();
      case 'configure':
        return renderConfigureStep();
      default:
        return null;
    }
  };

  return (
    <ReusableDrawer
      open={show}
      title="Upload Dataset"
      onClose={onClose}
      onSave={handleSubmit}
      saveDisabled={loading || publishing || !file || !datasetName.trim()}
      footer={
        <Button
          className="w-full"
          onClick={handleSubmit}
          disabled={loading || publishing || !file || !datasetName.trim()}>
          {publishing ? (
            <>
              <span className="mr-2 inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span>
              Publishing...
            </>
          ) : (
            'Upload Dataset'
          )}
        </Button>
      }>
      {renderContent()}
    </ReusableDrawer>
  );
};

const readFile = (file: File): Promise<any[]> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = e => {
      try {
        const text = e.target?.result as string;
        const extension = file.name.split('.').pop()?.toLowerCase();

        let data: any[] = [];

        if (extension === 'csv') {
          data = parseCSV(text, ',');
        } else if (extension === 'tsv') {
          data = parseCSV(text, '\t');
        } else if (extension === 'json') {
          const jsonData = JSON.parse(text);
          data = Array.isArray(jsonData) ? jsonData : [jsonData];
        } else if (extension === 'jsonl') {
          data = text
            .split('\n')
            .filter(line => line.trim())
            .map(line => JSON.parse(line));
        }

        resolve(data);
      } catch (err) {
        reject(err);
      }
    };

    reader.onerror = () => {
      reject(new Error('Error reading file'));
    };

    reader.readAsText(file);
  });
};

const parseCSV = (text: string, delimiter: string): any[] => {
  const lines = text.split('\n');
  if (lines.length === 0) {
    return [];
  }

  const headers = lines[0]
    .split(delimiter)
    .map(h => h.trim().replace(/^"|"$/g, ''));

  return lines
    .slice(1)
    .filter(line => line.trim()) // Skip empty lines
    .map(line => {
      const values = line
        .split(delimiter)
        .map(v => v.trim().replace(/^"|"$/g, ''));
      const row: Record<string, string> = {};

      headers.forEach((header, index) => {
        row[header] = values[index] || '';
      });

      return row;
    });
};
