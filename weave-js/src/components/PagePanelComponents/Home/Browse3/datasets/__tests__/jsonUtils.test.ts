import {beforeEach, describe, expect, it, vi} from 'vitest';

import {
  analyzeColumns,
  castDataWithColumnTypes,
  ParsedColumn,
} from '../csvUtils';
import {parseJSON, parseJSONL} from '../jsonUtils';

// Mock the csvUtils functions
vi.mock('../csvUtils', () => ({
  analyzeColumns: vi.fn(),
  castDataWithColumnTypes: vi.fn(),
}));

describe('jsonUtils', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('parseJSON', () => {
    it('should parse a JSON array of objects', async () => {
      const mockData = [
        {name: 'John', age: 30, active: true},
        {name: 'Jane', age: 25, active: false},
      ];
      const mockColumns: ParsedColumn[] = [
        {name: 'name', type: 'string', sample: 'John'},
        {name: 'age', type: 'number', sample: 30},
        {name: 'active', type: 'boolean', sample: true},
      ];
      const mockCastedData = mockData;

      (analyzeColumns as any).mockReturnValue(mockColumns);
      (castDataWithColumnTypes as any).mockReturnValue(mockCastedData);

      const file = new File([JSON.stringify(mockData)], 'test.json', {
        type: 'application/json',
      });

      const result = await parseJSON(file);

      expect(result.data).toEqual(mockCastedData);
      expect(result.errors).toHaveLength(0);
      expect(result.meta.columns).toEqual(mockColumns);
      expect(result.meta.totalRows).toBe(2);
      expect(analyzeColumns).toHaveBeenCalledWith(mockData);
      expect(castDataWithColumnTypes).toHaveBeenCalledWith(
        mockData,
        mockColumns
      );
    });

    it('should parse a single JSON object', async () => {
      const mockData = {name: 'John', age: 30, active: true};
      const mockColumns: ParsedColumn[] = [
        {name: 'name', type: 'string', sample: 'John'},
        {name: 'age', type: 'number', sample: 30},
        {name: 'active', type: 'boolean', sample: true},
      ];
      const mockCastedData = [mockData];

      (analyzeColumns as any).mockReturnValue(mockColumns);
      (castDataWithColumnTypes as any).mockReturnValue(mockCastedData);

      const file = new File([JSON.stringify(mockData)], 'test.json', {
        type: 'application/json',
      });

      const result = await parseJSON(file);

      expect(result.data).toEqual(mockCastedData);
      expect(result.errors).toHaveLength(0);
      expect(result.meta.columns).toEqual(mockColumns);
      expect(result.meta.totalRows).toBe(1);
      expect(analyzeColumns).toHaveBeenCalledWith([mockData]);
      expect(castDataWithColumnTypes).toHaveBeenCalledWith(
        [mockData],
        mockColumns
      );
    });

    it('should handle invalid JSON', async () => {
      const file = new File(['invalid json'], 'test.json', {
        type: 'application/json',
      });

      await expect(parseJSON(file)).rejects.toThrow();
    });

    it('should handle empty JSON array', async () => {
      const mockData: any[] = [];
      const mockColumns: ParsedColumn[] = [];
      const mockCastedData: any[] = [];

      (analyzeColumns as any).mockReturnValue(mockColumns);
      (castDataWithColumnTypes as any).mockReturnValue(mockCastedData);

      const file = new File([JSON.stringify(mockData)], 'test.json', {
        type: 'application/json',
      });

      const result = await parseJSON(file);

      expect(result.data).toEqual(mockCastedData);
      expect(result.errors).toHaveLength(0);
      expect(result.meta.columns).toEqual(mockColumns);
      expect(result.meta.totalRows).toBe(0);
    });
  });

  describe('parseJSONL', () => {
    it('should parse JSONL file with multiple objects', async () => {
      const mockData = [
        {name: 'John', age: 30, active: true},
        {name: 'Jane', age: 25, active: false},
      ];
      const mockColumns: ParsedColumn[] = [
        {name: 'name', type: 'string', sample: 'John'},
        {name: 'age', type: 'number', sample: 30},
        {name: 'active', type: 'boolean', sample: true},
      ];
      const mockCastedData = mockData;

      (analyzeColumns as any).mockReturnValue(mockColumns);
      (castDataWithColumnTypes as any).mockReturnValue(mockCastedData);

      const jsonlContent = mockData.map(obj => JSON.stringify(obj)).join('\n');
      const file = new File([jsonlContent], 'test.jsonl', {
        type: 'application/x-jsonlines',
      });

      const result = await parseJSONL(file);

      expect(result.data).toEqual(mockCastedData);
      expect(result.errors).toHaveLength(0);
      expect(result.meta.columns).toEqual(mockColumns);
      expect(result.meta.totalRows).toBe(2);
      expect(analyzeColumns).toHaveBeenCalledWith(mockData);
      expect(castDataWithColumnTypes).toHaveBeenCalledWith(
        mockData,
        mockColumns
      );
    });

    it('should handle empty lines in JSONL file', async () => {
      const mockData = [
        {name: 'John', age: 30},
        {name: 'Jane', age: 25},
      ];
      const mockColumns: ParsedColumn[] = [
        {name: 'name', type: 'string', sample: 'John'},
        {name: 'age', type: 'number', sample: 30},
      ];
      const mockCastedData = mockData;

      (analyzeColumns as any).mockReturnValue(mockColumns);
      (castDataWithColumnTypes as any).mockReturnValue(mockCastedData);

      const jsonlContent = [
        JSON.stringify(mockData[0]),
        '',
        JSON.stringify(mockData[1]),
        '',
      ].join('\n');
      const file = new File([jsonlContent], 'test.jsonl', {
        type: 'application/x-jsonlines',
      });

      const result = await parseJSONL(file);

      expect(result.data).toEqual(mockCastedData);
      expect(result.errors).toHaveLength(0);
      expect(result.meta.totalRows).toBe(2);
    });

    it('should handle invalid JSONL line', async () => {
      const jsonlContent = [
        JSON.stringify({name: 'John', age: 30}),
        'invalid json',
        JSON.stringify({name: 'Jane', age: 25}),
      ].join('\n');
      const file = new File([jsonlContent], 'test.jsonl', {
        type: 'application/x-jsonlines',
      });

      await expect(parseJSONL(file)).rejects.toThrow();
    });

    it('should handle empty JSONL file', async () => {
      const mockColumns: ParsedColumn[] = [];
      const mockCastedData: any[] = [];

      (analyzeColumns as any).mockReturnValue(mockColumns);
      (castDataWithColumnTypes as any).mockReturnValue(mockCastedData);

      const file = new File([''], 'test.jsonl', {
        type: 'application/x-jsonlines',
      });

      const result = await parseJSONL(file);

      expect(result.data).toEqual(mockCastedData);
      expect(result.errors).toHaveLength(0);
      expect(result.meta.columns).toEqual(mockColumns);
      expect(result.meta.totalRows).toBe(0);
    });
  });
});
