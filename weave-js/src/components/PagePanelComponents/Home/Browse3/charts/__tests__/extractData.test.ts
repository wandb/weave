/**
 * Unit tests for extractData.ts
 *
 * Tests the core data extraction and transformation logic used throughout the charting system.
 */

// Import the mocked functions
import {beforeEach, describe, expect, it, vi} from 'vitest';

import {CallSchema} from '../../pages/wfReactInterface/wfDataModelHooksInterface';
import {
  convertSchemaToAxisFields,
  extractCallData,
  extractKeysFromObject,
  getInputOutputFieldValue,
  getValueType,
} from '../extractData';
import {ExtractedCallData, FieldSchema, FieldType} from '../types';

// Mock the parseRefMaybe and isWeaveObjectRef functions
vi.mock('@wandb/weave/react', () => ({
  parseRefMaybe: vi.fn(),
  isWeaveObjectRef: vi.fn(),
}));

describe('extractData', () => {
  describe('getValueType', () => {
    it('should correctly identify primitive types', () => {
      expect(getValueType('hello')).toBe('string');
      expect(getValueType(42)).toBe('number');
      expect(getValueType(true)).toBe('boolean');
      expect(getValueType(false)).toBe('boolean');
    });

    it('should correctly identify null and undefined', () => {
      expect(getValueType(null)).toBe('null');
      expect(getValueType(undefined)).toBe('undefined');
    });

    it('should correctly identify arrays and objects', () => {
      expect(getValueType([])).toBe('array');
      expect(getValueType([1, 2, 3])).toBe('array');
      expect(getValueType({})).toBe('object');
      expect(getValueType({key: 'value'})).toBe('object');
    });

    it('should default to string for unknown types', () => {
      expect(getValueType(Symbol('test'))).toBe('string');
      expect(getValueType(() => {})).toBe('string');
    });
  });

  describe('extractKeysFromObject', () => {
    let fieldsMap: Map<string, FieldSchema>;

    beforeEach(() => {
      fieldsMap = new Map();
    });

    it('should extract simple primitive fields', () => {
      const obj = {
        name: 'test',
        count: 42,
        enabled: true,
      };

      extractKeysFromObject(obj, 'input', fieldsMap);

      expect(fieldsMap.size).toBe(3);
      expect(fieldsMap.get('input.name')).toEqual({
        key: 'input.name',
        types: new Set(['string']),
        label: 'Input: name',
        source: 'input',
        fullPath: 'name',
      });
      expect(fieldsMap.get('input.count')).toEqual({
        key: 'input.count',
        types: new Set(['number']),
        label: 'Input: count',
        source: 'input',
        fullPath: 'count',
      });
      expect(fieldsMap.get('input.enabled')).toEqual({
        key: 'input.enabled',
        types: new Set(['boolean']),
        label: 'Input: enabled',
        source: 'input',
        fullPath: 'enabled',
      });
    });

    it('should extract nested object fields', () => {
      const obj = {
        user: {
          profile: {
            name: 'John',
            age: 30,
          },
        },
      };

      extractKeysFromObject(obj, 'output', fieldsMap);

      expect(fieldsMap.size).toBe(2);
      expect(fieldsMap.get('output.user.profile.name')).toEqual({
        key: 'output.user.profile.name',
        types: new Set(['string']),
        label: 'Output: user.profile.name',
        source: 'output',
        fullPath: 'user.profile.name',
      });
      expect(fieldsMap.get('output.user.profile.age')).toEqual({
        key: 'output.user.profile.age',
        types: new Set(['number']),
        label: 'Output: user.profile.age',
        source: 'output',
        fullPath: 'user.profile.age',
      });
    });

    it('should skip underscore-prefixed keys', () => {
      const obj = {
        _private: 'secret',
        public: 'visible',
      };

      extractKeysFromObject(obj, 'input', fieldsMap);

      expect(fieldsMap.size).toBe(1);
      expect(fieldsMap.has('input._private')).toBe(false);
      expect(fieldsMap.has('input.public')).toBe(true);
    });

    it('should respect maxDepth parameter', () => {
      const obj = {
        level1: {
          level2: {
            level3: {
              level4: {
                deep: 'value',
              },
            },
          },
        },
      };

      extractKeysFromObject(obj, 'input', fieldsMap, '', 2);

      expect(fieldsMap.size).toBe(0); // No primitive values within depth 2
    });

    it('should handle arrays gracefully', () => {
      const obj = {
        items: [1, 2, 3],
        valid: true,
      };

      extractKeysFromObject(obj, 'input', fieldsMap);

      expect(fieldsMap.size).toBe(1);
      expect(fieldsMap.has('input.items')).toBe(false); // Arrays are skipped
      expect(fieldsMap.has('input.valid')).toBe(true);
    });

    it('should merge types for existing fields', () => {
      const obj1 = {field: 'string_value'};
      const obj2 = {field: 42};

      extractKeysFromObject(obj1, 'input', fieldsMap);
      extractKeysFromObject(obj2, 'input', fieldsMap);

      expect(fieldsMap.size).toBe(1);
      expect(fieldsMap.get('input.field')?.types).toEqual(
        new Set(['string', 'number'])
      );
    });
  });

  describe('getInputOutputFieldValue', () => {
    const extractedData: ExtractedCallData = {
      callId: 'test-call',
      traceId: 'test-trace',
      started_at: '2023-01-01T00:00:00Z',
      inputs: {
        message: 'Hello world',
        config: {
          temperature: 0.7,
          model: 'gpt-4',
        },
      },
      output: {
        response: 'Hi there!',
        metadata: {
          tokens: 150,
          confidence: 0.95,
        },
      },
    };

    it('should extract simple input fields', () => {
      expect(getInputOutputFieldValue(extractedData, 'input.message')).toBe(
        'Hello world'
      );
    });

    it('should extract nested input fields', () => {
      expect(
        getInputOutputFieldValue(extractedData, 'input.config.temperature')
      ).toBe(0.7);
      expect(
        getInputOutputFieldValue(extractedData, 'input.config.model')
      ).toBe('gpt-4');
    });

    it('should extract simple output fields', () => {
      expect(getInputOutputFieldValue(extractedData, 'output.response')).toBe(
        'Hi there!'
      );
    });

    it('should extract nested output fields', () => {
      expect(
        getInputOutputFieldValue(extractedData, 'output.metadata.tokens')
      ).toBe(150);
      expect(
        getInputOutputFieldValue(extractedData, 'output.metadata.confidence')
      ).toBe(0.95);
    });

    it('should return undefined for missing fields', () => {
      expect(getInputOutputFieldValue(extractedData, 'input.nonexistent')).toBe(
        undefined
      );
      expect(
        getInputOutputFieldValue(extractedData, 'output.missing.field')
      ).toBe(undefined);
    });

    it('should return undefined for invalid source', () => {
      expect(getInputOutputFieldValue(extractedData, 'invalid.field')).toBe(
        undefined
      );
    });

    it('should handle missing inputs/outputs gracefully', () => {
      const dataWithoutInputs: ExtractedCallData = {
        ...extractedData,
        inputs: undefined,
        output: undefined,
      };

      expect(getInputOutputFieldValue(dataWithoutInputs, 'input.message')).toBe(
        undefined
      );
      expect(
        getInputOutputFieldValue(dataWithoutInputs, 'output.response')
      ).toBe(undefined);
    });
  });

  describe('extractCallData', () => {
    const mockCallSchema = {
      entity: 'test-entity',
      project: 'test-project',
      callId: 'call-123',
      traceId: 'trace-456',
      traceCall: {
        id: 'call-123',
        started_at: '2023-01-01T10:00:00Z',
        ended_at: '2023-01-01T10:00:05Z',
        op_name: 'test_op',
        display_name: 'Test Operation',
        exception: null,
        summary: {
          weave: {
            costs: {
              'openai-gpt4': {
                prompt_tokens: 100,
                completion_tokens: 50,
                prompt_tokens_total_cost: 0.003,
                completion_tokens_total_cost: 0.001,
                prompt_token_cost_unit: 'USD',
                completion_token_cost_unit: 'USD',
              },
            },
          },
        },
      },
      rawSpan: {
        summary: {
          latency_s: 5.0,
        },
        inputs: {
          message: 'test input',
        },
        output: {
          response: 'test output',
        },
      },
    } as unknown as CallSchema;

    it('should extract basic call data correctly', () => {
      const result = extractCallData([mockCallSchema]);

      expect(result).toHaveLength(1);
      expect(result[0]).toMatchObject({
        callId: 'call-123',
        traceId: 'trace-456',
        started_at: '2023-01-01T10:00:00Z',
        ended_at: '2023-01-01T10:00:05Z',
        latency: 5.0,
        exception: 0,
        op_name: 'test_op',
        display_name: 'Test Operation',
        inputs: {message: 'test input'},
        output: {response: 'test output'},
      });
    });

    it('should calculate costs correctly', () => {
      const result = extractCallData([mockCallSchema]);

      expect(result[0]).toMatchObject({
        cost: 0.004, // 0.003 + 0.001
        prompt_tokens: 100,
        completion_tokens: 50,
        prompt_cost: 0.003,
        completion_cost: 0.001,
      });
    });

    it('should handle multiple cost entries', () => {
      const callWithMultipleCosts = {
        ...mockCallSchema,
        traceCall: {
          ...mockCallSchema.traceCall,
          summary: {
            weave: {
              costs: {
                'openai-gpt4': {
                  prompt_tokens: 50,
                  completion_tokens: 25,
                  prompt_tokens_total_cost: 0.0015,
                  completion_tokens_total_cost: 0.0005,
                  prompt_token_cost_unit: 'USD',
                  completion_token_cost_unit: 'USD',
                },
                'openai-gpt3': {
                  prompt_tokens: 30,
                  completion_tokens: 15,
                  prompt_tokens_total_cost: 0.0006,
                  completion_tokens_total_cost: 0.0003,
                  prompt_token_cost_unit: 'USD',
                  completion_token_cost_unit: 'USD',
                },
              },
            },
          },
        },
      } as CallSchema;

      const result = extractCallData([callWithMultipleCosts]);

      expect(result[0]).toMatchObject({
        cost: 0.0029, // 0.0015 + 0.0005 + 0.0006 + 0.0003
        prompt_tokens: 80, // 50 + 30
        completion_tokens: 40, // 25 + 15
        prompt_cost: 0.0021, // 0.0015 + 0.0006
        completion_cost: 0.0008, // 0.0005 + 0.0003
      });
    });

    it('should handle non-USD currencies with warnings', () => {
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

      const callWithEuroCosts = {
        ...mockCallSchema,
        traceCall: {
          ...mockCallSchema.traceCall,
          summary: {
            weave: {
              costs: {
                'openai-gpt4': {
                  prompt_tokens: 100,
                  completion_tokens: 50,
                  prompt_tokens_total_cost: 0.002,
                  completion_tokens_total_cost: 0.001,
                  prompt_token_cost_unit: 'EUR',
                  completion_token_cost_unit: 'EUR',
                },
              },
            },
          },
        },
      } as CallSchema;

      const result = extractCallData([callWithEuroCosts]);

      expect(consoleSpy).toHaveBeenCalledWith(
        'Skipping prompt cost in non-USD currency: EUR'
      );
      expect(consoleSpy).toHaveBeenCalledWith(
        'Skipping completion cost in non-USD currency: EUR'
      );

      // Should still include token counts but not costs
      expect(result[0]).toMatchObject({
        prompt_tokens: 100,
        completion_tokens: 50,
        cost: undefined,
        prompt_cost: 0, // Costs in non-USD currencies are excluded
        completion_cost: 0,
      });

      consoleSpy.mockRestore();
    });

    it('should handle calls with exceptions', () => {
      const callWithException = {
        ...mockCallSchema,
        traceCall: {
          ...mockCallSchema.traceCall,
          exception: 'Some error occurred',
        },
      } as CallSchema;

      const result = extractCallData([callWithException]);

      expect(result[0].exception).toBe(1);
    });

    it('should handle empty calls array', () => {
      const result = extractCallData([]);
      expect(result).toEqual([]);
    });

    it('should handle calls without cost data', () => {
      const callWithoutCosts = {
        ...mockCallSchema,
        traceCall: {
          ...mockCallSchema.traceCall,
          summary: {},
        },
      } as CallSchema;

      const result = extractCallData([callWithoutCosts]);

      expect(result[0]).toMatchObject({
        cost: undefined,
        prompt_tokens: undefined,
        completion_tokens: undefined,
        prompt_cost: undefined,
        completion_cost: undefined,
      });
    });
  });

  describe('convertSchemaToAxisFields', () => {
    it('should convert field schemas to axis fields', () => {
      const schema = {
        inputFields: new Map([
          [
            'input.temperature',
            {
              key: 'input.temperature',
              types: new Set(['number'] as FieldType[]),
              label: 'Input: temperature',
              source: 'input' as const,
              fullPath: 'temperature',
            },
          ],
          [
            'input.message',
            {
              key: 'input.message',
              types: new Set(['string'] as const),
              label: 'Input: message',
              source: 'input' as const,
              fullPath: 'message',
            },
          ],
        ]),
        outputFields: new Map([
          [
            'output.confidence',
            {
              key: 'output.confidence',
              types: new Set(['number'] as FieldType[]),
              label: 'Output: confidence',
              source: 'output' as const,
              fullPath: 'confidence',
            },
          ],
        ]),
        annotationFields: new Map(),
        scoreFields: new Map(),
        reactionFields: new Map(),
      };

      const axisFields = convertSchemaToAxisFields(schema);

      expect(axisFields).toHaveLength(3);

      const temperatureField = axisFields.find(
        f => f.key === 'input.temperature'
      );
      expect(temperatureField).toEqual({
        key: 'input.temperature',
        label: 'Input: temperature',
        type: 'number',
        render: expect.any(Function),
      });

      const messageField = axisFields.find(f => f.key === 'input.message');
      expect(messageField).toEqual({
        key: 'input.message',
        label: 'Input: message',
        type: 'string',
        render: expect.any(Function),
      });

      const confidenceField = axisFields.find(
        f => f.key === 'output.confidence'
      );
      expect(confidenceField).toEqual({
        key: 'output.confidence',
        label: 'Output: confidence',
        type: 'number',
        render: expect.any(Function),
      });
    });

    it('should prioritize number type over other types', () => {
      const schema = {
        inputFields: new Map([
          [
            'input.mixed',
            {
              key: 'input.mixed',
              types: new Set(['string', 'number', 'boolean'] as const),
              label: 'Input: mixed',
              source: 'input' as const,
              fullPath: 'mixed',
            },
          ],
        ]),
        outputFields: new Map(),
        annotationFields: new Map(),
        scoreFields: new Map(),
        reactionFields: new Map(),
      };

      const axisFields = convertSchemaToAxisFields(schema);

      expect(axisFields[0].type).toBe('number');
    });
  });
});
