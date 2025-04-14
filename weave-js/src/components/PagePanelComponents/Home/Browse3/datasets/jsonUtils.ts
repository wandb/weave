import {analyzeColumns, castDataWithColumnTypes, ParseResult} from './csvUtils';

const unnestObject = (obj: any, prefix = ''): Record<string, any> => {
  const result: Record<string, any> = {};

  for (const [key, value] of Object.entries(obj)) {
    const newKey = prefix ? `${prefix}.${key}` : key;

    if (value && typeof value === 'object' && !Array.isArray(value)) {
      Object.assign(result, unnestObject(value, newKey));
    } else {
      result[newKey] = value;
    }
  }

  return result;
};

export const parseJSON = async (file: File): Promise<ParseResult> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = e => {
      try {
        const text = e.target?.result as string;
        const data = JSON.parse(text);

        // Handle both array of objects and single object
        const rows = Array.isArray(data) ? data : [data];

        // Unnest all objects in the rows
        const unnestedRows = rows.map(row => unnestObject(row));

        // Analyze columns and cast data types
        const columns = analyzeColumns(unnestedRows);
        const castedData = castDataWithColumnTypes(unnestedRows, columns);

        resolve({
          data: castedData,
          errors: [],
          meta: {
            delimiter: '',
            linebreak: '\n',
            columns,
            totalRows: rows.length,
            encoding: 'UTF-8',
          },
        });
      } catch (error) {
        reject(error);
      }
    };
    reader.onerror = () => reject(new Error('Failed to read file'));
    reader.readAsText(file);
  });
};

export const parseJSONL = async (file: File): Promise<ParseResult> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = e => {
      try {
        const text = e.target?.result as string;
        const rows = text
          .split('\n')
          .filter(line => line.trim())
          .map(line => JSON.parse(line));

        // Unnest all objects in the rows
        const unnestedRows = rows.map(row => unnestObject(row));

        // Analyze columns and cast data types
        const columns = analyzeColumns(unnestedRows);
        const castedData = castDataWithColumnTypes(unnestedRows, columns);

        resolve({
          data: castedData,
          errors: [],
          meta: {
            delimiter: '',
            linebreak: '\n',
            columns,
            totalRows: rows.length,
            encoding: 'UTF-8',
          },
        });
      } catch (error) {
        reject(error);
      }
    };
    reader.onerror = () => reject(new Error('Failed to read file'));
    reader.readAsText(file);
  });
};
