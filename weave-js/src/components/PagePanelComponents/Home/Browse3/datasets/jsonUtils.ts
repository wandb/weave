export interface JSONParseResult {
  data: any[];
  error?: string;
}

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

export const parseJSON = async (file: File): Promise<JSONParseResult> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = e => {
      try {
        const text = e.target?.result as string;
        const data = JSON.parse(text);

        if (!Array.isArray(data)) {
          if (typeof data === 'object' && data !== null) {
            // Single object case - wrap in array
            const rows = [data];
            resolve({
              data: rows.map(row => unnestObject(row)),
            });
          } else {
            reject(
              new Error(
                'JSON content must be an array of objects or a single object'
              )
            );
          }
          return;
        }

        if (data.length > 0 && typeof data[0] !== 'object') {
          reject(new Error('JSON array must contain objects'));
          return;
        }

        // Unnest all objects in the rows
        const unnestedRows = data.map(row => unnestObject(row));
        resolve({
          data: unnestedRows,
        });
      } catch (error) {
        reject(
          error instanceof Error ? error : new Error('Failed to parse JSON')
        );
      }
    };
    reader.onerror = () => reject(new Error('Failed to read file'));
    reader.readAsText(file);
  });
};

export const parseJSONL = async (file: File): Promise<JSONParseResult> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = e => {
      try {
        const text = e.target?.result as string;
        const rows = text
          .split('\n')
          .filter(line => line.trim())
          .map(line => {
            try {
              return JSON.parse(line);
            } catch (error) {
              throw new Error(
                `Invalid JSONL: Each line must be valid JSON. Error at line: ${line}`
              );
            }
          });

        if (rows.length > 0 && typeof rows[0] !== 'object') {
          reject(new Error('JSONL must contain objects on each line'));
          return;
        }

        // Unnest all objects in the rows
        const unnestedRows = rows.map(row => unnestObject(row));
        resolve({
          data: unnestedRows,
        });
      } catch (error) {
        reject(
          error instanceof Error ? error : new Error('Failed to parse JSONL')
        );
      }
    };
    reader.onerror = () => reject(new Error('Failed to read file'));
    reader.readAsText(file);
  });
};
