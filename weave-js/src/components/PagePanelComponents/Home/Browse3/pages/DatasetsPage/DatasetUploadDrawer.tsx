import {Button} from '@wandb/weave/components/Button';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useEffect, useState} from 'react';

import {useWeaveflowRouteContext} from '../../context';
import {createNewDataset} from '../../datasets/datasetOperations';
import {ReusableDrawer} from '../../ReusableDrawer';
import {useWFHooks} from '../wfReactInterface/context';

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
  const [error, setError] = useState<string | null>(null);

  const {peekingRouter} = useWeaveflowRouteContext();
  const {useObjCreate, useTableCreate} = useWFHooks();
  const tableCreate = useTableCreate();
  const objCreate = useObjCreate();

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
      setError(null);
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

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) {
      return;
    }

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

  const handleSubmit = async () => {
    if (!datasetName.trim()) {
      setError('Please enter a dataset name');
      return;
    }

    if (!file || !fileContent) {
      setError('Please upload a file');
      return;
    }

    const finalColumns = columns.filter(col => col.selected);
    const finalRows = fileContent.map(row => {
      return Object.fromEntries(
        finalColumns.map(col => [col.renamed, row[col.original]])
      );
    });

    const projectId = `${entity}/${project}`;
    await createNewDataset({
      projectId,
      entity,
      project,
      datasetName,
      rows: finalRows,
      tableCreate,
      objCreate,
      router: peekingRouter,
    });

    onClose();
  };

  const renderUploadStep = () => (
    <Tailwind>
      <div className="flex flex-col gap-8 p-2">
        <div>
          <div className="border-blue-200 bg-blue-50 hover:bg-blue-100 rounded-lg border-2 border-dashed p-8 text-center transition-colors duration-200 hover:border-blue-300">
            <input
              type="file"
              accept=".csv,.tsv,.json,.jsonl"
              onChange={handleFileChange}
              className="hidden"
              id="file-upload"
            />
            <label
              htmlFor="file-upload"
              className="flex cursor-pointer flex-col items-center justify-center gap-3">
              <div className="text-5xl text-blue-400">📄</div>
              <div className="text-lg font-medium text-blue-700">
                Click to upload a file
              </div>
              <div className="text-sm font-semibold text-blue-500">
                Supported formats: CSV, TSV, JSON, JSONL
              </div>
            </label>
          </div>
        </div>

        {loading && (
          <div className="py-4 text-center">
            <div className="mb-2 inline-block h-8 w-8 animate-spin rounded-full border-b-2 border-t-2 border-blue-500"></div>
            <div>Processing file...</div>
          </div>
        )}

        {error && (
          <div className="bg-red-50 rounded border-l-4 border-red-500 p-4">
            <div className="flex">
              <div className="flex-shrink-0">⚠️</div>
              <div className="ml-3">
                <p className="text-sm text-red-700">{error}</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </Tailwind>
  );

  const renderConfigureStep = () => (
    <Tailwind>
      <div className="flex flex-col gap-8 p-2">
        <div>
          <label
            htmlFor="dataset-name"
            className="mb-3 block text-base font-medium">
            Dataset Name
          </label>
          <input
            type="text"
            id="dataset-name"
            value={datasetName}
            onChange={e => setDatasetName(e.target.value)}
            className="border-gray-300 w-full rounded-md border px-4 py-2 outline-none transition-all duration-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-500"
            placeholder="Enter dataset name"
          />
        </div>

        <div>
          <div className="mb-3 flex items-center justify-between">
            <label className="block text-base font-medium">Columns</label>
            <div className="text-gray-500 text-sm">
              {columns.filter(c => c.selected).length} of {columns.length}{' '}
              selected
            </div>
          </div>

          <div className="border-gray-300 shadow-sm overflow-hidden rounded-lg border">
            <div className="max-h-[400px] overflow-auto">
              <table className="w-full border-collapse">
                <thead className="bg-gray-100 sticky top-0 z-10">
                  <tr>
                    <th className="text-gray-700 border-gray-200 w-[70px] border-b px-4 py-3 text-left font-semibold">
                      Include
                    </th>
                    <th className="text-gray-700 border-gray-200 w-[45%] border-b px-4 py-3 text-left font-semibold">
                      Original Name
                    </th>
                    <th className="text-gray-700 border-gray-200 w-[45%] border-b px-4 py-3 text-left font-semibold">
                      New Name
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {columns.map((column, index) => (
                    <tr
                      key={index}
                      className={`border-gray-200 border-b ${
                        index % 2 === 0 ? 'bg-white' : 'bg-gray-50'
                      } hover:bg-blue-50 transition-colors duration-150`}>
                      <td className="px-4 py-3 align-middle">
                        <input
                          type="checkbox"
                          checked={column.selected}
                          onChange={e =>
                            handleColumnChange(
                              index,
                              'selected',
                              e.target.checked
                            )
                          }
                          className="form-checkbox border-gray-300 h-5 w-5 rounded text-blue-600 focus:ring-blue-500"
                        />
                      </td>
                      <td className="px-4 py-3 align-middle">
                        <div
                          className="max-w-full overflow-hidden text-ellipsis whitespace-nowrap"
                          title={column.original}>
                          {column.original}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <input
                          type="text"
                          value={column.renamed}
                          onChange={e =>
                            handleColumnChange(index, 'renamed', e.target.value)
                          }
                          className="border-gray-300 py-1.5 w-full rounded border px-3 text-sm outline-none transition-all duration-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-500"
                          title={column.renamed}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {error && (
          <div className="bg-red-50 rounded border-l-4 border-red-500 p-4">
            <div className="flex">
              <div className="flex-shrink-0">⚠️</div>
              <div className="ml-3">
                <p className="text-sm text-red-700">{error}</p>
              </div>
            </div>
          </div>
        )}

        <div>
          <div className="mb-3 flex items-center justify-between">
            <label className="block text-base font-medium">Preview</label>
            <div className="text-gray-500 text-xs italic">
              First {Math.min(previewData?.length || 0, 5)} rows shown
            </div>
          </div>

          <div className="border-gray-300 shadow-sm overflow-hidden rounded-lg border bg-white">
            <div className="max-h-[200px] overflow-auto">
              {columns.filter(col => col.selected).length > 0 ? (
                <table className="w-full border-collapse">
                  <thead className="bg-gray-100 sticky top-0 z-10">
                    <tr>
                      {columns
                        .filter(col => col.selected)
                        .map((col, index) => (
                          <th
                            key={index}
                            className="text-gray-700 border-gray-200 whitespace-nowrap border-b px-3 py-2 text-left text-sm font-semibold">
                            <div
                              className="max-w-[150px] overflow-hidden text-ellipsis"
                              title={col.renamed}>
                              {col.renamed}
                            </div>
                          </th>
                        ))}
                    </tr>
                  </thead>
                  <tbody>
                    {previewData?.map((row, rowIndex) => (
                      <tr
                        key={rowIndex}
                        className={`border-gray-200 border-b ${
                          rowIndex % 2 === 0 ? 'bg-white' : 'bg-gray-50'
                        }`}>
                        {columns
                          .filter(col => col.selected)
                          .map((col, colIndex) => (
                            <td key={colIndex} className="px-3 py-2 text-sm">
                              <div
                                className="max-w-[150px] overflow-hidden text-ellipsis whitespace-nowrap"
                                title={String(row[col.original] ?? '')}>
                                {String(row[col.original] ?? '')}
                              </div>
                            </td>
                          ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="text-gray-500 p-4 text-center">
                  No columns selected for preview
                </div>
              )}
            </div>
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
      saveDisabled={loading || !file || !datasetName.trim()}
      footer={
        <Button
          className="w-full"
          onClick={handleSubmit}
          disabled={loading || !file || !datasetName.trim()}>
          Upload Dataset
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
