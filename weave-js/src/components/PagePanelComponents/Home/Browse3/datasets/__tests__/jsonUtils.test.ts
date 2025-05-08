import {describe, expect, it} from 'vitest';

import {parseJSON, parseJSONL} from '../jsonUtils';

describe('jsonUtils', () => {
  describe('parseJSON', () => {
    it('should parse a JSON array of objects', async () => {
      const mockData = [
        {name: 'John', age: 30, active: true},
        {name: 'Jane', age: 25, active: false},
      ];

      const file = new File([JSON.stringify(mockData)], 'test.json', {
        type: 'application/json',
      });

      const result = await parseJSON(file);

      expect(result.data).toEqual(mockData);
    });

    it('should parse a single JSON object', async () => {
      const mockData = {name: 'John', age: 30, active: true};

      const file = new File([JSON.stringify(mockData)], 'test.json', {
        type: 'application/json',
      });

      const result = await parseJSON(file);

      expect(result.data).toEqual([mockData]);
    });

    it('should handle invalid JSON', async () => {
      const file = new File(['invalid json'], 'test.json', {
        type: 'application/json',
      });

      await expect(parseJSON(file)).rejects.toThrow();
    });

    it('should handle empty JSON array', async () => {
      const mockData: any[] = [];

      const file = new File([JSON.stringify(mockData)], 'test.json', {
        type: 'application/json',
      });

      const result = await parseJSON(file);

      expect(result.data).toEqual([]);
    });
  });

  describe('parseJSONL', () => {
    it('should parse JSONL file with multiple objects', async () => {
      const mockData = [
        {name: 'John', age: 30, active: true},
        {name: 'Jane', age: 25, active: false},
      ];

      const jsonlContent = mockData.map(obj => JSON.stringify(obj)).join('\n');
      const file = new File([jsonlContent], 'test.jsonl', {
        type: 'application/x-jsonlines',
      });

      const result = await parseJSONL(file);

      expect(result.data).toEqual(mockData);
    });

    it('should handle empty lines in JSONL file', async () => {
      const mockData = [
        {name: 'John', age: 30},
        {name: 'Jane', age: 25},
      ];

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

      expect(result.data).toEqual(mockData);
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
      const file = new File([''], 'test.jsonl', {
        type: 'application/x-jsonlines',
      });

      const result = await parseJSONL(file);

      expect(result.data).toEqual([]);
    });
  });
});
