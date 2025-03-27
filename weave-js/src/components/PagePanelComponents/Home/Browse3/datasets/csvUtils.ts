import Papa, {ParseError, ParseResult as PapaParseResult} from 'papaparse';

export interface ParsedColumn {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'date' | 'null';
  sample: any;
}

export interface ParseResult {
  data: any[];
  errors: Array<{message: string; row?: number}>;
  meta: {
    delimiter: string;
    linebreak: string;
    columns: ParsedColumn[];
    totalRows: number;
    encoding: string;
  };
}

export const detectDataType = (value: any): ParsedColumn['type'] => {
  if (value === null || value === undefined || value === '') {
    return 'null';
  }

  // If it's already a boolean type, immediately return boolean
  if (typeof value === 'boolean') {
    return 'boolean';
  }

  if (
    typeof value === 'string' &&
    (value === 'Infinity' || value === '-Infinity')
  ) {
    return 'string';
  }

  // Check for booleans before numbers to avoid treating "true"/"false" as NaN
  if (
    typeof value === 'string' &&
    (value.toLowerCase() === 'true' || value.toLowerCase() === 'false')
  ) {
    return 'boolean';
  }

  if (!isNaN(Number(value)) && value.toString().trim() !== '') {
    return 'number';
  }

  // Try parsing as date - check for common date formats
  if (typeof value === 'string') {
    const date = new Date(value);
    // Ensure it's a valid date and the original string somewhat looks like a date
    // to avoid false positives
    if (
      !isNaN(date.getTime()) &&
      (value.includes('-') || value.includes('/') || /\d{8,}/.test(value))
    ) {
      return 'date';
    }
  }

  return 'string';
};

export const analyzeColumns = (data: any[]): ParsedColumn[] => {
  if (data.length === 0) {
    return [];
  }

  const firstRow = data[0];
  const columns: ParsedColumn[] = [];

  Object.keys(firstRow).forEach(key => {
    // Look at first 100 non-null values to better determine type
    const values = data
      .slice(0, 100)
      .map(row => row[key])
      .filter(val => val !== null && val !== undefined && val !== '');

    const sample = values[0];

    // If no valid values found, mark as null type
    if (values.length === 0) {
      columns.push({
        name: key,
        type: 'null',
        sample: null,
      });
      return;
    }

    // Special handling for potential boolean columns
    // Check if all values are either true, false, "true", "false", "yes", "no", "1", "0", etc.
    const isPotentialBooleanColumn = values.every(val => {
      if (typeof val === 'boolean') {
        return true;
      }
      if (typeof val === 'string') {
        const normalized = val.toLowerCase().trim();
        return ['true', 'false', 'yes', 'no', 'y', 'n', '1', '0'].includes(
          normalized
        );
      }
      if (typeof val === 'number') {
        return val === 0 || val === 1;
      }
      return false;
    });

    if (isPotentialBooleanColumn && values.length > 0) {
      columns.push({
        name: key,
        type: 'boolean',
        sample,
      });
      return;
    }

    // Continue with regular type detection if not a boolean column
    const initialType = detectDataType(sample);
    const allSameType = values.every(
      val => detectDataType(val) === initialType
    );

    columns.push({
      name: key,
      type: allSameType ? initialType : 'string', // Fall back to string if mixed types
      sample,
    });
  });

  return columns;
};

// Cast a single value based on the specified type
export const castValueToType = (
  value: any,
  type: ParsedColumn['type']
): any => {
  if (value === null || value === undefined || value === '') {
    return null;
  }

  // If the value is already the correct type, return it directly
  if (
    (type === 'boolean' && typeof value === 'boolean') ||
    (type === 'number' && typeof value === 'number') ||
    (type === 'string' && typeof value === 'string')
  ) {
    return value;
  }

  switch (type) {
    case 'number':
      const num = Number(value);
      return isNaN(num) ? value : num;
    case 'boolean':
      // Already a boolean
      if (typeof value === 'boolean') {
        return value;
      }
      // String representation of boolean
      if (typeof value === 'string') {
        const lowered = value.toLowerCase().trim();
        if (
          lowered === 'true' ||
          lowered === 'yes' ||
          lowered === '1' ||
          lowered === 'y'
        ) {
          return true;
        }
        if (
          lowered === 'false' ||
          lowered === 'no' ||
          lowered === '0' ||
          lowered === 'n'
        ) {
          return false;
        }
      }
      // Number 1 or 0
      if (typeof value === 'number') {
        if (value === 1) {
          return true;
        }
        if (value === 0) {
          return false;
        }
      }
      return value;
    case 'date':
      const date = new Date(value);
      return isNaN(date.getTime()) ? value : date;
    case 'null':
      return null;
    case 'string':
    default:
      return String(value);
  }
};

// Process all data and cast values based on column types
export const castDataWithColumnTypes = (
  data: any[],
  columns: ParsedColumn[]
): any[] => {
  if (data.length === 0 || columns.length === 0) {
    return data;
  }

  // Create a map of column names to their types for easy lookup
  const columnTypes = new Map<string, ParsedColumn['type']>();
  columns.forEach(col => columnTypes.set(col.name, col.type));

  // Cast each value in the data based on its column type
  return data.map(row => {
    const castedRow: Record<string, any> = {};

    Object.keys(row).forEach(key => {
      const type = columnTypes.get(key) || 'string';
      castedRow[key] = castValueToType(row[key], type);
    });

    return castedRow;
  });
};

export const parseCSV = async (
  file: File,
  delimiter: string = 'auto'
): Promise<ParseResult> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = e => {
      const buffer = e.target?.result as ArrayBuffer;
      const decoder = new TextDecoder();
      const text = decoder.decode(buffer);

      Papa.parse(text, {
        header: true,
        skipEmptyLines: true,
        encoding: 'UTF-8',
        delimiter: delimiter === 'auto' ? undefined : delimiter,
        complete: (results: PapaParseResult<any>) => {
          const columns = analyzeColumns(results.data);

          // Cast the data to the appropriate types based on column analysis
          const castedData = castDataWithColumnTypes(results.data, columns);

          const parseResult: ParseResult = {
            data: castedData,
            errors: results.errors.map((err: ParseError) => ({
              message: err.message,
              row: err.row,
            })),
            meta: {
              delimiter: results.meta.delimiter,
              linebreak: results.meta.linebreak || '\n',
              columns,
              totalRows: results.data.length,
              encoding: 'UTF-8',
            },
          };

          resolve(parseResult);
        },
        error: (error: Error) => {
          reject(error);
        },
      });
    };
    reader.onerror = () => reject(new Error('Failed to read file'));
    reader.readAsArrayBuffer(file);
  });
};
